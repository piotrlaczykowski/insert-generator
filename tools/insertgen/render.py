"""Headless OpenSCAD: per-tray STL/3MF/PNG and an assembled view."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

VIEWS = {"iso": "55,0,25", "top": "0,0,0", "front": "90,0,0", "right": "90,0,90"}


def openscad() -> list[str]:
    exe = os.environ.get("OPENSCAD") or shutil.which("openscad")
    if not exe:
        raise RuntimeError("OpenSCAD not found: install a nightly (brew install --cask openscad@snapshot) or set OPENSCAD")
    # Linux CI has no display; PNG export needs one.
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        return ["xvfb-run", "-a", exe]
    return [exe]


def _run(args: list[str]) -> str:
    r = subprocess.run(openscad() + ["--backend", "Manifold", *args], capture_output=True, text=True)
    if r.returncode != 0 or "ERROR:" in r.stderr:
        raise RuntimeError(f"openscad {' '.join(args)} failed:\n{r.stderr}")
    return r.stderr


def bit_warnings(stderr: str) -> list[str]:
    return [line.split("BGSD_WARNING:", 1)[1].strip().rstrip('"') for line in stderr.splitlines() if "BGSD_WARNING:" in line]


def png(scad: Path, out: Path, view: str, *defines: str, full_render: bool = True) -> None:
    _run([*defines, *(["--render"] if full_render else []), "-o", str(out), "--imgsize=1200,900",
          "--projection=ortho", "--viewall", "--autocenter", f"--camera=0,0,0,{VIEWS[view]},0", str(scad)])


def tray(scad: Path, tray_id: str, out_dir: Path, views: bool = True) -> list[str]:
    """Export one tray. Returns BIT validation warnings."""
    which = f'which="{tray_id}"'
    warnings = bit_warnings(_run(["-D", which, "-o", str(out_dir / f"{tray_id}.stl"), str(scad)]))
    _run(["-D", which, "-o", str(out_dir / f"{tray_id}.3mf"), str(scad)])
    if views:
        for v in VIEWS:
            png(scad, out_dir / f"{tray_id}_{v}.png", v, "-D", which)
    return warnings


def assembly(scad: Path, out_dir: Path) -> None:
    # Preview mode keeps colors and the transparent box ghost.
    for v in ("iso", "top"):
        png(scad, out_dir / f"assembly_{v}.png", v, full_render=False)
