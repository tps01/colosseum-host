"""Host parser checks with supplied text; no real /proc, /sys or sampling."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


def check_input(data: bytes) -> None:
    from colosseum_host.host.collectors import linux

    data = data[:512]
    check_raw_text(data.decode("utf-8", errors="replace"))
    flags = data[0] if data else 0
    values = [int.from_bytes(data[start : start + 4], "little") for start in (1, 5, 9, 13)]
    keys = ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")
    lines = ["noise", "Ignored: not-a-number kB", ""]
    expected = {}
    for bit, (key, value) in enumerate(zip(keys, values)):
        if flags & (1 << bit):
            lines.append(f"{key}: {value} kB")
            expected[key] = value / 1024.0
    if flags & 16:
        lines += ["MemTotal: 1024 kB", "MemTotal: invalid kB"]
        expected["MemTotal"] = 1.0  # Invalid duplicates must not erase a valid field.
    with patch.object(linux, "_read_text", return_value="\n".join(lines)):
        try:
            info = linux.meminfo()
        except OSError:
            assert not {"MemTotal", "MemAvailable"} <= expected.keys()
        else:
            assert {"MemTotal", "MemAvailable"} <= expected.keys()
            assert (info.total_mb, info.available_mb, info.swap_total_mb, info.swap_free_mb) == (
                expected["MemTotal"],
                expected["MemAvailable"],
                expected.get("SwapTotal", 0.0),
                expected.get("SwapFree", 0.0),
            )

    keys = ("pgfault", "pgpgin", "pgpgout", "oom_kill")
    expected_vm = {}
    lines = ["noise", "pgfault bad", "pgpgin 99 extra"]
    for bit, (key, value) in enumerate(zip(keys, values)):
        if flags & (1 << bit):
            expected_vm[key] = value
            lines.append(f"{key} {value}")
    if flags & 32:
        lines += ["pgfault -1", "pgfault bad"]
        expected_vm["pgfault"] = -1
    with patch.object(linux, "_read_text", return_value="\n".join(lines)):
        info = linux.vmstat()
        assert (info.pgfault, info.pgpgin, info.pgpgout, info.oom_kill) == (
            expected_vm.get("pgfault", 0),
            expected_vm.get("pgpgin", 0),
            expected_vm.get("pgpgout", 0),
            expected_vm.get("oom_kill"),
        )
    text = data[1:].decode("utf-8", errors="replace")
    try:
        expected_int = int(text.strip())
    except ValueError:
        expected_int = None
    with patch.object(linux, "_read_text", return_value=text):
        assert linux._read_sys_int(Path("unused")) == expected_int
    with patch.object(linux, "_read_text", side_effect=OSError("unavailable")):
        assert linux._read_sys_int(Path("unused")) is None


def check_raw_text(text: str) -> None:
    """Compare arbitrary rows with a table model, including missing required fields."""
    from colosseum_host.host.collectors import linux

    memory, counters = {}, {}
    for row in text.splitlines():
        columns = row.split()
        if len(columns) < 2:
            continue
        try:
            number = int(columns[1])
        except ValueError:
            continue
        if len(columns) == 2:
            counters[columns[0]] = number
        try:
            memory[columns[0].rstrip(":")] = number / 1024.0
        except OverflowError:
            # Unrepresentable memory values are malformed, like nonnumeric rows.
            continue
    with patch.object(linux, "_read_text", return_value=text):
        try:
            info = linux.meminfo()
        except OSError:
            assert not {"MemTotal", "MemAvailable"} <= memory.keys()
        else:
            assert {"MemTotal", "MemAvailable"} <= memory.keys()
            assert (info.total_mb, info.available_mb, info.swap_total_mb, info.swap_free_mb) == (
                memory["MemTotal"],
                memory["MemAvailable"],
                memory.get("SwapTotal", 0.0),
                memory.get("SwapFree", 0.0),
            )
        vm = linux.vmstat()
        assert (vm.pgfault, vm.pgpgin, vm.pgpgout, vm.oom_kill) == (
            counters.get("pgfault", 0),
            counters.get("pgpgin", 0),
            counters.get("pgpgout", 0),
            counters.get("oom_kill"),
        )


def main() -> None:
    import atheris

    with atheris.instrument_imports(include=["colosseum_host"]):
        import colosseum_host.host.collectors.linux  # noqa: F401
    atheris.Setup(sys.argv, atheris.instrument_func(check_input))
    atheris.Fuzz()


if __name__ == "__main__":
    main()
