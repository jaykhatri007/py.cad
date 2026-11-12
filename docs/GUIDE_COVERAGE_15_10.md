# Supplied menu guide → PyCAD 15.10

Source: the user's one-page [AutoCAD Menu & Interface Guide](autocad_menu_guide.pdf).
Its named workflows now have working entry points in this build. This overview
does not specify the full implementation of each AutoCAD feature. The scope
column records what PyCAD actually provides; it is not a claim of AutoCAD parity.

| Guide row | PyCAD entry points | Result and scope |
| --- | --- | --- |
| Enable classic menus | `MENUBAR`, then `1`; `0` hides menus | Added. Saved preference; Quick Access File remains available when menus are hidden. |
| File / Application: New, Open, Save, Export, Plot, Purge | File's category and action panels; Ctrl+N/O/S/P; `PURGE` | Existing native file, DXF, optional DWG converter, PDF and solid-export paths retained. Compact two-column panel added. Purge now removes unused local blocks, layers, dimension/text/multileader styles with Undo. Unsupported export formats remain visibly disabled. |
| Edit: Undo, Redo, Cut, Copy, Paste, Find | Edit menu; Ctrl+Z/Y/X/C/V/F; `COPYCLIP`, `CUTCLIP`, `PASTECLIP`, `FIND` | Native clipboard and Find/Replace added. Paste supports selected 2D entities, blocks, style/layer dependencies and supported internal links/constraints; fresh IDs and physical unit conversion. Find searches model TEXT/MLEADER annotations. |
| View: Zoom, Pan, Orbit, Visual Styles, Viewports | View menu; `ZOOMEXTENTS`, `ZOOMWINDOW`, `PAN`, `3DORBIT`, `VPORTS`; View/3D ribbon | Existing navigation and embedded views retained; classic View menu now exposes Pan, Window Zoom, Viewports and Visual Styles. Saved extrusions support software wireframe/shaded/X-ray views. Conceptual/Realistic use approximate styles, without a photorealistic renderer. |
| Insert: Block, Xref, Raster Image | Insert menu; `BLOCK`, `INSERT`, `XREF`, `IMAGEATTACH` | Block definitions/references, linked DXF references and embedded image underlays. PDF attachment also remains available. Linked DWG Xrefs remain planned. |
| Format: Layer Manager, Text/Dimension Styles, Units | Format menu; `LAYER`, `STYLE`, `DIMSTYLE`, `UNITS` | Compact nine-column layer manager retained with all controls. Named text styles added: font, bold, italic, width factor, oblique and default new-text height. Existing dimension styles and explicit physical unit conversion retained. |
| Tools: Properties, Tool Palettes, Options, OSNAP | Tools menu; `PROPERTIES`, `TOOLPALETTES`, `OPTIONS`, `OSNAP` | Options/theme and snap configuration added. Properties now edits single TEXT content/style/height/rotation. Existing searchable tool palettes retain honest availability labels. |
| Draw: Line, Polyline, Circle, Arc, Rectangle, Hatch | Draw menu; `LINE`, `PLINE`, `CIRCLE`, `ARC`, `RECTANGLE`, `HATCH` | Existing editable 2D geometry retained. Hatch provides solid or parallel-line fill and supported source links, without the complete AutoCAD pattern library. |
| Dimension: Linear, Aligned, Radius, Leader, Dimension Style | Dimension menu; `DIMHORIZONTAL`, `DIMVERTICAL`, `DIMALIGNED`, `DIMRADIUS`, `LEADER`, `MLEADER`, `DIMSTYLE` | Existing dimensions retained; `DIMLINEAR` aliases horizontal dimensioning. Classic menu now includes Leader and Multileader. Static LEADER blocks and persistent plain-text MLEADER annotations are both available. |
| Modify: Move, Copy, Rotate, Scale, Trim, Extend, Fillet | Modify menu; commands with the same names | Existing 2D operations retained. `COPY` duplicates model geometry; `COPYCLIP` is clipboard copy. These operations do not provide solid-model editing. |
| Parametric: Coincident, Parallel, Perpendicular, Tangent | Parametric menu/ribbon; `GCCOINCIDENT`, `GCPARALLEL`, `GCPERPENDICULAR`, `GCTANGENT` | Persistent tangency added for LINE/CIRCLE and CIRCLE/CIRCLE pairs; existing sketch relations retained. Initial placement chooses line side or external/internal circle tangency. Arc segments, spline tangency and general solid constraints are outside this solver. |
| Home tab: common Draw / Modify / Layers / Annotate | Home ribbon, now including Clipboard | Existing grouped/compact ribbon retained. Cut, Copy, Paste and Find added. Individual tools remain searchable through Tool Palettes. |
| Annotate tab: text formatting / dimensions / leaders / tables | Annotate ribbon; `STYLE`, `TEXTEDIT`, dimension and multileader commands, `TABLE`, `TABLESTYLE` | Whole-object named text formatting and content editing added. Native multiline text remains plain text; no mixed formatting runs, fields, columns or automatic wrapping. Tables remain editable line/text blocks, without formulas or linked cell semantics. |
| Output tab: plot configurations / print settings / PDF | Output ribbon; `PAGESETUP`, `PLOTPREVIEW`, `PLOT`, `BATCHPLOT`, `EXPORTPDF` | Existing vector PDF plotting, layout size/orientation, plot preview and batch-sheet ZIP retained. There is no Autodesk PC3/CTB/STB configuration engine or direct physical-printer driver. |
| Collaborate tab: shared views / cloud management / drawing comparison | New Collaborate ribbon/menu; `SHAREDVIEWS`, `CLOUD`, `COMPARE` | Added: self-contained read-only 2D HTML/SVG snapshots, configured WebDAV listing/upload/download, and native/DXF comparison with overlay/report. Cloud requires the user's server; there is no included Autodesk/cloud account or live multi-user editing. Comparison requires matching units and reports tables/layouts/constraints/underlays/solids separately. |

Additional requested changes: saved Dark/Light/Midnight themes; independent model,
paper-sheet, 3D, grid and accent colors; bounded File category/action panels;
compact layer property dialog with New/Rename/Delete/Current/Isolate/Show all.

The full ribbon catalog contains **168 commands: 69 available, 76 limited and
23 planned**, across eight tabs and 31 panels. The 23 planned entries originate
in the earlier spreadsheet and remain disabled. See
[the full command coverage](RIBBON_COVERAGE_15_10.md) for their exact status.

Technical references used for the new interoperability paths:
[ezdxf text-style documentation](https://ezdxf.readthedocs.io/en/stable/tables/style_table_entry.html)
and [WebDAV RFC 4918](https://www.rfc-editor.org/rfc/rfc4918.html).
