import re
import shutil
from itertools import combinations
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from insertgen import render, slicer
from insertgen.cli import PRINTER, app
from insertgen.model import Game, effective_rules, load_game, load_printer
from insertgen.sizing import usable_height
from insertgen.solver import solve

REPO = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "testgame"


@pytest.fixture
def raw() -> dict:
    return yaml.safe_load((FIXTURE / "game.yaml").read_text())


def _solve(raw: dict):
    game = Game.model_validate(raw)
    printer = load_printer(PRINTER)
    rules = effective_rules(printer, game)
    return game, rules, solve(game, rules, printer)


@pytest.mark.parametrize("stretch", [True, False])
def test_layout_fits_box_without_overlap(raw, stretch):
    raw["rules"] = {"stretch": stretch}
    game, rules, layout = _solve(raw)
    W, D = layout.area
    assert W == game.box.inner_xyz[0] - rules.box_margin
    for p in layout.placements:
        assert p.x >= 0 and p.y >= 0 and p.x + p.w <= W + 1e-6 and p.y + p.d <= D + 1e-6
        assert p.h == pytest.approx(usable_height(game, rules))
        X, Y, _ = p.size
        row = sum(w.x for w in p.tray.wells) + rules.divider * (len(p.tray.wells) - 1)
        assert (X - row) / 2 >= rules.wall - 1e-6
        assert all((Y - w.y) / 2 >= rules.wall - 1e-6 for w in p.tray.wells)
    for a, b in combinations(layout.placements, 2):
        assert a.x + a.w <= b.x + 1e-6 or b.x + b.w <= a.x + 1e-6 or a.y + a.d <= b.y + 1e-6 or b.y + b.d <= a.y + 1e-6
    assert len(next(p for p in layout.placements if p.tray.id == "die").tray.wells) == 2   # one well per object
    if stretch:
        assert sum(p.w * p.d for p in layout.placements) == pytest.approx(W * D)


def test_reference_dimensions_never_change_geometry(raw):
    *_, base = _solve(raw)
    raw["box"]["reference"] = {"outer_xyz": [999, 999, 999]}
    *_, other = _solve(raw)
    assert [(p.x, p.y, p.size) for p in base.placements] == [(p.x, p.y, p.size) for p in other.placements]


@pytest.mark.parametrize("orientation", ["auto", "flat", "upright"])
def test_tall_card_stack_fits_usable_depth(raw, orientation):
    if orientation == "upright":
        raw["box"]["inner_xyz"][2] = 70                         # 63 mm cards can stand

    deck = raw["components"][0]
    deck["count"], deck["orientation"] = 200, orientation      # 64 mm stack, 42.8 mm usable depth
    game, rules, layout = _solve(raw)
    depth = usable_height(game, rules) - rules.floor
    wells = next(p for p in layout.placements if p.tray.id == "big").tray.wells
    assert all(w.content_z <= depth + 1e-6 for w in wells)
    if orientation == "flat":
        assert len(wells) == 2
    if orientation == "upright":
        assert wells[0].upright and wells[0].x == pytest.approx(64 + 2 * rules.clearance)


@pytest.mark.parametrize("mutate, error", [
    (lambda r: r["trays"][0]["compartments"].append("ghost"), "unknown components"),
    (lambda r: r["trays"].pop(), "not in any tray"),
    (lambda r: r["trays"][2]["compartments"].append("deck_a"), "more than one compartment"),
    (lambda r: r["trays"][1].__setitem__("compartments", [["deck_b", "coins"], "deck_c"]), "one kind"),
])
def test_schema_rejects_inconsistent_trays(raw, mutate, error):
    mutate(raw)
    with pytest.raises(ValueError, match=error):
        Game.model_validate(raw)


def test_build_refuses_null_dimensions_and_lists_them(raw, tmp_path):
    raw["box"]["inner_xyz"][2] = None
    raw["components"][0]["stack"]["height"] = None
    (tmp_path / "game.yaml").write_text(yaml.safe_dump(raw))
    runner = CliRunner()

    result = runner.invoke(app, ["build", str(tmp_path), "--no-render"])
    assert result.exit_code == 2
    assert "box.inner_xyz" in result.output and "components.deck_a.stack.height" in result.output
    assert not (tmp_path / "insert.scad").exists()

    assert runner.invoke(app, ["build", str(tmp_path), "--skip-incomplete"]).exit_code == 0


@pytest.mark.parametrize("path", sorted(REPO.glob("games/*/game.yaml")) + [FIXTURE / "game.yaml"], ids=str)
def test_game_files_are_valid(path):
    load_game(path)


def _stl_bbox(path: Path):
    v = [tuple(map(float, m)) for m in re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", path.read_text())]
    return [(min(c[i] for c in v), max(c[i] for c in v)) for i in range(3)]


@pytest.mark.skipif(not (shutil.which("openscad") or __import__("os").environ.get("OPENSCAD")),
                    reason="OpenSCAD not installed")
def test_rendered_trays_match_layout_exterior(tmp_path):
    game_dir = tmp_path / "testgame"
    shutil.copytree(FIXTURE, game_dir)
    result = CliRunner().invoke(app, ["build", str(game_dir), "--fit-test", "5"])
    assert result.exit_code == 0, result.output
    assert "BIT" not in result.output                       # BIT physical validation stayed quiet

    game, rules, layout = _solve(yaml.safe_load((FIXTURE / "game.yaml").read_text()))
    out = game_dir / "out"
    for p in layout.placements:
        bbox = _stl_bbox(out / f"{p.tray.id}.stl")
        assert [hi - lo for lo, hi in bbox] == pytest.approx(list(p.size), abs=0.01)
        assert (out / f"{p.tray.id}.3mf").stat().st_size > 0
        assert all((out / f"{p.tray.id}_{v}.png").exists() for v in render.VIEWS)
        X, Y, _ = p.size
        ring = _stl_bbox(out / "fit" / f"{p.tray.id}.stl")
        assert [hi - lo for lo, hi in ring] == pytest.approx([X, Y, rules.floor + 5], abs=0.01)
    assert (out / "assembly_iso.png").exists()


@pytest.mark.skipif(slicer.bambu() is None or not shutil.which("openscad"), reason="needs Bambu Studio and OpenSCAD")
def test_slice_adds_print_estimates(tmp_path):
    game_dir = tmp_path / "testgame"
    shutil.copytree(FIXTURE, game_dir)
    result = CliRunner().invoke(app, ["build", str(game_dir), "--slice"])
    assert result.exit_code == 0, result.output
    rows = re.findall(r"^\| (\w+) \| (\d+)h (\d+)m \| (\d+) g \|$", (game_dir / "out" / "report.md").read_text(), re.M)
    assert {r[0] for r in rows} == {"big", "small", "die"}
    assert all(int(g) > 0 and int(h) * 60 + int(m) > 0 for _, h, m, g in rows)
