from __future__ import annotations

from dataclasses import dataclass, field

from .models import FixtureState, LiveOverride, Scene, Sequence


@dataclass(slots=True)
class EngineState:
    scenes: dict[str, Scene] = field(default_factory=dict)
    sequences: dict[str, Sequence] = field(default_factory=dict)
    current_scene_id: str | None = None
    preview_scene_id: str | None = None
    live_override: LiveOverride = field(default_factory=LiveOverride)
    base_output: dict[int, FixtureState] = field(default_factory=dict)
    current_output: dict[int, FixtureState] = field(default_factory=dict)
    master_dimmer: float = 1.0
    blackout: bool = False
    dirty: bool = False


class EngineStateManager:
    def __init__(self) -> None:
        self.state = EngineState()

    def add_scene(self, scene: Scene) -> None:
        self.state.scenes[scene.id] = scene

    def set_sequence(self, sequence: Sequence) -> None:
        self.state.sequences[sequence.id] = sequence

    def set_current_scene(self, scene_id: str | None) -> None:
        self.state.current_scene_id = scene_id
        self.state.dirty = False

    def set_preview_scene(self, scene_id: str | None) -> None:
        self.state.preview_scene_id = scene_id

    def set_base_output(self, fixture_states: dict[int, FixtureState], *, dirty: bool = False) -> None:
        self.state.base_output = fixture_states
        self.state.current_output = fixture_states
        self.state.dirty = dirty

    def set_output(self, fixture_states: dict[int, FixtureState], *, dirty: bool = False) -> None:
        self.state.current_output = fixture_states
        self.state.dirty = dirty

    def set_master_dimmer(self, value: float) -> None:
        self.state.master_dimmer = max(0.0, min(1.0, value))

    def set_blackout(self, enabled: bool) -> None:
        self.state.blackout = enabled

    def apply_override(self, states: list[FixtureState]) -> None:
        self.state.live_override.set_states(states)
        self.state.dirty = True

    def clear_override(self) -> None:
        self.state.live_override.clear()
        self.state.dirty = False