import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "pycad_installer_build", ROOT / "installer/build.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_macos_universal_slices_preserve_both_executables():
    x86, arm = b"x86-slice", b"arm-slice"
    fat = builder.fat_macho(x86, arm)
    assert struct.unpack_from(">II", fat) == (0xCAFEBABE, 2)
    for index, data, cpu in [(0, x86, 0x01000007), (1, arm, 0x0100000C)]:
        cputype, subtype, offset, size, align = struct.unpack_from(
            ">IIIII", fat, 8 + index * 20
        )
        assert cputype == cpu and size == len(data) and offset % (1 << align) == 0
        assert fat[offset : offset + size] == data


@pytest.mark.skipif(sys.platform != "linux", reason="executes Linux setup envelope")
def test_linux_self_extractor_preserves_spaced_args_and_only_cleans_its_temp(tmp_path):
    setup = tmp_path / "setup with spaces.run"
    executable = b'#!/bin/sh\nprintf "PAYLOAD:%s\\n" "$@"\n'
    builder.linux_run(setup, executable, b"")
    marker = tmp_path / "keep drawing.pycad"
    marker.write_text("preserve this drawing")
    result = subprocess.run(
        ["sh", str(setup), "--diagnose", "drawing with spaces.pycad"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "PAYLOAD:--diagnose",
        "PAYLOAD:drawing with spaces.pycad",
    ]
    assert marker.read_text() == "preserve this drawing"


def test_macos_zip_permissions_and_unicode_paths(tmp_path):
    path = tmp_path / "setup.zip"
    builder.write_zip(
        path,
        [
            ("PyCAD Setup.app/Contents/MacOS/PyCAD-Setup", b"native", True),
            ("readme ü.txt", b"doc", False),
        ],
    )
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert (
            z.getinfo("PyCAD Setup.app/Contents/MacOS/PyCAD-Setup").external_attr >> 16
            & 0o111
        )
        assert not z.getinfo("readme ü.txt").external_attr >> 16 & 0o111
