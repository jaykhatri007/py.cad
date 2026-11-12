"""Build native setup files with embedded PY.cad source. Requires Python + Go.

No third-party Go modules. Runtime bootstrap URLs/hashes are pinned separately.
The resulting installers do not need Go or preinstalled Python on user machines.
"""

from pathlib import Path
import argparse
import hashlib
import json
import html
import os
import plistlib
import shutil
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "installer"
EXCLUDE = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv-linux",
}


def prepare(reuse_payload=False):
    version = (ROOT / "pycad/_version.py").read_text().split('"')[1]
    assets = HERE / "assets"
    assets.mkdir(exist_ok=True)
    for name in ("pycad-logo.png", "pycad-icon.png", "pycad.ico", "pycad.icns"):
        shutil.copyfile(ROOT / "assets" / name, assets / name)
    legal_files = [ROOT / "LICENSE", ROOT / "COPYRIGHT", ROOT / "THIRD_PARTY_NOTICES.md"] + sorted((ROOT / "legal").glob("*.md"))
    (assets / "legal.txt").write_text("\n\n".join(p.name+"\n"+"="*60+"\n"+p.read_text(encoding="utf-8") for p in legal_files),encoding="utf-8")
    legal_html = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>PY.cad · Licenses and Legal</title><style>body{max-width:960px;margin:40px auto;padding:0 24px;font:15px/1.6 system-ui;color:#173042}details{border-bottom:1px solid #c7d5db;padding:15px 0}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,monospace}a{color:#007e83}</style><h1>PY.cad · Licenses and Legal</h1><p>GNU GPL version 3 only · free software, without warranty, subject to applicable law. Your drawings remain yours.</p>'
    for p in legal_files:
        legal_html += '<details><summary>' + html.escape(p.name) + '</summary><pre>' + html.escape(p.read_text()) + '</pre></details>'
    (HERE / "legal.html").write_text(legal_html + '</html>', encoding="utf-8")
    payload = assets / "payload.zip"
    if reuse_payload:
        prior = json.loads((assets / "manifest.json").read_text())
        if prior["Version"] != version or hashlib.sha256(payload.read_bytes()).hexdigest() != prior["payload_sha256"]:
            raise ValueError("The existing application payload and version must match the installer manifest")
    else:
        with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(ROOT.rglob("*")):
                rel = p.relative_to(ROOT)
                if (
                    not p.is_file()
                    or (rel.name.startswith('.') and rel.name not in ('.gitignore','.gitattributes'))
                    or EXCLUDE.intersection(rel.parts)
                    or rel.parts[:2] in (("installer", "assets"), ("installer", "packages"))
                    or p.suffix == ".syso"
                    or rel.as_posix() == "installer/legal.html"
                    or p.suffix in (".pyc", ".pyo")
                    or rel.name.startswith("VALIDATION_")
                ):
                    continue
                info = zipfile.ZipInfo(
                    "PyCAD-v15/" + rel.as_posix(), (2026, 10, 19, 0, 0, 0)
                )
                info.external_attr = (0o100755 if p.suffix == ".sh" or (rel.parts[:3] == ("vendor", "libredwg", "bin") and p.name in ("dwg2dxf", "dwgread", "dwgwrite")) else 0o100644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())
    manifest = {
        **json.loads((HERE / "runtime-sources.json").read_text()),
        "Version": version,
        "payload_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
    }
    (assets / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return version


def write_zip(path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data, executable in entries:
            info = zipfile.ZipInfo(name, (2026, 10, 19, 0, 0, 0))
            info.external_attr = (0o100755 if executable else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)


def fat_macho(x86, arm):
    # FAT_MAGIC with two FAT_ARCH entries. Each Go-produced thin slice retains
    # its own code signature. Developer ID signing/notarization remains a Mac release step.
    align = 14
    off1 = 1 << align
    off2 = ((off1 + len(x86) + (1 << align) - 1) >> align) << align
    header = struct.pack(">II", 0xCAFEBABE, 2)
    header += struct.pack(">IIIII", 0x01000007, 3, off1, len(x86), align)
    header += struct.pack(">IIIII", 0x0100000C, 0, off2, len(arm), align)
    return header.ljust(off1, b"\0") + x86 + b"\0" * (off2 - off1 - len(x86)) + arm


def linux_run(path, amd64, arm64):
    # Fixed-width numeric fields make offsets independent of header length.
    template = """#!/bin/sh
# PY.cad native setup. Supports desktop glibc Linux x86_64 and aarch64.
set -eu
if [ "$(uname -s)" != Linux ]; then echo 'Use the Windows or macOS setup file.' >&2; exit 1; fi
case "$(uname -m)" in
 x86_64|amd64) offset=OFFSET_AMD; size=SIZE_AMD ;;
 aarch64|arm64) echo 'This full Linux release requires Intel/AMD x64; ARM64 is not qualified.' >&2; exit 1 ;;
 *) echo 'PY.cad needs 64-bit Intel/AMD or ARM Linux.' >&2; exit 1 ;;
esac
pycad_temp=$(mktemp -d "${TMPDIR:-/tmp}/pycad-setup.XXXXXXXX")
trap 'rm -rf -- "$pycad_temp"' EXIT HUP INT TERM
# Only the private mktemp directory is removed. Application data is untouched.
tail -c "+$offset" -- "$0" | head -c "$size" > "$pycad_temp/PyCAD-Setup"
chmod 700 "$pycad_temp/PyCAD-Setup"
"$pycad_temp/PyCAD-Setup" "$@"
exit $?
# __PYCAD_NATIVE_PAYLOAD__
"""
    for key in ["OFFSET_AMD", "SIZE_AMD", "OFFSET_ARM", "SIZE_ARM"]:
        template = template.replace(key, "000000000000" + key)
    # Replace placeholders with exactly the same final width.
    lengths = {
        key: len("000000000000" + key)
        for key in ["OFFSET_AMD", "SIZE_AMD", "OFFSET_ARM", "SIZE_ARM"]
    }

    def header(values):
        text = template
        for key, val in values.items():
            text = text.replace("000000000000" + key, str(val).zfill(lengths[key]))
        return text.encode()

    empty = header(dict.fromkeys(lengths, 0))
    actual = header(
        dict(
            OFFSET_AMD=len(empty) + 1,
            SIZE_AMD=len(amd64),
            OFFSET_ARM=len(empty) + len(amd64) + 1,
            SIZE_ARM=len(arm64),
        )
    )
    assert len(actual) == len(empty)
    # POSIX shells interpret leading-zero arithmetic ambiguously, but these
    # fields are passed as decimal strings to head/tail, not shell arithmetic.
    path.write_bytes(actual + amd64 + arm64)
    path.chmod(0o755)


def build(out, go, reuse_payload=False):
    version = prepare(reuse_payload)
    out.mkdir(parents=True, exist_ok=True)
    native = out / "native"
    native.mkdir(exist_ok=True)
    built = {}
    for target in ["linux-amd64", "windows-amd64", "darwin-amd64", "darwin-arm64"]:
        goos, goarch = target.split("-")
        dest = native / (target + (".exe" if goos == "windows" else ""))
        env = {
            **os.environ,
            "GOOS": goos,
            "GOARCH": goarch,
            "CGO_ENABLED": "0",
            "GOTOOLCHAIN": "local",
            "GOTELEMETRY": "off",
        }
        flags = "-s -w -buildid="
        if goos == "windows":
            flags += " -H=windowsgui"
        subprocess.run(
            [
                go,
                "build",
                "-buildvcs=false",
                "-trimpath",
                "-ldflags=" + flags,
                "-o",
                str(dest),
                ".",
            ],
            cwd=HERE,
            env=env,
            check=True,
        )
        built[target] = dest.read_bytes()
    # Release parity gate: every target must link the exact shared Studio art.
    art = [((HERE / "studio/art") / name).read_bytes() for name in ("banner.png", "construction.gif")]
    for target, binary in built.items():
        if not all(asset in binary for asset in art):
            raise ValueError(f"{target} is missing the shared Studio installer artwork")
    windows = out / f"PY.cad-Setup-{version}-Windows-x64.exe"
    windows.write_bytes(built["windows-amd64"])
    mac = fat_macho(built["darwin-amd64"], built["darwin-arm64"])
    plist = plistlib.dumps(
        dict(
            CFBundleName="PY.cad Setup",
            CFBundleDisplayName="PY.cad Setup",
            CFBundleIdentifier="org.pycad.setup",
            CFBundleExecutable="PyCAD-Setup",
            CFBundleIconFile="pycad.icns",
            CFBundlePackageType="APPL",
            CFBundleShortVersionString=version,
            CFBundleVersion=version,
            LSMinimumSystemVersion="13.0",
            NSHighResolutionCapable=True,
        )
    )
    write_zip(
        out / f"PY.cad-Setup-{version}-macOS-Universal.zip",
        [
            ("PY.cad Setup.app/Contents/Info.plist", plist, False),
            ("PY.cad Setup.app/Contents/MacOS/PyCAD-Setup", mac, True),
            ("PY.cad Setup.app/Contents/Resources/pycad.icns", (ROOT / "assets/pycad.icns").read_bytes(), False),
            ("Uninstall-PY.cad.command", (HERE / "studio/Uninstall-PY.cad.command").read_bytes(), True),
            ("uninstall.py", (HERE / "studio/uninstall.py").read_bytes(), False),
        ],
    )
    from studio.package import build as studio_linux
    classic = native / "classic-linux.run"
    linux_run(classic, built["linux-amd64"], b"")
    studio_linux(classic, out / f"PY.cad-Setup-{version}-Linux-x64-Studio.run")
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.iterdir()
        if p.is_file() and p.name.startswith("PY.cad-Setup-")
    }
    (out / "SHA256SUMS.txt").write_text(
        "".join(f"{value}  {name}\n" for name, value in sorted(manifest.items()))
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "setup-build")
    parser.add_argument("--go", default=shutil.which("go") or "go")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--reuse-payload", action="store_true", help="Rebuild installer only, keeping the existing verified CAD payload")
    args = parser.parse_args()
    if args.prepare_only:
        print("Prepared installer assets for", prepare(args.reuse_payload))
    else:
        build(args.output.resolve(), args.go, args.reuse_payload)
