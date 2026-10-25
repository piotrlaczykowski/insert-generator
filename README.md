# insert-generator

Parametric, 3D-printable board game inserts. A game is described once in `games/<slug>/game.yaml`
(components from the rulebook + caliper measurements); the generator lays out the trays, writes a
[Boardgame Insert Toolkit](https://github.com/dppdppd/The-Boardgame-Insert-Toolkit) (BIT) `.scad`
file and renders STL/3MF plus PNG previews with OpenSCAD.

**No invented dimensions.** Anything not measured is `null`; the build refuses to run and prints a
measurement checklist instead. Publisher/BGG sizes are kept under `box.reference` for a sanity check
only and never feed the geometry.

## Setup

- [uv](https://docs.astral.sh/uv/) (Python 3.11+)
- OpenSCAD **nightly** (the 2021.01 release lacks the Manifold backend):
  `brew install --cask openscad@snapshot` on macOS, an AppImage from
  <https://files.openscad.org/snapshots/> on Linux. Or point `OPENSCAD` at the binary.

```sh
uv sync
uv run pytest
```

## Usage

```sh
uv run insertgen check games/tajniacy-hp     # what still needs measuring
uv run insertgen build games/tajniacy-hp     # layout, insert.scad, out/{*.stl,*.3mf,*.png,report.md}
uv run insertgen build games/tajniacy-hp --fit-test 5   # + out/fit/: 5 mm high rings to test the clearance
```

`insert.scad` is committed; `out/` is built locally and in CI (artifact `inserts`).
Export a single tray by hand with `openscad -D 'which="<tray id>"' -o tray.stl games/<slug>/insert.scad`.

## Layout

| Path | |
|---|---|
| `games/<slug>/game.yaml` | components, counts, measurements, tray grouping |
| `games/<slug>/private/` | rulebook PDF, photos (gitignored) |
| `config/printer.yaml` | Bambu Lab X2D bed sizes and default design rules (walls, floor, clearances) |
| `tools/insertgen/` | schema, checklist, sizing, solver, BIT writer, OpenSCAD runner |
| `vendor/bit/` | BIT v4.12.0, unmodified (see `NOTICE`) |
| `.claude/skills/boardgame-insert/` | Claude Code skill that walks through a new game |

How it works: each compartment is the measured piece plus clearance; card stacks taller than the
usable depth are split into side-by-side stacks or stood upright, whichever uses less area. Trays are
shelf-packed into the box interior (minus a margin), with extra height layers only when one layer is
not enough, then optionally stretched so they don't slide. The insert top sits below the box rim by
the thickness of whatever lies on top plus a lid clearance.

## Games

| Game | Status |
|---|---|
| Tajniacy Harry Potter | waiting for measurements |

## License

[CC BY-NC-SA 4.0](LICENSE), inherited from BIT, which this project builds on and redistributes.
Generated models are adaptations of BIT and fall under the same license.
