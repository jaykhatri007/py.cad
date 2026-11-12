# PyCAD 16.4 — logo, license and setup

Open the setup for your OS or extract the full ZIP and use the source launchers.
If replacing 16.3, run the new setup: it prepares a separate release and only
selects it after checks, keeping your drawings and prior release. First setup
needs internet for the managed runtime/dependencies. OS security/admin prompts
still apply. Installers are unsigned.

| Platform | Setup |
| --- | --- |
| Desktop glibc Linux x64, glibc 2.34+ | PyCAD-Setup-16.4.0-Linux-x64.run |
| Windows 10/11, Intel/AMD x64 | PyCAD-Setup-16.4.0-Windows-x64.exe |
| macOS 13+, Intel or Apple Silicon | Extract PyCAD-Setup-16.4.0-macOS-Universal.zip and open PyCAD Setup.app |

Linux may require enabling **Allow executing file as program** in file
properties. If needed, open a terminal in the download folder and run
`chmod +x PyCAD-Setup-16.4.0-Linux-x64.run`, then open it. Full Linux ARM64 and
Windows ARM64 are not qualified. Windows/macOS files are cross-built and their
native execution has not been validated in this Linux environment.

## Logo

The approved full logo is visible in quick access and About. The symbol appears
in the application/window icon and installed shortcuts. macOS bundles contain
ICNS artwork; Windows setup has embedded ICO resources. The artwork is included
under assets, along with the unmodified approved master and icon export inputs.
The compact toolbar and existing workspace themes are retained.

## License and legal material

Open **Help → Licenses and Legal**, or **Help → About PyCAD → Licenses and Legal**.
Choose a document from the drop-down. These documents work offline; clicking
upstream links opens your browser. The setup's **Licenses and Legal** link opens
its embedded legal material while setup is running. Source copies are in
LICENSE, COPYRIGHT, THIRD_PARTY_NOTICES.md, legal and LICENSES.

The application is GPLv3-only. You may use it for commercial drafting; your
drawings do not become GPL just because you used the program. Redistribution
of the program involves source and notice obligations. See legal/DISTRIBUTION.md.
Third-party libraries/tools keep their own terms. See legal/RESEARCH.md for the
review scope and publication checks, including contributed-code authority,
trademark clearance, exact-source hosting and jurisdiction-specific review.

## Inspect the source without installing

Advanced command-line usage: `PyCAD-Setup --extract-source NEW_DIRECTORY`.
Use the actual setup executable's filename; on Linux the .run wrapper accepts
the same option. The destination must not already exist, preventing accidental
overwrites. The embedded archive contains application and installer source,
logo inputs, license files, scripts and requirements. See legal/DISTRIBUTION.md
for rebuild details. A complete independent source ZIP is also provided.

## Installed dependency notices

The installer records actual Python distribution versions and copies available
notice files to `runtime-legal` inside its selected release directory. Its log
shows the export path. The project's LICENSES/reference-linux folder contains
the review snapshot, not a claim to list all native components on every OS.
Retain the actual inventory when redistributing a runtime bundle.

## Existing drawing features

The drawing schema and editing/BOQ/chat functionality remain unchanged. See the
16.2 feature guide and 16.3 setup guide for existing workflows. Optional AI
services send the requested instruction/context to the user-configured endpoint;
read legal/PRIVACY.md before sending client data.
