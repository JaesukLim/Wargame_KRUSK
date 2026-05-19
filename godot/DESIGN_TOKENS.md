# Godot UI Design Tokens

These tokens are encoded in `godot/scripts/Main.gd` as constants so the visual system is reproducible without a separate theme resource.

## Colors
- Background: near-black `Color(0.025, 0.030, 0.032)`
- Panel: dark green-black `Color(0.045, 0.055, 0.058, 0.97)`
- Panel dark: `Color(0.030, 0.037, 0.039, 0.98)`
- Lines: muted steel `Color(0.22, 0.27, 0.27)`
- RED force: `Color(0.86, 0.18, 0.14)`
- BLUE force: `Color(0.38, 0.60, 0.92)`
- Gold emphasis / WTA / timeline: `Color(0.94, 0.76, 0.25)`
- Green active / health: `Color(0.38, 0.74, 0.34)`

## Spacing and layout
- Base viewport: 1920x1080, with font scale clamped from 0.95 to 1.45 for FHD-to-4K readability.
- Exported release builds request fullscreen at startup; screenshot/smoke runs stay windowed.
- Outer margin: 10 px
- Header: 56 px
- Bottom operations bar: 170 px
- Panel gap: 8 px
- Left OOB: 17% viewport width, clamped 245-305 px; enemy summary and validation are pinned to the bottom so list rows cannot overlap them.
- Right stack: 31% viewport width, clamped 400-530 px

## Typography
- Main title: 19 px
- Panel title: 13-15 px
- Body text: 10-12 px
- Large combat ratio: 25 px

## Component states
- Buttons use dark fill; active buttons switch to green-tinted fill and green border.
- Unit selection uses gold halo + gold outline.
- Unit health bars use green fill and are clamped to unit symbol width.
- Text drawn through `_text(..., max_width)` is truncated with ellipsis to prevent panel overflow.

## Interaction states
- Header buttons: Reset, State, Full, 2D, and 3D all dispatch real actions.
- Map toolbar buttons set the active tool: Select, Move, Fire, LOS, WTA, Road, Rail, Elevation.
- Selected-unit buttons set queued intent: Move, Attack, Defend, Retreat.
- Command queue buttons append or clear selected-unit orders.
- Timeline Back loads the previous replay frame from `/state/replay`; Step advances the backend by 30 seconds.
- 3D mode draws the same backend units as perspective battlefield symbols rather than a static preview.
