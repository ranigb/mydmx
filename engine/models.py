from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


def clamp_dmx(value: int) -> int:
    return max(0, min(255, int(value)))


class TriggerMode(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"


@dataclass(slots=True)
class FixtureState:
    fixture_id: int
    intensity: int = 0
    red: int = 0
    green: int = 0
    blue: int = 0
    white: int = 0

    def normalized(self) -> "FixtureState":
        return FixtureState(
            fixture_id=self.fixture_id,
            intensity=clamp_dmx(self.intensity),
            red=clamp_dmx(self.red),
            green=clamp_dmx(self.green),
            blue=clamp_dmx(self.blue),
            white=clamp_dmx(self.white),
        )


@dataclass(slots=True)
class FixtureGroup:
    id: str
    name: str
    fixture_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class FixturePatch:
    fixture_id: int
    start_address: int
    num_channels: int
    position: tuple[int, int] = (0, 0)
    angle: int = 0


@dataclass(slots=True)
class Transition:
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    hold_ms: int = 0


@dataclass(slots=True)
class Scene:
    id: str
    name: str
    fixture_states: dict[int, FixtureState] = field(default_factory=dict)
    notes: str = ""

    def with_updates(self, states: list[FixtureState]) -> "Scene":
        updated_states = dict(self.fixture_states)
        for state in states:
            updated_states[state.fixture_id] = state.normalized()
        return Scene(id=self.id, name=self.name, fixture_states=updated_states, notes=self.notes)


@dataclass(slots=True)
class Cue:
    id: str
    scene_id: str
    transition: Transition = field(default_factory=Transition)
    trigger_mode: TriggerMode = TriggerMode.MANUAL
    notes: str = ""


@dataclass(slots=True)
class Sequence:
    id: str
    name: str
    cues: list[Cue] = field(default_factory=list)
    notes: str = ""
    cyclic: bool = False


@dataclass(slots=True)
class LiveOverride:
    fixture_states: dict[int, FixtureState] = field(default_factory=dict)
    active: bool = False

    def clear(self) -> None:
        self.fixture_states.clear()
        self.active = False

    def set_states(self, states: list[FixtureState]) -> None:
        for state in states:
            self.fixture_states[state.fixture_id] = state.normalized()
        self.active = bool(self.fixture_states)


@dataclass(slots=True)
class ShowFile:
    fixtures: list[FixturePatch]
    groups: list[FixtureGroup] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    sequences: list[Sequence] = field(default_factory=list)
    schema_version: int = 1