"""Measured components -> compartments -> tray footprints. Expects a game with no nulls."""
import math
from dataclasses import dataclass

from .model import Game, Rules


@dataclass
class Well:
    label: str
    kind: str                      # cards | tokens | object
    x: float                       # interior, clearance included
    y: float
    content_z: float               # height the pieces occupy
    upright: bool = False


@dataclass
class TrayPlan:
    id: str
    name: str
    wells: list[Well]              # laid out in a row along X
    w: float                       # exterior footprint
    d: float

    @property
    def content_z(self) -> float:
        return max(w.content_z for w in self.wells)


def usable_height(game: Game, rules: Rules) -> float:
    """Top of the insert: box rim minus whatever lies on top, minus lid clearance."""
    return game.box.inner_xyz[2] - sum(t.xyz[2] for t in game.on_top) - rules.top_clearance


def _row_area(wells: list[Well], rules: Rules) -> float:
    return (sum(w.x for w in wells) + rules.divider * (len(wells) - 1)) * max(w.y for w in wells)


def _stack_wells(game: Game, ids: list[str], rules: Rules, depth: float) -> list[Well]:
    parts = [game.component(i) for i in ids]
    label = "+".join(ids)
    kind = parts[0].kind
    short = max(min(p.size_xy) for p in parts)
    long_ = max(max(p.size_xy) for p in parts)
    height = sum(p.count * p.stack.height / p.stack.count for p in parts)
    orientation = next((p.orientation for p in parts if p.orientation != "auto"), "auto")
    c2 = 2 * rules.clearance

    options: dict[str, list[Well]] = {}
    if orientation in ("auto", "flat"):
        n = math.ceil(height / depth)
        options["flat"] = [Well(label if n == 1 else f"{label}#{i + 1}", kind, short + c2, long_ + c2, height / n)
                           for i in range(n)]
    if orientation in ("auto", "upright") and kind == "cards" and short <= depth:
        options["upright"] = [Well(label, kind, height + c2, long_ + c2, short, upright=True)]
    if not options:
        raise ValueError(f"{label}: cards {short} mm tall don't fit upright in {depth:.1f} mm of usable depth")
    return min(options.values(), key=lambda ws: _row_area(ws, rules))


def plan_trays(game: Game, rules: Rules) -> list[TrayPlan]:
    depth = usable_height(game, rules) - rules.floor
    if depth <= 0:
        raise ValueError(f"no usable height left: {depth:.1f} mm")
    trays = []
    for t in game.trays:
        wells: list[Well] = []
        for ids in t.groups():
            c = game.component(ids[0])
            if c.kind == "object":
                x, y, z = c.xyz
                if z > depth:
                    raise ValueError(f"{c.id}: {z} mm tall, only {depth:.1f} mm usable")
                wells += [Well(c.id if c.count == 1 else f"{c.id}#{i + 1}", "object",
                               x + 2 * rules.clearance, y + 2 * rules.clearance, z) for i in range(c.count)]
            else:
                wells += _stack_wells(game, ids, rules, depth)
        w = 2 * rules.wall + sum(x.x for x in wells) + rules.divider * (len(wells) - 1)
        d = 2 * rules.wall + max(x.y for x in wells)
        trays.append(TrayPlan(t.id, t.name or t.id, wells, w, d))
    return trays
