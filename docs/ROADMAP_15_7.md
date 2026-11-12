# PyCAD roadmap after the Ubuntu migration

15.7 adds an Ubuntu setup/launch workflow, offline dependency reuse, diagnostic
and desktop checks, Applications integration and reference relinking. Native
schema 6 and the 15.6 CAD feature set are preserved. The Windows launcher remains.

| Priority | Next work | Acceptance gate |
| --- | --- | --- |
| User migration | Run the included check on the target Ubuntu computer; verify a real project, fonts, plot scale and reference paths | Open/save/reopen and sample PDF output match the source drawing; orbit works on the actual desktop |
| Platform release | Native Wayland, Ubuntu 26.04, DPI/multi-monitor and physical GPU testing; clean Windows rerun | Published platform/dependency matrix with reproducible smoke results |
| Distribution | Choose maintained packaging (.deb or AppImage) and appropriate licensing/distribution checks | Clean-machine install and upgrade, bundled Qt plugins, reliable uninstall and logs |
| Drafting | Two-line associative angular dimensions, richer annotation scales and grip editing | Native persistence, source edits, undo and explicit interchange fidelity |
| Sheets and printing | Per-layout plot settings, title blocks, batch plot review and printer integration | Measured plot scales, predictable lineweights and clipping |
| 3D and exchange | More solid editing, generated views and deeper supported format coverage | Valid geometry, recoverable edits, representative round-trip fixtures |

The detailed CAD expansion stages in ROADMAP_15_6.md still apply. No planned
command becomes enabled merely because the application now launches on Ubuntu.
