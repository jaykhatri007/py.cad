# Command options — 16.16

Start a command with its name or alias, then press Enter or Space. A compact row
above the command line shows its current choices. Shortcut letters are highlighted
and underlined. Type a shortcut and press Enter/Space, or click its label. Grey
choices are unavailable until the command has enough input. Esc cancels.

- **L → Enter** starts Line. Pick or type points, **U → Enter** undoes the last
  segment, and **C → Enter** closes a chain with at least three points. Enter
  finishes. Undo does not remove unrelated geometry.
- **Z → Enter** starts Zoom without changing the view. Choose **W** Window,
  **S** Selected, **E** Extents, **A** All, **P** Previous, **I** In, **O** Out,
  or **R** Realtime. Each choice is followed by Enter/Space.
- Window accepts two clicked or typed corners. Selected uses the current
  selection, or lets you pick entities and press Enter. Previous restores the
  preceding view in the current drawing and space; it is not saved to disk.
- Zoom also accepts a positive numeric factor such as **2x**. All includes the
  drawing origin as well as visible drawing content. Realtime uses mouse drag;
  Esc leaves navigation. Three-dimensional views offer supported camera choices;
  Window, Selected and Realtime are currently drafting-view choices.
- Polyline/Spline show vertex Undo, Close and Finish. Hatch exposes Settings;
  Mirror shows Yes/No when asking about the source. Trim/Extend, dimensions,
  driving constraints, Area, Copy and menu visibility expose their supported
  context choices. Text and block names remain literal input.

The row updates as the tool progresses and disappears when idle. It can scroll
horizontally on smaller windows. The choices use the same handlers as typed
commands and do not imply support for every AutoCAD command keyword.
