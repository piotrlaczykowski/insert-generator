"""game.yaml / printer.yaml schema.

Hard rule: a dimension nobody measured is null. Nothing here invents defaults for
physical sizes; `checklist.missing()` lists every null that blocks a build.
"""
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator

Dim = PositiveFloat | None
XY = tuple[Dim, Dim]
XYZ = tuple[Dim, Dim, Dim]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Rules(Strict):
    wall: PositiveFloat
    divider: PositiveFloat
    floor: PositiveFloat
    clearance: float = Field(ge=0)
    box_margin: float = Field(ge=0)
    top_clearance: float = Field(ge=0)
    stretch: bool


class Slicer(Strict):
    machine: str
    process: str
    filament: str
    filament_diameter: PositiveFloat
    filament_density: PositiveFloat


class Printer(Strict):
    name: str
    nozzle: PositiveFloat
    beds: dict[str, tuple[PositiveFloat, PositiveFloat]]
    bed: str
    rules: Rules
    slicer: Slicer | None = None

    @model_validator(mode="after")
    def _bed_exists(self):
        if self.bed not in self.beds:
            raise ValueError(f"bed '{self.bed}' not in beds {list(self.beds)}")
        return self


class Box(Strict):
    inner_xyz: XYZ                       # interior of the box bottom; Z = floor to rim
    # Publisher/BGG numbers: outer and approximate. Sanity check only, never geometry.
    reference: dict | None = None


class OnTop(Strict):
    id: str
    name: str
    xyz: XYZ


class Stack(Strict):
    count: PositiveInt                   # how many pieces were in the measured stack
    height: Dim


class Component(Strict):
    id: str
    name: str
    kind: Literal["cards", "tokens", "object"]
    count: PositiveInt = 1
    size_xy: XY | None = None            # one card / token (round token: [d, d])
    stack: Stack | None = None
    xyz: XYZ | None = None               # objects only
    orientation: Literal["auto", "flat", "upright"] = "auto"
    note: str | None = None

    @model_validator(mode="after")
    def _fields_for_kind(self):
        if self.kind == "object":
            if self.xyz is None:
                raise ValueError(f"{self.id}: objects need xyz")
        elif self.size_xy is None or self.stack is None:
            raise ValueError(f"{self.id}: {self.kind} need size_xy and stack")
        if self.orientation == "upright" and self.kind != "cards":
            raise ValueError(f"{self.id}: only cards can be upright")
        return self


class Tray(Strict):
    id: str
    name: str | None = None
    # One entry per compartment; a list shares one compartment (stacked together).
    compartments: list[str | list[str]]

    def groups(self) -> list[list[str]]:
        return [[c] if isinstance(c, str) else c for c in self.compartments]


class Game(Strict):
    name: str
    slug: str
    edition: str | None = None
    box: Box
    on_top: list[OnTop] = []
    components: list[Component]
    trays: list[Tray]
    rules: dict = {}                     # overrides of printer.yaml rules
    notes: list[str] = []

    @model_validator(mode="after")
    def _references(self):
        ids = [c.id for c in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate component ids")
        used = [i for t in self.trays for g in t.groups() for i in g]
        unknown = set(used) - set(ids)
        if unknown:
            raise ValueError(f"trays reference unknown components: {sorted(unknown)}")
        dupes = {i for i in used if used.count(i) > 1}
        if dupes:
            raise ValueError(f"components in more than one compartment: {sorted(dupes)}")
        if unplaced := set(ids) - set(used):
            raise ValueError(f"components not in any tray: {sorted(unplaced)}")
        for t in self.trays:
            for g in t.groups():
                kinds = {self.component(i).kind for i in g}
                if len(g) > 1 and kinds != {"cards"} and kinds != {"tokens"}:
                    raise ValueError(f"tray {t.id}: a shared compartment must hold one kind of stackable pieces")
        return self

    def component(self, cid: str) -> Component:
        return next(c for c in self.components if c.id == cid)


def load_printer(path: Path) -> Printer:
    return Printer.model_validate(yaml.safe_load(path.read_text()))


def load_game(path: Path) -> Game:
    return Game.model_validate(yaml.safe_load(path.read_text()))


def effective_rules(printer: Printer, game: Game) -> Rules:
    return Rules.model_validate(printer.rules.model_dump() | game.rules)
