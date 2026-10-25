"""2D shelf packing of trays into the box, with height layers when one layer is not enough."""
from dataclasses import dataclass, field

from .model import Game, Printer, Rules
from .sizing import TrayPlan, plan_trays, usable_height


@dataclass
class Placement:
    tray: TrayPlan
    x: float                       # box frame, from the inner wall corner
    y: float
    w: float                       # footprint in the box frame (after rotation and stretch)
    d: float
    rotated: bool
    layer: int
    shelf: int
    z: float = 0.0
    h: float = 0.0

    @property
    def size(self) -> tuple[float, float, float]:
        """Exterior size in the tray's own frame, i.e. BOX_SIZE_XYZ."""
        return (self.d, self.w, self.h) if self.rotated else (self.w, self.d, self.h)


@dataclass
class Layout:
    area: tuple[float, float]      # packable X/Y (box interior minus margin)
    offset: float                  # margin per side
    usable_h: float
    placements: list[Placement]
    fill: float                    # tray footprints before stretching / packable area, per layer avg
    free: list[tuple[float, float, float, float, int]] = field(default_factory=list)   # x, y, w, d, layer
    warnings: list[str] = field(default_factory=list)


def _shelf_pack(trays: list[TrayPlan], W: float, D: float, tall_shelves: bool):
    """Next-fit-ish shelf packing. Returns placements, leftovers, shelves [(y, h)]."""
    shelves: list[list[float]] = []            # [y, h, used_x]
    placed: list[Placement] = []
    left: list[TrayPlan] = []
    for t in trays:
        orients = [(t.w, t.d, False), (t.d, t.w, True)]
        for si, s in enumerate(shelves):
            fits = [o for o in orients if o[1] <= s[1] + 1e-9 and s[2] + o[0] <= W + 1e-9]
            if fits:
                w, d, r = max(fits, key=lambda o: o[1])     # fill the shelf height
                placed.append(Placement(t, s[2], s[0], w, d, r, 0, si))
                s[2] += w
                break
        else:
            y = sum(s[1] for s in shelves)
            fits = [o for o in orients if o[0] <= W + 1e-9 and y + o[1] <= D + 1e-9]
            if not fits:
                left.append(t)
                continue
            w, d, r = (max if tall_shelves else min)(fits, key=lambda o: o[1])
            shelves.append([y, d, w])
            placed.append(Placement(t, 0, y, w, d, r, 0, len(shelves) - 1))
    return placed, left, [(s[0], s[1]) for s in shelves]


def _best_pack(trays: list[TrayPlan], W: float, D: float):
    tries = []
    for key in (lambda t: -max(t.w, t.d), lambda t: -t.w * t.d):
        for tall in (False, True):
            placed, left, shelves = _shelf_pack(sorted(trays, key=key), W, D, tall)
            tries.append((len(left), sum(h for _, h in shelves), placed, left, shelves))
    return min(tries, key=lambda r: r[:2])[2:]


def _free_space(placed: list[Placement], shelves, W: float, D: float, layer: int):
    free = []
    for si, (y, h) in enumerate(shelves):
        row = [p for p in placed if p.shelf == si]
        used = sum(p.w for p in row)
        if W - used > 0.05:
            free.append((used, y, W - used, h, layer))
        free += [(p.x, p.y + p.d, p.w, h - p.d, layer) for p in row if h - p.d > 0.05]
    top = sum(h for _, h in shelves)
    if D - top > 0.05:
        free.append((0, top, W, D - top, layer))
    return free


def _stretch(placed: list[Placement], shelves, W: float, D: float):
    """Grow trays so each layer tiles the whole packable area."""
    extra_y = (D - sum(h for _, h in shelves)) / len(shelves)
    y = 0.0
    for si, (_, h) in enumerate(shelves):
        row = sorted((p for p in placed if p.shelf == si), key=lambda p: p.x)
        extra_x = (W - sum(p.w for p in row)) / len(row)
        x = 0.0
        for p in row:
            p.x, p.y, p.w, p.d = x, y, p.w + extra_x, h + extra_y
            x += p.w
        y += h + extra_y


def solve(game: Game, rules: Rules, printer: Printer) -> Layout:
    trays = plan_trays(game, rules)
    W = game.box.inner_xyz[0] - rules.box_margin
    D = game.box.inner_xyz[1] - rules.box_margin
    U = usable_height(game, rules)

    layers = []
    remaining = trays
    while remaining:
        placed, left, shelves = _best_pack(remaining, W, D)
        if not placed:
            names = ", ".join(f"{t.id} {t.w:.1f}x{t.d:.1f}" for t in left)
            raise ValueError(f"trays larger than the box interior {W:.1f}x{D:.1f}: {names}")
        layers.append((placed, shelves))
        remaining = left

    layout = Layout((W, D), rules.box_margin / 2, U, [], 0.0)
    z = 0.0
    for li, (placed, shelves) in enumerate(layers):
        top = li == len(layers) - 1
        h = U - z if top else max(p.tray.content_z for p in placed) + rules.floor
        if max(p.tray.content_z for p in placed) + rules.floor > h + 1e-9:
            raise ValueError(f"layers don't fit in {U:.1f} mm of usable height")
        layout.fill += sum(p.w * p.d for p in placed) / (W * D) / len(layers)
        layout.free += _free_space(placed, shelves, W, D, li)
        if rules.stretch:
            _stretch(placed, shelves, W, D)
        for p in placed:
            p.layer, p.z, p.h = li, z, h
        layout.placements += placed
        z += h

    for p in layout.placements:
        grown = max(p.w - (p.tray.d if p.rotated else p.tray.w), p.d - (p.tray.w if p.rotated else p.tray.d)) / 2
        if grown > 10:
            layout.warnings.append(f"tray {p.tray.id}: stretching adds solid walls up to {grown:.0f} mm thick "
                                   f"(filament); consider regrouping or rules.stretch: false")
    if len(layers) > 1:
        layout.warnings.append(f"{len(layers)} layers: lower trays are covered by upper ones")
    bed = printer.beds[printer.bed]
    for p in layout.placements:
        x, y, _ = p.size
        if not (x <= bed[0] and y <= bed[1]) and not (y <= bed[0] and x <= bed[1]):
            layout.warnings.append(f"tray {p.tray.id} {x:.1f}x{y:.1f} exceeds the {printer.bed} bed {bed[0]}x{bed[1]}")
    return layout
