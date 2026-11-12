# License review and publication status

Reviewed 18 October 2026 for PyCAD 16.4.0. This is a technical license review and
documentation package, not a legal opinion or certification for all countries.

## Reviewed evidence

1. Riverbank's official PyQt page and license FAQ confirm GPLv3/commercial
   licensing and that PyQt is not LGPL. Installed PyQt6 6.11.0 metadata and its
   retained license specify GPL-3.0-only. This determines the selected GPLv3-only
   license for the combined PyCAD distribution.
   https://www.riverbankcomputing.com/software/pyqt/
   https://www.riverbankcomputing.com/commercial/license-faq
2. GNU GPLv3 text, sections 0, 2, 4–6, 10 and 15–17, and the FSF distribution
   guidance support the run/modify/distribute rights, corresponding-source
   requirements and warranty notice. Full unmodified text is in LICENSE.
   https://www.gnu.org/licenses/gpl-3.0.html
   https://www.gnu.org/licenses/quick-guide-gplv3.en.html
   https://www.gnu.org/licenses/gpl-faq.en.html
3. Qt explains the additional LGPL requirements, including notices, source and
   replacement/relinking concerns. PyQt6-Qt6 6.11.2's installed notice is retained.
   https://www.qt.io/development/open-source-lgpl-obligations
4. ezdxf's installed MIT notice and official documentation, CadQuery's installed
   Apache-2.0 notice, NumPy's full wheel notice, the OCP wrapper's installed
   Apache-2.0 license, and the Open CASCADE release's LGPL2.1 exception were
   inspected/retained. The wrapper license is not a replacement for OCCT's license.
   https://ezdxf.readthedocs.io/en/stable/introduction.html
   https://github.com/CadQuery/cadquery
   https://github.com/Open-Cascade-SAS/OCCT/tree/V7_8_1
5. IfcOpenShell's official introduction and release source identify LGPL-3.0-or-later
   for the relevant libraries. The installed 0.9.0 wheel has no standalone notice
   in its RECORD, so upstream GPL/LGPL texts and the release source header were
   fetched separately and retained with their URLs and hashes.
   https://docs.ifcopenshell.org/introduction.html
   https://github.com/IfcOpenShell/IfcOpenShell/tree/v0.9.0
6. uv's MIT/Apache dual license, CPython's own license and the compiled Go
   runtime's BSD notice are retained separately. They are not relicensed as PyCAD.
   https://docs.astral.sh/uv/reference/policies/license/
   https://github.com/python/cpython/blob/v3.12.12/LICENSE
   https://go.dev/LICENSE
7. The 48-distribution Linux reference inventory retains package metadata and
   143 installed notice-related files. Additional source/license files are
   recorded in LICENSES/upstream and LICENSES/SOURCE_INDEX.json. Actual installed
   inventories are generated per machine. Dependency metadata alone is not proof
   of complete bundled-native compliance.

## What is incorporated

- GPLv3-only project declaration and full text, original-material copyright
  scope, third-party attributions, GPL/LGPL/Apache texts and exact notice files.
- Offline legal pages in the application and setup, source extraction from
  native setup, editable rebuild scripts, dependency/source inventory and an
  automatic actual-installation notice inventory.
- Local-data/AI privacy explanation, output ownership explanation, professional
  use guidance, warranty statement and brand/non-affiliation notice.

## Remaining checks for public distribution

The archive originally contained no project license. This release adds GPLv3-only
under the owner's request to license the project; it does not prove the rights
history of every earlier contribution. Confirm authority to license imported or
third-party contributions. No attribution was intentionally removed.

No comprehensive trademark/patent search, dependency vulnerability audit,
independent native-wheel source reconstruction, or country-by-country legal
review was performed. The inventory covers Python distributions and retained
notices; it does not certify every compiled subcomponent. Build/notice changes
were checked on Linux; Windows/macOS native execution remains unqualified in
this environment. Verify those packages and their actual native inventories.

The Windows runtime and optional ODA converter are external proprietary
components. The development-only PyMuPDF dependency is AGPL/commercial, not a
runtime dependency and not bundled; optional PyInstaller builds have their own
GPL-with-bootloader-exception terms. Do not describe every possible external
tool or service as GPL or fully open-source merely because PyCAD is open-source.

Before a public launch, the publisher should arrange exact-source availability,
verify contributed-code authority and native dependency notices, publish real
operator/contact details, and obtain jurisdiction-specific review for the
intended distribution/hosted-service model. Applicable privacy, consumer,
export and professional-practice laws remain separate from the software license.
For example, GDPR applicability depends on the processing and territorial scope
described in Regulation (EU) 2016/679:
https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng .

No paid global software license or registration is represented as necessary or
obtained. This package cannot guarantee lawful use in every jurisdiction.
