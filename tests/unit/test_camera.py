"""Camera lifecycle and failure propagation without physical hardware."""
from contextlib import suppress
from unittest.mock import MagicMock

import pytest
from colosseum_host.api import camera


@pytest.fixture
def backend(monkeypatch):
    capture = MagicMock()
    frame = MagicMock()
    frame.shape = (480, 640, 3)
    capture.read.return_value = (True, frame)
    writer = MagicMock()
    monkeypatch.setattr(camera.cv2, "VideoCapture", lambda device: capture)
    monkeypatch.setattr(camera.cv2, "VideoWriter", MagicMock(return_value=writer))
    monkeypatch.setattr(camera.cv2, "imwrite", MagicMock(return_value=True))
    yield capture, writer
    for device in list(camera._recordings):
        with suppress(RuntimeError):
            camera.stop_recording(device=device)


def test_picture_releases_camera_on_write_failure(ctx, backend):
    capture, _ = backend
    camera.cv2.imwrite.return_value = False
    with pytest.raises(RuntimeError, match="Cannot write picture"):
        camera.take_picture()
    capture.release.assert_called_once()


def test_picture_saved_under_run_directory(ctx, backend):
    result = camera.take_picture(path="images/webcam.png")
    assert result == str(ctx.output_dir / "images/webcam.png")
    backend[0].release.assert_called_once()


def test_recording_finalizes_and_rejects_duplicate_start(ctx, backend):
    capture, writer = backend
    path = camera.start_recording(fps=1)
    with pytest.raises(ValueError, match="already recording"):
        camera.start_recording()
    assert camera.stop_recording() == path
    writer.write.assert_called()
    capture.release.assert_called_once()
    writer.release.assert_called_once()
    assert not camera._recordings


def test_recording_worker_failure_is_reported_and_releases_resources(ctx, backend):
    capture, writer = backend
    frame = capture.read.return_value[1]
    capture.read.side_effect = [(True, frame), (False, None)]
    camera.start_recording(fps=1000)
    camera._recordings[0].thread.join(timeout=2)
    with pytest.raises(RuntimeError, match="Camera recording failed"):
        camera.stop_recording()
    capture.release.assert_called_once()
    writer.release.assert_called_once()


def test_unavailable_camera_releases_resources(ctx, backend):
    capture, writer = backend
    capture.read.return_value = (False, None)
    with pytest.raises(RuntimeError, match="Cannot read camera"):
        camera.start_recording()
    capture.release.assert_called_once()
    writer.release.assert_called_once()
    assert not camera._recordings


@pytest.mark.parametrize("fps", [0, -1, float("nan"), float("inf")])
def test_invalid_frame_rate(ctx, backend, fps):
    with pytest.raises(ValueError, match="fps"):
        camera.start_recording(fps=fps)


def test_writer_open_failure_releases_camera(ctx, backend):
    capture, writer = backend
    writer.isOpened.return_value = False
    with pytest.raises(RuntimeError, match="Cannot open recording"):
        camera.start_recording()
    capture.release.assert_called_once()
    writer.release.assert_called_once()


def test_picture_rejects_sibling_directory_escape(ctx, backend):
    with pytest.raises(ValueError, match="inside"):
        camera.take_picture(path=f"../{ctx.output_dir.name}-sibling/camera.jpg")
    backend[0].read.assert_not_called()
