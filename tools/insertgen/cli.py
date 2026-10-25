from pathlib import Path

import typer

from . import render as rnd
from .checklist import format_checklist, missing
from .model import effective_rules, load_game, load_printer
from .report import build_report
from .scad import render_assembly, render_scad
from .solver import solve

app = typer.Typer(no_args_is_help=True, add_completion=False)
PRINTER = Path(__file__).resolve().parents[2] / "config" / "printer.yaml"


@app.command()
def check(game_dir: Path):
    """Validate game.yaml and list the measurements still missing (exit 2 if any)."""
    game = load_game(game_dir / "game.yaml")
    if items := missing(game):
        typer.echo(format_checklist(game, items))
        raise typer.Exit(2)
    typer.echo(f"{game.name}: all measurements present")


@app.command()
def build(game_dir: Path,
          render: bool = typer.Option(True, help="Export STL/3MF/PNG with OpenSCAD"),
          skip_incomplete: bool = typer.Option(False, help="Exit 0 instead of 2 when measurements are missing (CI)"),
          fit_test: float = typer.Option(0, help="Also export low rings (floor + this many mm of wall) "
                                                  "to out/fit/ for a quick print-and-try fit check"),
          printer: Path = PRINTER):
    """game.yaml -> layout -> insert.scad -> out/ (STL, 3MF, PNG, report.md)."""
    game = load_game(game_dir / "game.yaml")
    if items := missing(game):
        typer.echo("Refusing to build: dimensions are null and will not be guessed.\n")
        typer.echo(format_checklist(game, items))
        raise typer.Exit(0 if skip_incomplete else 2)
    prn = load_printer(printer)
    rules = effective_rules(prn, game)
    try:
        layout = solve(game, rules, prn)
    except ValueError as e:
        typer.echo(f"Layout failed: {e}", err=True)
        raise typer.Exit(1)

    scad = game_dir / "insert.scad"
    scad.write_text(render_scad(game, rules, layout, scad))
    out = game_dir / "out"
    out.mkdir(exist_ok=True)
    bit_warnings: list[str] = []
    if render:
        for p in layout.placements:
            bit_warnings += rnd.tray(scad, p.tray.id, out)
        asm = out / "assembly.scad"
        asm.write_text(render_assembly(game, layout, out, asm))
        rnd.assembly(asm, out)
    report = build_report(game, rules, layout, bit_warnings)
    (out / "report.md").write_text(report)
    typer.echo(report)
    typer.echo(f"Wrote {scad} and {out}/")

    if fit_test > 0:
        # Same footprint and wells, only cut down in height: checks clearance for a few grams of filament.
        for p in layout.placements:
            p.h = rules.floor + fit_test
        fit = out / "fit"
        fit.mkdir(exist_ok=True)
        fit_scad = fit / "fit_test.scad"
        fit_scad.write_text(render_scad(game, rules, layout, fit_scad))
        for p in layout.placements:
            for w in rnd.tray(fit_scad, p.tray.id, fit, views=False):
                typer.echo(f"BIT (fit test): {w}")
        typer.echo(f"Fit-test rings ({fit_test} mm walls) in {fit}/")
