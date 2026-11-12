# Distribution and corresponding source

This is practical release guidance; the licenses themselves govern.

## What these packages contain

The native setup executables contain PY.cad's source payload, the Go installer,
approved logo assets, legal notices and a compiled Go standard-library runtime.
They download uv, CPython and Python dependency wheels separately on the target
computer. They do not contain a ready-to-run prebundled Qt/CadQuery environment.
Windows may additionally download Microsoft's runtime installer under its own
terms. OS desktop packages are obtained through the OS package manager.

`PY.cad-v16.5-Full.zip` is the complete project and rebuild package for this release.
The full ZIP root is `PY.cad`. Native setup retains the internal source payload
root `PyCAD-v15` for compatibility; the actual version is
16.5.0. The editable PY.cad and installer source, dependency requirements, icon
export script and setup build script are included. Native setup packages also
carry this application/installer source payload. An advanced user can extract
it without installing using `PY.cad-Setup --extract-source NEW_DIRECTORY`.
The installed application's directory contains the same source and legal files.

## Redistribution duties

- Keep the license text, copyright notices, attribution files and applicable
  third-party notices. Make the legal material readily available to recipients.
- Provide the complete corresponding source for the covered binaries you
  distribute, including modifications and the scripts needed to build/install
  them. If distributing online, place an equivalent source download and clear
  directions alongside every binary download; follow GPLv3 section 6.
- Mark your modifications and dates. Do not restrict recipients' GPL rights or
  impose a contradictory EULA, NDA, per-seat restriction, or ban on commercial
  use. The explanatory safety/privacy text is not an extra license restriction.
- If distributing a User Product, assess GPLv3's installation-information
  obligations. Do not add technical restrictions that defeat required rights.
- Keep MIT/BSD copyrights and disclaimers and Apache license/NOTICE material.
  Retain Qt, Open CASCADE, IfcOpenShell and other LGPL terms and exceptions.
  If repackaging LGPL libraries, review their source, replacement/relinking,
  modification and reverse-engineering rights. Static packaging needs special
  attention. Do not assume dynamic linking removes every obligation.
- A link to a moving upstream branch is not a substitute for the exact source
  and build/patch information needed for your own redistributed binaries.

## Dependency records and boundaries

`LICENSES/reference-linux/inventory.json` records the 48 Python distributions
installed in the release review environment, their exact versions, dependency
metadata, links and hashes of retained notice files. This is a reference
inventory, not a claim to be a complete cross-platform native SBOM. Native
libraries inside wheels, system libraries, and unrecorded upstream patches need
their own review. `LICENSES/SOURCE_INDEX.json` records upstream source routes.

After installation, setup runs `scripts/export_legal_inventory.py` using the
managed application interpreter and writes an actual platform inventory plus
retained notices in the selected release's `runtime-legal` directory. If this
inventory cannot be written, setup reports the failure before selecting the
new release. Keep that inventory with any redistributed runtime environment.
The source folder's reference inventory does not replace that platform record.

This update adds constraints for reviewed Linux dependency versions; requirements
still allow platform-specific dependencies. Update and review the inventory
whenever changing requirements, native wheels, runtimes or build tools.

## Rebuild

Use Python 3.12 and the requirements files. For native installers, install Go
1.27.3 (the toolchain used for this release), prepare the approved icon exports
with `python packaging/export_icons.py` if changing the PNG icon (ImageMagick is
needed for exports), then run `python installer/build.py --output setup-build`.
The build regenerates the embedded payload, legal page and native assets.
There are no third-party Go module dependencies. The Go runtime's BSD notice is
in `LICENSES/Go-LICENSE.txt`. Review Python/runtime source references and the
upstream licenses when redistributing a runtime rather than this bootstrapper.

Installers are unsigned. Signing/notarization is a publisher release step and
is separate from the open-source license. This build does not bypass OS prompts.

## Before a public international release

The distributor must confirm authority to license all original contributions,
publish a durable exact-source route for every binary release, review the
actual dependency/native inventory on each supported platform, and provide
the real publisher/support/security/privacy contact through its distribution
channel. The individual publisher is Jay Kundanlal Khatri, India, as reported. No company
identity, registration number, contact address, trademark registration or
government approval has been invented. See legal/PUBLISHER.md.
Review applicable export/sanctions, consumer, privacy and professional-practice
rules for the markets and deployment model involved. These remain publisher
responsibilities; this package is not a legal-compliance certification.
