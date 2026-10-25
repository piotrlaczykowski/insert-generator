"""Human-readable build report (Markdown)."""
from .model import Game, Rules
from .solver import Layout


def sanity(game: Game) -> list[str]:
    """Compare measured interior with publisher/BGG outer size. Report only, never geometry."""
    outer = (game.box.reference or {}).get("outer_xyz")
    if not outer:
        return []
    out = []
    for axis, inner, o in zip("XYZ", game.box.inner_xyz, outer):
        if o is None:
            continue
        if inner >= o:
            out.append(f"box {axis}: measured interior {inner} >= reference outer {o}; re-measure")
        elif o - inner > 15:
            out.append(f"box {axis}: interior {inner} is {o - inner:.1f} mm smaller than reference outer {o}; re-measure")
    return out


def _f(v: float) -> str:
    return f"{v:.1f}"


def build_report(game: Game, rules: Rules, layout: Layout, bit_warnings: list[str]) -> str:
    X, Y, Z = game.box.inner_xyz
    W, D = layout.area
    lines = [
        f"# {game.name}: insert report", "",
        f"- Box interior: {X} x {Y} x {Z} mm; packable {_f(W)} x {_f(D)} mm",
        f"- Insert top: {_f(layout.usable_h)} mm (rim {Z} - on top {_f(sum(t.xyz[2] for t in game.on_top))}"
        f" - lid clearance {rules.top_clearance})",
        f"- Fill (tray footprints before stretching): {layout.fill * 100:.0f}%"
        + (" -- trays stretched to fill the box" if rules.stretch else ""), "",
        "| tray | exterior X x Y x Z | at (x, y, z) | rotated | wells (interior X x Y, content height) |",
        "|---|---|---|---|---|",
    ]
    for p in layout.placements:
        sx, sy, sz = p.size
        wells = "<br>".join(f"{w.label}{' upright' if w.upright else ''}: {_f(w.x)} x {_f(w.y)}, {_f(w.content_z)}"
                            for w in p.tray.wells)
        lines.append(f"| {p.tray.id} | {_f(sx)} x {_f(sy)} x {_f(sz)} | "
                     f"{_f(p.x + layout.offset)}, {_f(p.y + layout.offset)}, {_f(p.z)} | {'yes' if p.rotated else 'no'} | {wells} |")
    if layout.free:
        lines += ["", "Free space before stretching (x, y, w, d, layer):"]
        lines += [f"- {_f(x)}, {_f(y)}: {_f(w)} x {_f(d)} (layer {li})" for x, y, w, d, li in layout.free]
    warnings = layout.warnings + sanity(game) + [f"BIT: {w}" for w in bit_warnings]
    lines += ["", "## Warnings", ""] + ([f"- {w}" for w in warnings] or ["- none"])
    return "\n".join(lines) + "\n"
