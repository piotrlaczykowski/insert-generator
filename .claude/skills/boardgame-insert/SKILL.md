---
name: boardgame-insert
description: Use when designing a 3D-printable board game box insert or organizer, adding a new game to the insert generator, turning a rulebook component list and caliper measurements into trays, or iterating on tray layout, STL/3MF export and previews.
---

# Board game insert

## Overview
Game data (`game.yaml`) + real measurements → tray layout → BIT/OpenSCAD models → STL/3MF + PNG.
The `insertgen` CLI does all geometry. Your job is the data, the measurement checklist and the conversation.

**Core rule: never invent a dimension.** Unknown = `null`. `insertgen build` refuses to build with nulls
and prints the checklist. Publisher/BGG/shop sizes are outer and approximate: they go under
`box.reference` (sanity check only), never into a field the geometry reads.

## Setup (the only repo-specific part)
| What | Where |
|---|---|
| Game data | `games/<slug>/game.yaml` (schema: `tools/insertgen/model.py`, example: `tests/fixtures/testgame/game.yaml`) |
| Rulebook PDF, photos | `games/<slug>/private/` (gitignored, never commit publisher material) |
| Printer + default design rules | `config/printer.yaml`; per-game overrides under `rules:` |
| Outputs | `games/<slug>/out/`: `<tray>.stl/.3mf`, `<tray>_{iso,top,front,right}.png`, `assembly_{iso,top}.png`, `report.md` |
| Commands | `uv run insertgen check <dir>`, `uv run insertgen build <dir> [--no-render]` |

Requires OpenSCAD nightly on PATH (or `OPENSCAD=/path`).

## Workflow
1. **Inventory.** Read the rulebook component list from `private/` (or ask the user). Draft `game.yaml`:
   every component with `kind` (cards / tokens / object) and `count`, all sizes `null`.
   Items lying on top of the insert (rulebook, score pad) go in `on_top`.
   Group components into `trays` by setup: what comes out together lies together.
   A nested list in `compartments` shares one well (same kind only).
   Show the inventory to the user and get it confirmed; editions differ.
2. **Measurement checklist.** Run `insertgen check`. Give the user the list in their language:
   mm, 0.1 precision, calipers. Card thickness comes from a stack (e.g. 50 cards pressed lightly), not one card.
   Box interior: X short side, Y long side, Z floor to the rim of the bottom part.
   Ask about sleeves. Then **stop and wait** for the numbers.
3. **Build.** Enter measurements, run `insertgen build`. Read `out/report.md`.
   Before the first full print, suggest `insertgen build <dir> --fit-test 5`: low rings in `out/fit/`
   with the real wells, so the user can check the clearance with real pieces for a few grams of filament.
   Pieces too tight or too loose → adjust `rules.clearance`, rebuild.
4. **Review with the user.** Show the PNGs (Read the image files) and the report: fill %, free space,
   warnings (stretched solid walls, bed size, BIT physical validation). Iterate on grouping, `orientation`
   (auto / flat / upright) and `rules`, rebuild. When accepted, point the user to the `.3mf` files.

## Quick reference
| Need | game.yaml |
|---|---|
| Cards stand on edge | component `orientation: upright` |
| Two decks in one well | `compartments: [[deck_a, deck_b]]` |
| Less plastic in a sparse box | `rules: {stretch: false}` |
| Thicker items on top | add them to `on_top` with measured `xyz` |

## Red flags: stop
| Thought | Reality |
|---|---|
| "Standard card size is 63x88, I'll use that" | Card sizes vary by game. Leave null, ask. |
| "BGG says 239 mm, close enough for the box" | Outer, approximate. `box.reference` only. |
| "I'll put a placeholder so the build runs" | The refusal is the feature. Give the checklist. |
| "User said 'about 5 cm'" | Ask for the caliper value at 0.1 mm. |
