# PyCAD 16.2 — building, quantities and drafting chat

The complete source build adds all nine building features discussed, drawing-linked
BOQ and interactive drafting chat. Existing drafting tools, independent drawing
files, compact Layers/File controls and OPTIONS theme/space color selectors remain.

![Actual two-storey model workspace](model-v16.2.png)

## Start or update

Extract **PyCAD-v15-Full.zip**, open its **PyCAD-v15** folder and run the existing
launcher. On Ubuntu use `bash setup_ubuntu.sh`, then `bash start.sh`. On Windows
run `start_windows.bat`. The folder name stays PyCAD-v15; Help/About shows 16.2.0.
The full ZIP includes all source, launchers, dependencies, tests, examples and docs.
It is not a prebuilt executable installer.

For an existing **16.1.0** installation, close PyCAD and back up the folder and
native drawings. Extract **PyCAD-Update-v16.1-to-v16.2.zip** into the folder
containing `main.py`, replacing the complete files. Do not use this patch on an
older build; use the full ZIP. Native schema 12 reads schemas 1–11. Keep backups
for use in earlier PyCAD versions, which cannot read new schema-12 saves.

Core 2D drafting, building plans, BOQ and offline chat use `requirements.txt`.
Live 3D and building sections/elevations need the optional CadQuery kernel:

```bash
python -m pip install -r requirements-3d.txt
```

IFC export additionally needs:

```bash
python -m pip install -r requirements-bim.txt
```

Use the **same Python interpreter as the launcher**, including its virtual
environment. These dependencies need compatible wheels for that Python and OS.
QA used Python 3.12.14 on Ubuntu 24.04, with CadQuery 2.7.0 and IfcOpenShell 0.9.0.
The Ubuntu core launcher retains its existing 26.04/Python 3.14 setup target;
optional kernel support on that interpreter was not exercised. Windows, native
Ubuntu 26.04, GPU/printer output and a production AI provider were not exercised.
Run `python scripts/check_environment.py --gui` in your launching environment.

## The nine building features

Open **Tools → Building**, or enter these commands in the command line. The
ribbon puts them in existing dropdowns, keeping eight tabs and 31 panels.

| Feature | Command | Use |
|---|---|---|
| Levels/storeys | `LEVELS` | Add a level; edit elevation, floor height and visibility; choose current level; assign selected objects. |
| Slabs and ceilings | `SLAB`, `CEILING`, `SLABHOLE` | Select a closed straight-edge boundary. Set thickness, height above level and material. Select one slab/ceiling plus an inner closed boundary to add a hole. |
| Roofs | `ROOF` | Select an axis-aligned rectangle. Choose Flat, Shed, Gable or Hip; set slope, overhang, thickness and elevation. Rotate/place the resulting object normally. |
| Stairs and rails | `STAIR` | Choose Straight/L/U layout, width, tread, total rise, step count, landing and rail height; turn rails on/off. |
| Automatic rooms | `AUTOROOM` | Detect enclosed spaces on the current level from joined straight walls. Linked boundaries and areas follow compatible wall edits. |
| Building views | `BUILD3D`, `BUILDVIEW` | Build real wall/building solids, then choose source models for a whole-building Front/Top/Right elevation or X/Y/Z section. Dashed hidden edges and section hatching are optional. |
| Visual materials | `MATERIALS` | Save/assign surface color, opacity, pattern or embedded image; inspect the preview and actual shaded model. |
| Quantity takeoff/costs | `BOQ`, `QUANTITYTAG` | Measure native building objects or tagged imported geometry; enter rates/allowance; select source objects; export CSV/JSON. |
| BIM exchange | `IFCEXPORT` | Export IFC4 typed objects, storeys, opening relationships, material names and source/quantity properties. |

`BUILDING` opens the small launcher for these tools. Edit created objects in the
existing **Properties** dock. Model browser → **Edit source object** selects the
native source. Committed source edits update plans, cached models and linked
views together; Undo restores the edit and cached results.

Levels keep different-storey wall joins separate. Openings follow their host's
level. Level/layer visibility affects drafting and model display. BOQ and IFC
include all levels by default, including hidden ones; BOQ can filter one level.
Generated views retain the chosen source list and placement. Add new objects to
a newly created view if they were not part of an existing view's source list.

![Compact storey manager](levels-v16.2.png)

## BOQ from a drawing

For native walls, openings, rooms and building objects, open **BOQ** directly.
It calculates current quantities and deducts hosted wall openings and defined
slab/ceiling holes. Rows retain source IDs; **Select sources** returns to Model
space and selects editable sources. Recalculate after edits or Undo. Export
CSV for spreadsheets or detailed JSON for traceable item/summary data.

For plain DXF/imported geometry, assign physical drawing units with `UNITS`.
Select geometry and run **QUANTITYTAG** to provide the item description,
material, measurement and factor. Length supports lines/polylines/circles;
area/volume require closed polylines or circles. Volume factor is thickness in
**metres**. Count measures selected objects. Unclassified objects are reported;
annotations do not automatically become building items.

| Item | Measurement basis |
|---|---|
| Wall masonry | Current linked net solid volume where available; otherwise joined footprint × height less hosted openings. |
| Wall finish | Two centre-line faces minus opening areas. Reveals/end faces are excluded. |
| Door/window | One count per live hosted opening, grouped by identifier. |
| Room finish | Current enclosed floor area. A stale automatic room reports its last valid boundary. |
| Slab/ceiling | Net area after holes; material volume uses vertical thickness. |
| Roof covering | Sloped surface area including overhang. |
| Stairs/railing | Solid-step prism volume; flight rail centre lines plus end posts. |
| Tagged geometry | User-defined Length/Area/Volume/Count and factor. |

Quantities export in metres, square metres, cubic metres or counts. Enter your
currency and project rates in **BOQ → Apply rates**. Blank rates stay unpriced;
the displayed **priced subtotal** covers priced items only. A global allowance
adjusts all quantities, including counts, while exports keep both net and adjusted
quantities. Taxes, reinforcement, assemblies, labor and regional prices are not
inferred. The example deliberately has blank rates. Native edits do not infer
measurement categories from a raster scan, PDF image or arbitrary linework.

![Compact BOQ with editable rates and source selection](boq-v16.2.png)

## Interactive drafting chat

Enter `DRAFTCHAT` or use **Tools → Automation → Drafting chat**. It opens a
330-pixel dock tab beside Properties/Layers. It supports drawing instructions,
selected-object edits, BOQ questions and a recent conversation for each open
file during this application session.

**Offline commands** work immediately, without an account or model. Examples:

```text
room 6m x 4m at 0,0
wall from 0,0 to 6000,0 width 200 height 3000
slab from selection thickness 150
roof from selection type Gable slope 25
stairs 18 steps height 3300 layout L
set selected thickness to 200
apply Timber to selection
detect rooms
build 3d
show BOQ
undo
```

Select objects first for selection-based instructions. Explicit mm/cm/m/in/ft
lengths convert into drawing units; bare coordinates use current drawing units.
Separate drafting commands with semicolons. Send a BOQ question separately after
applying drawing changes. `help` lists examples. Offline mode is a bounded command
parser; it does not understand every natural-language instruction.

**AI provider** accepts broader conversational instructions through your own
compatible chat-completions service or local model. In **Settings**, enter the
complete endpoint, model name and optional session API key. A local compatible
endpoint example is `http://localhost:11434/v1/chat/completions`; a remote
endpoint must use HTTPS. The service must return the structured JSON actions
requested by PyCAD. No model weights, provider account, credit or hosted AI is
bundled. Actual output quality and supported models depend on your service.

AI mode sends your instruction, recent chat, bounded object/quantity summaries
and selected geometry to the configured endpoint. The key stays in application
memory for this session; it is not saved in preferences, drawings or exports.
Endpoint/model settings persist. Chat history is session-only and separate from
the saved drawing. Network requests run in the background with a timeout.

Every drawing response is validated and rehearsed on a copy first. **Preview /
Apply** opens the review of supported actions; **Apply** commits one Undo step.
Cancel leaves the drawing untouched. A response becomes invalid if the active
drawing changes while it is pending. Read-only BOQ answers do not edit geometry.
The supported action set creates walls/openings/building objects, manages levels,
assigns materials, edits listed properties and rates, detects rooms and builds
models, alongside the existing bounded 2D actions. It does not execute arbitrary
Python, shell commands or unsolicited file changes. Prices are user supplied.

![Actual drafting chat, BOQ answer and pending reviewed edit](chat-v16.2.png)

## Materials, exchange and supported boundaries

Material images are embedded in native drawings (up to 1 MiB and 2048 × 2048).
Colors/opacity/patterns/images appear in the software model view. This is a
simple surface display, with screen-space repeating images; there is no UV
unwrapping, physically based renderer or photorealistic lighting.

![Small materials manager](materials-v16.2.png)

IFC exports typed walls, slabs, ceilings, roofs, stairs, doors/windows and spaces
with storey placements in metres. It includes actual tessellated geometry,
opening void/fill relationships, material names and PyCAD source/quantity
properties. Generic drafting entities are not inferred as BIM elements. This is
IFC4 **export**, not IFC round-trip editing, layered construction assemblies or
certification against every downstream BIM viewer.

Roof types require a rectangular source. They do not trim/extend walls to slopes,
add rafters/gutters or perform drainage/structural design. Roof material thickness
is vertical. Stair solids use full-height step prisms and simple flight rails/end
posts; they are not waist-slab, reinforcement, accessibility or code calculations.
Slab/ceiling holes must be contained and nonoverlapping. General curved walls,
complex building topology and construction detailing remain outside this scope.

Automatic rooms use an interior seed to identify an enclosure. Compatible wall
resizing updates it; opening an enclosure, removing walls, moving it away from the
seed, or ambiguous split/merge can mark it stale. Inspect that warning and
recreate the room as needed. Doors/windows do not break room enclosure detection.
Cached models/views display without the kernel if unchanged. Changed sources
need the kernel for regeneration; stale linked solids/affected views are blocked
from relevant export. Last valid geometry remains available for inspection.

## Included example and validation

Open **examples/v16_2_building.pycad**: two levels, nine walls, five hosted
openings, three linked rooms, five building objects, fourteen saved models,
two live building views and two physical-scale sheets. The staircase is placed
outside the footprint to make its layout visible. Its generator, BOQ CSV/JSON,
IFC4 and two-page PDF are included. The Ground sheet uses viewport overrides to
hide upper-level geometry. Older examples and guides remain in the ZIP.

See **docs/VALIDATION_16_2.txt** for the Linux/Qt tests and fresh-package checks,
and **docs/RIBBON_COVERAGE_16_2.md** for the actual 205-command catalog and remaining
limited/planned capabilities. Full AutoCAD/BIM parity is not claimed.

![Compact drafting and chat at 960 × 640](small-window-v16.2.png)
