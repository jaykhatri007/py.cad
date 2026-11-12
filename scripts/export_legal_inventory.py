"""Record actual installed Python distributions and retain their notice files.

Standard-library only. Run with the application's managed interpreter. This is
an inventory, not a license-compatibility verdict or a complete native SBOM.
"""

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import sysconfig


def filesystem_path(value):
    """Use explicit extended paths for deep wheel notices on Windows."""
    path = os.path.abspath(value)
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        path = '\\\\?\\UNC\\' + path[2:] if path.startswith('\\\\') else '\\\\?\\' + path
    return Path(path)


def export(output, exclude=()):
    output = filesystem_path(output)
    output.mkdir(parents=True, exist_ok=True)
    paths = sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
    records = []
    for dist in sorted(metadata.distributions(path=paths), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        if name.lower().replace("_", "-") in exclude:
            continue
        slug = re.sub(r"[^a-z0-9.-]", "-", name.lower()) + "-" + dist.version
        notices = []
        for entry in dist.files or []:
            filename = Path(str(entry))
            if ".." in filename.parts or filename.is_absolute():
                continue
            if not re.search(r"(?i)(licen[cs]e|copying|copyright|notice)", str(filename)):
                continue
            path = filesystem_path(dist.locate_file(entry))
            if not path.is_file() or path.suffix.lower() in (".so", ".dll", ".pyd", ".pyc"):
                continue
            data = path.read_bytes()
            relative = Path("notices") / slug / filename
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            notices.append({"path": relative.as_posix(), "sha256": hashlib.sha256(data).hexdigest()})
        raw_license = dist.metadata.get("License-Expression") or dist.metadata.get("License")
        classifiers = [s for s in dist.metadata.get_all("Classifier", []) if s.startswith("License ::")]
        records.append({
            "name": name, "version": dist.version,
            "license_metadata": raw_license,
            "license_classifiers": classifiers,
            "project_urls": dist.metadata.get_all("Project-URL", []),
            "home_page": dist.metadata.get("Home-page"),
            "pypi_release": f"https://pypi.org/project/{name}/{dist.version}/",
            "requires_dist": dist.requires or [],
            "notice_files": notices,
            "review": "Notice files retained; bundled native components still need review" if notices else "No notice file in installed RECORD; consult upstream and LICENSES/upstream",
        })
    manifest = {
        "format": "PyCAD dependency license inventory 1",
        "python": platform.python_version(), "platform": platform.platform(),
        "scope": "Installed Python distributions in this interpreter's prefix; metadata is not a legal determination. Native subcomponents may have additional licenses.",
        "packages": records,
    }
    (output / "inventory.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    table = ["# Installed dependency inventory", "", manifest["scope"], "", "| Distribution | Version | License metadata / classifier | Retained notice files |", "| --- | --- | --- | --- |"]
    for r in records:
        value = r["license_metadata"] or "; ".join(r["license_classifiers"]) or "Not declared; see upstream"
        if len(value) > 120:
            value = "Full copyright/license text in inventory.json and notice files"
        table.append(f"| {r['name']} | {r['version']} | {value.replace(chr(10), ' ').replace('|', '/')} | {len(r['notice_files'])} |")
    (output / "INVENTORY.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    print(f"Retained {len(records)} distribution records and {sum(len(r['notice_files']) for r in records)} notice files in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exclude", default="")
    args = parser.parse_args()
    export(args.output, tuple(args.exclude.split(",")))
