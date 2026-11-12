# PY.cad 16.29 — drawing productivity guide

Open **Workflow → Drawingtools**, or type `DRAWINGTOOLS`. Eight compact pages extend the existing drafting, professional and workflow tools.

| Command | Addition |
| --- | --- |
| HATCHAREAS | Selected closed boundaries, individual area removal, separate or combined fills |
| PDFIMPORT | Editable PDF vector paths, scale calibration, background parsing and review |
| DRAWTABLE | Safe formula cells, linked CSV reload, live BOQ and block-count schedules |
| STANDARDSCHECK | Office layer/color/lineweight/text/dimension standards checker |
| SURVEY | Local affine grids, WGS84 UTM, point CSV, labels, bearings and distances |
| BLOCKPARAMETERS | Named width/height and rotation states, automatic regeneration |
| BOQOVERLAY | Measured/priced, measured/unpriced and unmeasured display colors |
| AIEXPLAIN | Geometry, quantities and command-failure explanations grounded in drawing data |

## Hatch areas

Pick-point flow: `H` → settings → click each enclosed region → Enter. `U` removes the last pick. `A` opens a staged-area list; select any entries and remove them, then Apply. Cancel preserves the queue. `C` combines areas; `Separate` restores independent fills. Esc discards previews. Combined hatches use existing even-odd loops, with Normal/Outer/Ignore island settings. Their outlines must not cross or touch. Combined fills store boundaries without associative links.

For explicit objects, select closed circles/polylines first and use HATCHAREAS. Remove unwanted outlines, choose combined/separate, then hatch settings. Nested outlines become islands. Separate fills retain available source links. The operation validates before modifying the drawing and uses one Undo.

## Vector PDF import

Choose one page, insertion X/Y and scale. Default scale converts PDF points (1/72 inch) into physical drawing units; calibrate unitless drawings explicitly. Alternatively supply a known drawing length and its corresponding PDF point length: their ratio sets scale. Set curve subdivisions and cleanup tolerance. The isolated parser can be cancelled; preview geometry and warnings before accepting. Adding uses one Undo; originals are unchanged.

Supported 2D paths become editable polylines. Cubic curves are approximated by the chosen segment count. Consecutive near-duplicate vertices, degenerate paths and duplicate paths are cleaned. Filled paths become outlines. Text, images and Form XObjects are skipped and reported. Clipping and dash/width/transparency styles are not faithfully reproduced. Use PDFATTACH for full visual appearance. This is vector linework import, not OCR or lossless PDF conversion.

## Drawing tables

Create a formula table, link UTF-8 CSV (optional BOM), or insert live BOQ/block schedules. Formulas support A1 references, arithmetic, bounded powers, SUM/MIN/MAX/AVERAGE and ranges: `=B2*C2`, `=SUM(D2:D10)`. Empty referenced cells count as zero. Circular references, nonnumeric arithmetic, outside references, arbitrary expressions and division by zero are rejected. Expressions are parsed without eval/exec.

Edit table cells to revise formulas. CSV reload is explicit and reviewable, never triggered by opening a drawing. Project packages include linked CSV sources. Live schedules regenerate after relevant drawing edits. Tables are ordinary line/text blocks for display and export. Native saving preserves formulas/links; DWG/DXF retains generated geometry, not native CAD TABLE semantics. Existing static TABLE placement remains available.

## Office standards

Capture a drawing standard; export its JSON, edit and reimport it. The fields are `layers` (allowed names, colors, lineweights), `text_height`, allowed `dimension_styles` and numeric `tolerance`. Checks include block-definition content and report source IDs when applicable. They are read-only; normal editing tools perform corrections. Reports export to JSON.

## Survey / georeferencing

Configure Local or WGS84 UTM, zone 1–60 and hemisphere. Origin Easting/Northing, rotation and scale are explicit. Scale is survey units per drawing unit: metres with mm geometry use 0.001. Changing settings changes interpretation and future import/labels; it does not move existing geometry.

CSV has no header: `ID,Easting,Northing[,Elevation]`; geographic CSV uses `ID,Longitude,Latitude[,Elevation]`. Choose label height and inspect the point/label preview before adding. Elevation remains labeled metadata; this is 2D drafting, not terrain modeling. Standard UTM latitude range −80..84 is enforced; hemisphere mismatch and points too far from the selected zone are rejected. There is no arbitrary EPSG, datum/geoid or cadastral transformation. Validate survey control independently.

Select POINT objects in from/to order for azimuth, quadrant bearing and distance. Distances use configured survey units (metres for UTM). Coordinate labels use the current coordinate settings.

## Named block parameters

Choose an ordinary local base and define a separate state. Set distinct width/height parameter names, base dimensions, target dimensions, rotation and X/Y thresholds. Coordinates beyond each threshold move by target minus base dimension. Straight lines, straight polylines, text and attribute positions follow this rule. Curved stretch content is rejected before modification; use Block Editor for it. Rotation without stretch can handle supported ordinary entities.

Apply a state to matching selected base/state instances. Parameter edits and base-definition edits regenerate the derived block and all its instances. IDs remain stable across unchanged refreshes. Undo/Redo and native save/reopen preserve the rules. These are shared explicit parameter states, not a general constraint solver or AutoCAD dynamic-block format.

## BOQ overlay and explanations

Green = measured / priced; amber = measured / unpriced; red = unmeasured. Selection takes priority. Colors refresh after edits and when toggled; saved colors and PDF plotting remain unchanged. Coverage reports identify missing measurements/rates. Invalid quantity adjustments produce an error rather than a misleading coverage result.

AIEXPLAIN provides deterministic offline explanations using actual geometry and BOQ rows: gross quantity, deduction, waste, final quantity and final × rate cost arithmetic. No network request occurs. Drafting chat accepts “explain selected” and “explain quantities”. Its existing optional AI provider mode receives the same selected evidence when you configure and choose it. An external model/service remains optional and user-configured. Explanations do not infer unknown design intent or independently verify/certify quantities.

Captured command-line and drawing-tool errors can be explained with relevant next checks. Geometry and quantity evidence, rather than an assumed reason, forms the explanation.

## Native format and platform scope

16.29 writes schema 15 and reads schemas 1–14. Keep original copies for older versions: 16.28 and earlier cannot read schema 15. Eligible clipboard transfers preserve table/parameter metadata and remap copied block names. Unit conversion preserves physical parameter/table dimensions and survey mapping. Standards and survey settings stay with the receiving document rather than arbitrary copied objects.

The full ZIP includes complete source, matching Windows/Linux/macOS setup packages, existing logo/license material, this guide and validation notes. Windows/macOS native installation and physical GPU behavior require platform testing; they are not claimed as verified in this Linux environment.
