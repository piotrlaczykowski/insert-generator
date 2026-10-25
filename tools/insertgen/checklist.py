"""Turn every null dimension into a measurement instruction."""
from dataclasses import dataclass

from .model import Game

HOW = "mm, 0.1 precision, calipers"


@dataclass(frozen=True)
class Item:
    path: str
    what: str
    how: str


def _nulls(values, labels) -> list[str]:
    return [label for v, label in zip(values, labels) if v is None]


def missing(game: Game) -> list[Item]:
    out: list[Item] = []
    if axes := _nulls(game.box.inner_xyz, "XYZ"):
        out.append(Item("box.inner_xyz", f"Box interior {'/'.join(axes)}",
                        "Inside the box bottom at floor level: X = short side, Y = long side, "
                        f"Z = floor to the top rim of the bottom part. {HOW}."))
    for t in game.on_top:
        if axes := _nulls(t.xyz, "XYZ"):
            out.append(Item(f"on_top.{t.id}.xyz", f"{t.name}: {'/'.join(axes)}",
                            f"Outer size as it lies on top of the insert, Z at the thickest spot. {HOW}."))
    for c in game.components:
        p = f"components.{c.id}"
        if c.kind == "object":
            if axes := _nulls(c.xyz, "XYZ"):
                out.append(Item(f"{p}.xyz", f"{c.name}: {'/'.join(axes)}",
                                f"Bounding box at the widest points, in the orientation you want it stored. {HOW}."))
            continue
        if axes := _nulls(c.size_xy, "XY"):
            hint = ("One card, both edges." if c.kind == "cards"
                    else "One token: diameter (enter it twice) or width and depth if not round.")
            out.append(Item(f"{p}.size_xy", f"{c.name}: {'/'.join(axes)}", f"{hint} {HOW}."))
        if c.stack.height is None:
            n = c.stack.count
            out.append(Item(f"{p}.stack.height", f"{c.name}: height of a stack of {n}",
                            f"Stack {n} pieces, press lightly, measure the thickness. {HOW}."
                            if n > 1 else f"Single piece thickness; measure several and average. {HOW}."))
    return out


def format_checklist(game: Game, items: list[Item]) -> str:
    lines = [f"Measurements needed for {game.name} ({len(items)}):"]
    lines += [f"  [ ] {i.path}\n      {i.what}\n      {i.how}" for i in items]
    return "\n".join(lines)
