"""Encode approved PNG assets as native icons; no redraw or color edits.

Requires ImageMagick's `convert` for format/size exports. Windows resource
generation uses Python's standard library and emits a single COFF .rsrc section.
"""

from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def windows_resource(ico, output):
    data = ico.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    if (reserved, kind) != (0, 1) or not 1 <= count <= 256:
        raise ValueError("Invalid icon file")
    icons, group = [], struct.pack("<HHH", 0, 1, count)
    for i in range(count):
        entry = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        w, h, colors, zero, planes, bpp, size, offset = entry
        image = data[offset:offset + size]
        if len(image) != size:
            raise ValueError("Truncated icon")
        icons.append((i + 1, image))
        group += struct.pack("<BBBBHHIH", w, h, colors, zero, planes, bpp, size, i + 1)
    tree = {3: dict(icons), 14: {1: group}}
    section, leaves = bytearray(), []

    def directory(entries, level=0):
        offset = len(section)
        section.extend(struct.pack("<IIHHHH", 0, 0, 0, 0, 0, len(entries)))
        table = len(section)
        section.extend(b"\0" * (8 * len(entries)))
        for i, (ident, value) in enumerate(sorted(entries.items())):
            if level == 0:
                dest = directory(value, 1) | 0x80000000
            elif level == 1:
                dest = directory({0: value}, 2) | 0x80000000
            else:
                dest = len(section)
                section.extend(b"\0" * 16)
                leaves.append((dest, value))
            struct.pack_into("<II", section, table + i * 8, ident, dest)
        return offset

    directory(tree)
    relocations = bytearray()
    for entry, value in leaves:
        section.extend(b"\0" * ((-len(section)) % 4))
        struct.pack_into("<IIII", section, entry, len(section), len(value), 0, 0)
        section.extend(value)
        relocations.extend(struct.pack("<IIH", entry, 0, 3))  # AMD64_ADDR32NB
    # IMAGE_FILE_HEADER, one section header, raw resources, relocations,
    # one section symbol and its auxiliary record, then empty string table.
    raw = 60
    reloc = raw + len(section)
    symbols = reloc + len(relocations)
    coff = struct.pack("<HHIIIHH", 0x8664, 1, 0, symbols, 2, 0, 0)
    coff += struct.pack("<8sIIIIIIHHI", b".rsrc\0\0\0", 0, 0, len(section), raw, reloc, 0, len(leaves), 0, 0x40000040)
    coff += section + relocations
    coff += struct.pack("<8sIhHBB", b".rsrc\0\0\0", 0, 1, 0, 3, 1)
    coff += struct.pack("<IHHIhBBh", len(section), len(leaves), 0, 0, 0, 0, 0, 0)
    coff += struct.pack("<I", 4)
    output.write_bytes(coff)


def export():
    assets = ROOT / "assets"
    source = assets / "pycad-icon.png"
    subprocess.run(["convert", str(source), "-define", "icon:auto-resize=256,128,64,48,32,24,16", str(assets / "pycad.ico")], check=True)
    chunks = []
    with tempfile.TemporaryDirectory() as temp:
        for code, size in [(b"ic07", 128), (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024)]:
            path = Path(temp) / f"icon-{size}.png"
            subprocess.run(["convert", str(source), "-resize", f"{size}x{size}", str(path)], check=True)
            data = path.read_bytes()
            chunks.append(code + struct.pack(">I", len(data) + 8) + data)
    body = b"".join(chunks)
    (assets / "pycad.icns").write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)
    windows_resource(assets / "pycad.ico", ROOT / "installer/branding_windows_amd64.syso")


if __name__ == "__main__":
    export()
