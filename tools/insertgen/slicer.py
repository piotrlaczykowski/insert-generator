"""Print time and filament estimates by slicing the exported 3MF headless in Bambu Studio."""
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

from .model import Slicer

APP = Path("/Applications/BambuStudio.app/Contents")


def bambu() -> Path | None:
    exe = os.environ.get("BAMBU_STUDIO") or shutil.which("bambu-studio") or APP / "MacOS" / "BambuStudio"
    return Path(exe) if Path(exe).exists() else None


def _profiles(exe: Path) -> Path:
    return exe.resolve().parents[1] / "Resources" / "profiles" / "BBL"


def seconds(text: str) -> int:
    """'1d 2h 3m 4s' -> seconds."""
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return sum(int(n) * units[u] for n, u in re.findall(r"(\d+)([dhms])", text))


def estimate(model: Path, cfg: Slicer, workdir: Path) -> tuple[int, float]:
    """Slice one 3MF. Returns (seconds, grams)."""
    exe = bambu()
    if exe is None:
        raise RuntimeError("Bambu Studio not found: install it or set BAMBU_STUDIO")
    p = _profiles(exe)
    workdir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(exe), "--slice", "0", "--arrange", "1", "--orient", "0",
                        "--load-settings", f"{p}/machine/{cfg.machine}.json;{p}/process/{cfg.process}.json",
                        "--load-filaments", f"{p}/filament/{cfg.filament}.json",
                        "--outputdir", str(workdir), str(model)], capture_output=True, text=True)
    gcode = workdir / "plate_1.gcode"
    if r.returncode != 0 or not gcode.exists():
        raise RuntimeError(f"Bambu Studio failed to slice {model.name} (exit {r.returncode})")
    with gcode.open() as f:
        head = f.read(200_000)                  # estimates live in the header block
    time = re.search(r"total estimated time: ([^\n;]+)", head)
    length = re.search(r"total filament length \[mm\] : ([\d.]+)", head)
    if not (time and length):
        raise RuntimeError(f"no estimates in the G-code header for {model.name}")
    mm3 = float(length.group(1)) * math.pi * (cfg.filament_diameter / 2) ** 2
    return seconds(time.group(1)), mm3 / 1000 * cfg.filament_density
