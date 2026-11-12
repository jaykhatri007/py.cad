# PY.cad logo integration

The current 16.5 wordmark reads PY.cad. See assets/BRANDING.md for its exact
edit prompt and AI provenance. The symbol and native icon exports are unchanged.
The original PyCAD master below is historical provenance, not the current text.


The approved logo is `assets/pycad-logo.png`. Its application-symbol variant is
`assets/pycad-icon.png`, with native ICO and ICNS exports alongside it. The
original preview remains unchanged. The built-in image-generation tool was used
for both images; format/size exports use ImageMagick without redrawing them.
`assets/pycad.svg` is a retained legacy asset and is no longer used by startup.

The application presents the navy wordmark on a pale neutral backing so it
stays readable with Dark, Light and Midnight themes. The workspace label is
shorter to keep the quick-access bar compact. The About viewer uses the larger
approved wordmark; the setup uses the same master image. Shortcuts use the symbol.

## Final prompt for the icon variant

Use case: background-extraction / logo-brand. The input is the approved PyCAD
logo. Produce the square application icon asset using ONLY its geometric
teal-and-deep-navy architectural symbol from the LEFT side. Remove all wordmark
letters and empty wide margins. Preserve the exact approved symbol silhouette,
face colors, open inner corner, proportions, geometry, and orientation. Do not
redesign or add details. Center the isolated symbol on a square genuinely
transparent canvas with about 12 percent clear padding on all sides. Crisp
clean edges for a desktop app icon. No text, no background tile, no shadows,
no glow, no new shapes.

The original master design requested a geometric architectural CAD mark,
teal/cyan and navy palette, and exact `PyCAD` wordmark on transparency. See
legal/TRADEMARKS.md for the artwork's licensing/provenance scope.

To regenerate native format exports, install ImageMagick and run
`python packaging/export_icons.py`. This also generates the Windows COFF icon
resource used by the Go setup build. Then run `python installer/build.py`.
