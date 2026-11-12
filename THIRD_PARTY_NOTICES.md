# Third-party notices — PY.cad 16.45.0

Project material with licensable rights held is GPL-3.0-only. This does not relicense upstream code.
Keep all accompanying upstream notices when redistributing relevant material.

| Component | Reviewed version | License / retained material | Role |
| --- | --- | --- | --- |
| PyQt6 | 6.11.0 | GPL-3.0-only; exact installed LICENSE | Desktop Python bindings |
| Qt via PyQt6-Qt6 | 6.11.2 | LGPLv3 notice; Qt has additional component licenses | Desktop framework |
| PyQt6-sip | 13.13.0 | BSD-2-Clause | Binding support |
| GNU LibreDWG | 0.14 | GPL-3.0-or-later; unmodified corresponding source, COPYING, AUTHORS, jsmn notice and rebuild instructions under vendor/libredwg | Bundled DWG readers and R2000 writer |
| ezdxf | 1.4.4 | MIT | DXF exchange and hatch pattern library |
| pypdf | 6.10.0 | BSD-3-Clause; exact wheel LICENSE retained in LICENSES/upstream | PDF vector path parser |
| NumPy | 2.3.5 | BSD-3-Clause plus bundled-component notices in full wheel LICENSE | Numerical operations |
| CadQuery | 2.7.0 | Apache-2.0 | Optional solid modeling |
| cadquery-ocp | 7.8.1.1.post1 | Apache-2.0 wrapper; OCCT retains LGPL-2.1 + OCCT exception | Kernel bindings |
| Open CASCADE | 7.8.1 family | LGPL-2.1 with OCCT exception; exact upstream texts retained | Native geometry kernel |
| IfcOpenShell | 0.9.0 | LGPL-3.0-or-later; upstream COPYING/COPYING.LESSER and source header retained | Optional IFC export |
| CasADi | 3.8.1 | LGPL-3.0-or-later; numerous solver/plugin licenses retained verbatim | CadQuery dependency |
| VTK | 9.3.1 | BSD and bundled-component notices | CadQuery dependency |
| uv | 0.9.26 | MIT OR Apache-2.0 | Downloaded setup/runtime manager |
| CPython | Managed Python 3.12 | PSF license and historical/bundled notices; actual micro version depends on managed runtime selection | Downloaded interpreter |
| Go runtime | 1.27.3 build toolchain | BSD-3-Clause; Go-LICENSE.txt and Go-PATENTS.txt | Compiled native installer |

The longer table with 48 exact Python distribution versions is in
`LICENSES/reference-linux/INVENTORY.md`. Machine-readable dependency metadata,
upstream URLs and notice hashes are in its `inventory.json`. The `notices`
directory preserves 143 files without rewriting their terms, including the
NumPy, CasADi, font, Shapely/GEOS and other bundled notices present in the wheels.
`LICENSES/upstream/manifest.json` identifies additional fetched source notices.

Some wheels do not include all native-component source/license detail. An
inventory records what was found; it is not an independent complete license
audit. See legal/RESEARCH.md and legal/DISTRIBUTION.md for these limits and duties.

## External, optional and development components

ODA File Converter is proprietary and must be installed/licensed separately.
It is not bundled. Microsoft's optional Visual C++ runtime installer is also
external and governed by Microsoft terms; PY.cad's GPL does not grant rights to
redistribute it independently. No Autodesk SDK is bundled.

AI models, hosted providers and user plugins are not covered by this project
license. Review their separate terms and data handling. No model weights or
provider subscription are included.

Development/test-only tools are not application runtime dependencies:
pytest (MIT), Ruff (MIT), PyMuPDF (AGPLv3 or commercial) and optional PyInstaller
(GPLv2-or-later with its bootloader exception). Their source/terms must be
reviewed if you redistribute those tools or use a different packaging route.

Full license texts in LICENSES are included for reference and retention. Do not
infer that every component uses every license in that directory. Each upstream
notice and relevant version governs its component. No affiliation or endorsement
by any upstream publisher is claimed.


## GNU LibreDWG 0.14 — DWG reader (16.14)

The bundled dwg2dxf reader is copyright the LibreDWG contributors and is
licensed GPL-3.0-or-later. Its code is not original PY.cad code. Windows x64
uses the unchanged dwg2dxf.exe and libredwg-0.dll from the official 0.14 win64
release. Linux x64 is built from the unchanged upstream 0.14 source archive.
The full corresponding source archive, COPYING, AUTHORS, jsmn MIT license, upstream README and
INSTALL, build instructions, archive URLs and SHA-256 records are shipped in
vendor/libredwg. The two Windows binaries depend only on the Windows system
KERNEL32/MSVCRT libraries and the supplied libredwg DLL, as inspected from the PE
import tables; optional iconv/PCRE binaries from the upstream ZIP are not shipped.
Linux links its system libc/libm; no host glibc binary is redistributed.

Upstream: https://www.gnu.org/software/libredwg/
Release: https://github.com/LibreDWG/libredwg/releases/tag/0.14

ODA File Converter is not bundled, downloaded, or installed. Optional existing
DWG export via ODA remains subject to ODA's own terms and is not covered by the
PY.cad license. The bundled LibreDWG support added here is for opening DWG only.
