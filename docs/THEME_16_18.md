# Theme colors — 16.18

Type **THEME** (or **OPTIONS**) and press Enter. Open **Appearance**.

The Dark preset uses neutral dark grey surfaces with lighter grey gradients in
the ribbon, menu strip and buttons. Model space and 3D space defaults are also
lighter. Light and Midnight presets remain available.

## Pick a color

Choose a color group or search (for example, "font", "ribbon" or "command").
Click a hex color swatch to open the color picker; its HTML field accepts an
exact #RRGGBB value. The small preview shows label, button and input fonts.
**Apply** saves without closing; **OK** saves and closes. **Cancel** discards
edits since the last Apply. Color swatches use automatically contrasting hex
labels so their values remain readable while editing.

Available groups cover drawing-space backgrounds and drafting grid, general
fonts/surfaces/states, ribbon gradients and captions, active/inactive tabs,
menus/status/tooltips, panels/tables/headers, inputs/placeholders/buttons,
scrollbars, command history/prompts/shortcut links, cursor input/measurements,
navigation faces and fonts, semantic icon pigments, selection/grips/snaps,
preview strokes, paper borders and 2D/3D axes and navigation guides.

Font colors have separate controls for their contexts. Changing the main font
color does not replace an explicitly selected button, menu or input font color.
Use the group controls or search "font" to customize those as well. Settings
also apply to Qt dialogs opened after the theme was saved.

## Reset

- **Reset** beside a color restores that color to the selected preset's default.
- **Reset all colors** restores all appearance colors, including drawing-space
  defaults, while keeping the selected theme preset. Apply or OK saves the reset;
  Cancel discards an unapplied reset. Drafting/snaps, graphics mode and menu-bar
  visibility are not reset by this button.
- Preset-derived colors follow the theme selector; explicitly chosen colors
  remain overrides until reset. New saves mark the palette revision so a deliberate
  choice of an older dark background is respected.

On upgrade, colors equal to the former untouched Dark stock background/grid/
accent defaults are updated to the lighter defaults. Other custom colors are
retained. If a legacy setup used exactly the old stock color intentionally,
choose that color again and Apply to retain it explicitly.

## Scope

Appearance preferences are separate from drawings: entity/layer colors, rich
text content, hatch pigments, plot output and the approved logo are preserved.
Layer names use readable theme text with a small drawing-color swatch alongside.
Color swatches displaying drawing data retain their actual pigment. Native OS
window frames, system cursors, native file/print dialogs and the separate native
installer use OS presentation; application theme settings do not recolor them.
The exported shared-view HTML is a separate document and keeps its own styling.

The default, custom and reset UI states were rendered and visually checked using
Qt offscreen rendering. See VALIDATION_16_18.txt for regression and platform limits.
