# Selection and hatch workflow — 16.22

## Selection

In the Select tool in Model space:

- **Ctrl + left click** adds the hit object to the existing selection. Repeating Ctrl-click does not duplicate it or toggle it off.
- **Alt + left click** subtracts the hit object. It does not start a move or grip edit.
- When Ctrl and Alt are both held, Alt/subtraction takes priority.
- Clicking another unselected object without a modifier replaces the selection. Clicking an already selected object preserves the selection for dragging.
- Ctrl/Alt-click on empty space preserves the existing selection. Ordinary empty-space clicking clears it.
- Ctrl-drag on empty space adds a selection window/crossing selection; Alt-drag subtracts. The mode is captured when the drag starts, so releasing the modifier before releasing the mouse does not change it.

Logical group members are added/removed together, consistent with ordinary group selection. Hidden/locked objects remain excluded. Modifier clicks bypass grips and never start an object move. The same canvas/tool behavior applies inside the block editor. Paper-space viewport move/resize selection retains its existing behavior.

## Hatching

**H / HATCH → settings dialog → Pick area… → click an enclosed area or closed boundary → Enter to apply.**

The settings dialog opens first for the command line, Home ribbon, menu/right-click command and block editor. Choose a pattern, scale, angle, origin, colors, transparency, island behavior and other existing options. Accepting the dialog starts picking; it does not create a hatch. A previously selected closed boundary is not hatched automatically. The canvas shows a preview after the area/boundary is picked, and Enter confirms one undoable hatch operation.

Cancel in the opening dialog leaves the current tool, selection and drawing unchanged. Escape after accepting settings cancels picking/preview without creating a hatch. While picking, the existing Settings subcommand can revise the configuration. HATCHEDIT continues to edit existing hatch properties; it is separate from starting a new hatch.

The existing hatch pattern library, PAT imports, scale/island/gradient options, boundary engine, undo, drawing-quota removal and graphics configuration are retained. This change does not add new boundary-detection algorithms or support for previously unsupported DWG content.

## Validation

New interaction tests send real Qt mouse press/release events with Ctrl/Alt modifiers and cover additive/subtractive/repeated selection, blank clicks, grips, groups/locks and selection boxes. Hatch tests cover H, HATCH, HATCHSETTINGS, ribbon/direct entry, cancel, settings-before-pick ordering, preview/Enter/undo, and block-editor entry. Existing hatch clipping/graphics and command/selection regressions are also run. See VALIDATION_16_22.txt for exact counts. Native Windows/macOS execution and the user's drawing are unverified here.
