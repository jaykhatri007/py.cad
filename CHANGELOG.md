# PY.cad changelog

## 16.45.0 — Office drafting

Open the **Office** ribbon tab, use the **Office Drafting** menu, or enter a command below.

| Command | Workflow |
|---|---|
| `OFFICEBLOCKS` | Select a shared folder, save a definition from the current drawing, and insert it into another drawing by point or coordinates. Search, use favorites and preview thumbnails. If a name already exists, choose the drawing's definition or import a renamed copy. Set drawing units before inserting between unitless and dimensioned drawings. |
| `PARAMETRICDOOR` | Enter the width in drawing units, opening angle, hinge side and swing, then place the hinge. Select an existing door and click **Edit door parameters…** in Properties. Each edit applies to that instance and can be undone. This creates a stand-alone 2D symbol; the existing hosted Door tool is separate. |
| `PDFREVIEW` | Import an annotated PDF page in Model or a paper layout. Align with origin, page width and rotation; adjust opacity. Numbered pins are amber when open and green when resolved. Select a row to read the comment or toggle its status. Flattened annotations are visible in the page image, but are not individually tracked. Review overlays are excluded from plots by default. |
| `PROJECTSHEETS` | Add layouts from saved native drawings. Set the issue revision, reorder sheets and save a portable project set. Publish a combined PDF; duplicate sheet numbers stop publishing. Publication applies the issue number and revision to the plotted title blocks without resaving source drawings. |
| `LINETYPEDESIGN` | Enter a style name, dash, gap, repeating text and text height. Preview the pattern and assign it to a layer, or save it and choose it later. ByLayer lines and curves pick up the layer style. The editable recipe and label pattern are retained in native drawings and PDF output; DXF/DWG exchange uses ordinary dashed lines. |

The installers share the same CAD build and use the existing Studio setup and uninstall flows. This release does not add Live 3D features. Drawings that use the new editable office data use native schema 18 and should be opened in PY.cad 16.45 or later.

## Earlier releases

- Improved large drawing rendering, layer controls, and interactive editing.
- Expanded 2D drafting, layouts, PDF output, and DXF/DWG workflows.
- Added architectural tools, quantity takeoffs, and optional 3D modeling.
- Improved desktop setup and removal workflows on supported platforms.

Individual release notes are retained in the full release archive.
