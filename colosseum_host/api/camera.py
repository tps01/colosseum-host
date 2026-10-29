"""Webcam snapshots and recordings under the active run's output directory."""

from __future__ import annotations

import math
from threading import Event, Lock, Thread
from time import monotonic

import cv2
from colosseum.decorators import command

from colosseum_host._paths import resolve_artifact_path


class _Recording:
    def __init__(self, device: int, path: str, fps: float) -> None:
        self.path = path
        self.error: Exception | None = None
        self.stop = Event()
        self.capture = cv2.VideoCapture(device)
        self.writer = cv2.VideoWriter()
        try:
            ok, frame = self.capture.read()
            if not self.capture.isOpened() or not ok:
                raise RuntimeError(f"Cannot read camera {device}")
            height, width = frame.shape[:2]
            self.writer.open(path, cv2.VideoWriter.fourcc(*"MJPG"), fps, (width, height))
            if not self.writer.isOpened():
                raise RuntimeError(f"Cannot open recording {path}")
            self.writer.write(frame)
        except Exception:
            self.capture.release()
            self.writer.release()
            raise
        self.thread = Thread(target=self._run, args=(fps,), daemon=True)
        try:
            self.thread.start()
        except RuntimeError:
            self.capture.release()
            self.writer.release()
            raise

    def _run(self, fps: float) -> None:
        try:
            deadline = monotonic()
            while not self.stop.wait(max(0.0, deadline + 1 / fps - monotonic())):
                ok, frame = self.capture.read()
                if not ok:
                    raise RuntimeError("Camera stopped delivering frames")
                self.writer.write(frame)
                deadline = monotonic()
        except Exception as exc:  # noqa: BLE001 - reported to stop_recording's caller
            self.error = exc
        finally:
            self.capture.release()
            self.writer.release()


_recordings: dict[int, _Recording] = {}
_lock = Lock()


@command
def take_picture(*, path: str = "camera.jpg", device: int = 0) -> str:
    """Save one webcam frame as a JPEG or PNG artifact and return its path.

    ``device`` is the OpenCV camera index. Stop a recording on that device before
    taking a picture. Reusing a path overwrites the previous image.

    :param path: Destination under the active run output directory, or an absolute path. Reusing
        it overwrites the file.
        Default: ``'camera.jpg'``.

    :param device: OpenCV camera index; defaults to 0. Requires an accessible local camera.
    :returns: Saved image path as a string.
    :raises ValueError: Unsupported suffix or the selected camera is recording.
    :raises RuntimeError: Camera open/read or image write failed.
    """
    with _lock:
        if device in _recordings:
            raise ValueError(f"Camera {device} is recording")
        target = resolve_artifact_path(path)
        if target.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            raise ValueError("Picture path must end in .jpg, .jpeg, or .png")
        capture = cv2.VideoCapture(device)
        try:
            ok, frame = capture.read()
            if not capture.isOpened() or not ok:
                raise RuntimeError(f"Cannot read camera {device}")
            if not cv2.imwrite(str(target), frame):
                raise RuntimeError(f"Cannot write picture {target}")
        finally:
            capture.release()
        return str(target)


@command
def start_recording(*, path: str = "camera.avi", device: int = 0, fps: float = 30.0) -> str:
    """Start background MJPEG/AVI recording and return the artifact path.

    Call ``stop_recording`` in a ``finally`` block to finalize the video before
    ending the run. Reusing a path overwrites the previous recording. The frame
    rate is a target; actual throughput depends on the camera and host.

    :param path: Destination under the active run output directory, or an absolute path. Reusing
        it overwrites the file.
        Default: ``'camera.avi'``.

    :param device: OpenCV camera index; defaults to 0. One recording per device is allowed.
    :param fps: Positive finite target frames per second; defaults to 30. Actual rate depends on
        the camera and host.
    :returns: Recording artifact path as a string.
    :raises ValueError: Invalid frame rate/suffix, device already recording, or output path in use.
    :raises RuntimeError: Camera or video writer could not open.
    """
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be finite and positive")
    with _lock:
        if device in _recordings:
            raise ValueError(f"Camera {device} is already recording")
        target = resolve_artifact_path(path)
        if target.suffix.lower() != ".avi":
            raise ValueError("Recording path must end in .avi")
        if any(recording.path == str(target) for recording in _recordings.values()):
            raise ValueError("Recording path is already in use")
        _recordings[device] = _Recording(device, str(target), fps)
        return str(target)


@command
def stop_recording(*, device: int = 0) -> str:
    """Stop and finalize a recording; raise if capture failed in the worker.

    :param device: OpenCV camera index passed to start_recording; defaults to 0.
    :returns: Finalized recording path as a string.
    :raises ValueError: No recording is active for the selected device.
    :raises RuntimeError: The recording worker failed to capture frames.

    A blocked camera read can delay this call. Use it in finally before endex.
    """
    with _lock:
        recording = _recordings.pop(device, None)
        if recording is None:
            raise ValueError(f"Camera {device} is not recording")
        recording.stop.set()
        recording.thread.join()
        if recording.error is not None:
            raise RuntimeError("Camera recording failed") from recording.error
        return recording.path
