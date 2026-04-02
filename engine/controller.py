from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from fixture import Fixture

from .fade_engine import FadeEngine
from .models import Cue, FixtureGroup, FixturePatch, FixtureState, Scene, Sequence, ShowFile, Transition, TriggerMode
from .output_engine import OutputEngine
from .scene_engine import SceneEngine
from .sequence_engine import SequenceEngine
from .state_manager import EngineStateManager


@dataclass(slots=True)
class _FadeState:
    started_at: float
    duration_ms: int
    start_states: dict[int, FixtureState]
    end_states: dict[int, FixtureState]
    destination_scene_id: str | None


class EngineController:
    def __init__(self, fixtures: list[Fixture], update_manager=None) -> None:
        self.fixtures = fixtures
        self.groups: list[FixtureGroup] = []
        self.state_manager = EngineStateManager()
        self.scene_engine = SceneEngine()
        self.fade_engine = FadeEngine()
        self.sequence_engine = SequenceEngine()
        self.output_engine = OutputEngine(fixtures, update_manager) if update_manager is not None else None
        self._fade_state: _FadeState | None = None
        self._loaded_sequence_id: str | None = None
        self._pending_render = False

    @property
    def state(self):
        return self.state_manager.state

    @property
    def is_output_enabled(self) -> bool:
        return self.output_engine is not None

    @property
    def loaded_sequence_id(self) -> str | None:
        return self._loaded_sequence_id

    @property
    def loaded_sequence(self) -> Sequence | None:
        if self._loaded_sequence_id is None:
            return None
        return self.state.sequences.get(self._loaded_sequence_id)

    @property
    def current_cue(self) -> Cue | None:
        return self.sequence_engine.current_cue

    @property
    def next_cue(self) -> Cue | None:
        return self.sequence_engine.next_cue

    @property
    def current_cue_number(self) -> int | None:
        if self.sequence_engine.current_cue is None:
            return None
        return self.sequence_engine.cue_index + 1

    @property
    def is_sequence_paused(self) -> bool:
        return self.sequence_engine.is_paused

    @property
    def is_rhythm_playing(self) -> bool:
        return self.sequence_engine.is_rhythm_enabled

    @property
    def rhythm_bpm(self) -> float:
        return self.sequence_engine.rhythm_bpm

    @property
    def is_fading(self) -> bool:
        return self._fade_state is not None

    def build_default_scene(self, name: str = "Scene 1") -> Scene:
        return Scene(id=self._new_id("scene"), name=name, fixture_states={})

    def add_scene(self, scene: Scene) -> None:
        normalized_states = self.scene_engine.resolve_scene(scene)
        self.state_manager.add_scene(Scene(id=scene.id, name=scene.name, fixture_states=normalized_states, notes=scene.notes))

    def create_scene(
        self,
        name: str,
        from_live_output: bool = False,
        fixture_ids: set[int] | None = None,
    ) -> Scene:
        selected_ids = set(fixture_ids or set())
        if from_live_output and selected_ids:
            live_states = self.get_live_output_states()
            base_states = {
                fixture_id: live_states[fixture_id].normalized()
                for fixture_id in selected_ids
                if fixture_id in live_states
            }
        else:
            base_states = {}
        scene = Scene(id=self._new_id("scene"), name=name, fixture_states=base_states)
        self.add_scene(scene)
        if self.state.current_scene_id is None:
            self.state_manager.set_current_scene(scene.id)
            self._render_base_states(self._scene_to_base_output(scene), dirty=False)
        return scene

    def add_fixture(
        self,
        *,
        start_address: int,
        num_channels: int = 5,
        position: tuple[int, int] = (0, 0),
        angle: int = 0,
    ) -> Fixture:
        next_fixture_id = max((fixture.fixture_id for fixture in self.fixtures), default=0) + 1
        fixture = Fixture(
            fixture_id=next_fixture_id,
            start_address=start_address,
            num_channels=num_channels,
            position=position,
            angle=angle,
        )
        self.fixtures.append(fixture)
        if self.output_engine is not None:
            self.output_engine = OutputEngine(self.fixtures, self.output_engine._update_manager)
        if self.state.base_output:
            updated_base = dict(self.state.base_output)
            updated_base[next_fixture_id] = FixtureState(fixture_id=next_fixture_id)
            self.state_manager.set_base_output(updated_base, dirty=self.state.dirty)
        if self.state.current_output:
            updated_output = dict(self.state.current_output)
            updated_output[next_fixture_id] = FixtureState(fixture_id=next_fixture_id)
            self.state_manager.set_output(updated_output, dirty=self.state.dirty)
        self._pending_render = True
        return fixture

    def duplicate_scene(self, scene_id: str, new_name: str) -> Scene:
        scene = self.state.scenes[scene_id]
        duplicate = Scene(
            id=self._new_id("scene"),
            name=new_name,
            fixture_states={fixture_id: state.normalized() for fixture_id, state in scene.fixture_states.items()},
            notes=scene.notes,
        )
        self.add_scene(duplicate)
        return duplicate

    def update_scene_states(self, scene_id: str, states: list[FixtureState]) -> Scene:
        scene = self.state.scenes[scene_id]
        updated_scene = Scene(
            id=scene.id,
            name=scene.name,
            fixture_states={state.fixture_id: state.normalized() for state in states},
            notes=scene.notes,
        )
        self.state_manager.add_scene(updated_scene)
        if self.state.current_scene_id == scene_id:
            base_output = self.scene_engine.overlay_states(self.get_base_scene_states(), updated_scene.fixture_states)
            self._render_base_states(base_output, dirty=self.state.live_override.active)
        return updated_scene

    def rename_scene(self, scene_id: str, name: str) -> None:
        scene = self.state.scenes[scene_id]
        self.state_manager.add_scene(Scene(id=scene.id, name=name, fixture_states=scene.fixture_states, notes=scene.notes))

    def delete_scene(self, scene_id: str) -> None:
        if scene_id not in self.state.scenes:
            return
        del self.state.scenes[scene_id]
        if self.state.current_scene_id == scene_id:
            replacement = next(iter(self.state.scenes), None)
            self.state_manager.set_current_scene(replacement)
            if replacement is not None:
                self._render_live_states(self.state.scenes[replacement].fixture_states, dirty=False)

    def preview_scene(self, scene_id: str | None) -> dict[int, FixtureState]:
        self.state_manager.set_preview_scene(scene_id)
        if scene_id is None:
            return self.get_live_output_states()
        return self._scene_to_base_output(self.state.scenes[scene_id])

    def apply_scene(self, scene_id: str, fade_ms: int = 0) -> None:
        target_scene = self.state.scenes[scene_id]
        target_states = self._scene_to_base_output(target_scene)
        if fade_ms > 0:
            self._fade_state = _FadeState(
                started_at=time.time(),
                duration_ms=fade_ms,
                start_states=self.get_live_output_states(),
                end_states=target_states,
                destination_scene_id=scene_id,
            )
        else:
            self.state_manager.set_current_scene(scene_id)
            self._fade_state = None
            self._render_base_states(target_states, dirty=self.state.live_override.active)

    def set_master_dimmer(self, value: float) -> None:
        self.state_manager.set_master_dimmer(value)
        if self.output_engine is not None:
            self.output_engine.set_master_dimmer(self.state.master_dimmer)
            self._pending_render = True

    def set_blackout(self, enabled: bool) -> None:
        self.state_manager.set_blackout(enabled)
        self._pending_render = True

    def apply_override(self, states: list[FixtureState]) -> None:
        self.state_manager.apply_override(states)
        effective = self.get_effective_live_states()
        self._render_live_states(effective, dirty=True)

    def clear_override(self) -> None:
        self.state_manager.clear_override()
        base_states = self.get_base_scene_states()
        self._render_live_states(base_states, dirty=False)

    def record_override_to_current_scene(self) -> Scene | None:
        current_scene_id = self.state.current_scene_id
        if current_scene_id is None:
            return None
        updated_scene = self.scene_engine.record_override(self.state.scenes[current_scene_id], self.state.live_override)
        self.state_manager.add_scene(updated_scene)
        self.clear_override()
        return updated_scene

    def create_sequence(self, name: str) -> Sequence:
        sequence = Sequence(id=self._new_id("sequence"), name=name)
        self._store_sequence(sequence)
        return sequence

    def rename_sequence(self, sequence_id: str, name: str) -> None:
        sequence = self.state.sequences[sequence_id]
        self._store_sequence(Sequence(id=sequence.id, name=name, cues=sequence.cues, notes=sequence.notes, cyclic=sequence.cyclic))

    def set_sequence_cyclic(self, sequence_id: str, cyclic: bool) -> Sequence:
        sequence = self.state.sequences[sequence_id]
        updated = Sequence(id=sequence.id, name=sequence.name, cues=sequence.cues, notes=sequence.notes, cyclic=cyclic)
        self._store_sequence(updated)
        return updated

    def add_cue_to_sequence(
        self,
        sequence_id: str,
        scene_id: str,
        *,
        fade_in_ms: int = 0,
        hold_ms: int = 0,
        trigger_mode: TriggerMode = TriggerMode.MANUAL,
    ) -> Sequence:
        sequence = self.state.sequences[sequence_id]
        cue = Cue(
            id=self._new_id("cue"),
            scene_id=scene_id,
            transition=Transition(fade_in_ms=fade_in_ms, hold_ms=hold_ms),
            trigger_mode=trigger_mode,
        )
        updated = Sequence(id=sequence.id, name=sequence.name, cues=[*sequence.cues, cue], notes=sequence.notes, cyclic=sequence.cyclic)
        self._store_sequence(updated)
        return updated

    def remove_cue_from_sequence(self, sequence_id: str, cue_id: str) -> Sequence:
        sequence = self.state.sequences[sequence_id]
        updated = Sequence(
            id=sequence.id,
            name=sequence.name,
            cues=[cue for cue in sequence.cues if cue.id != cue_id],
            notes=sequence.notes,
            cyclic=sequence.cyclic,
        )
        self._store_sequence(updated)
        return updated

    def load_sequence(self, sequence_id: str) -> None:
        self._loaded_sequence_id = sequence_id
        self.sequence_engine.load(self.state.sequences[sequence_id])

    def pause_sequence(self) -> None:
        self.sequence_engine.pause()

    def resume_sequence(self) -> None:
        self.sequence_engine.resume()

    def set_rhythm_bpm(self, bpm: float) -> None:
        self.sequence_engine.set_rhythm_bpm(bpm)

    def start_rhythm_play(self) -> Cue | None:
        cue = self.sequence_engine.start_rhythm()
        if cue is not None:
            self.apply_scene(cue.scene_id, fade_ms=cue.transition.fade_in_ms)
        return cue

    def stop_rhythm_play(self) -> None:
        self.sequence_engine.stop_rhythm()

    def go_next_cue(self) -> Cue | None:
        cue = self.sequence_engine.go()
        if cue is None:
            return None
        self.apply_scene(cue.scene_id, fade_ms=cue.transition.fade_in_ms)
        return cue

    def go_previous_cue(self) -> Cue | None:
        cue = self.sequence_engine.back()
        if cue is None:
            return None
        self.apply_scene(cue.scene_id, fade_ms=cue.transition.fade_in_ms)
        return cue

    def tick(self) -> tuple[bool, list[int] | None] | None:
        auto_cue = self.sequence_engine.poll_auto_advance()
        if auto_cue is not None:
            self.apply_scene(auto_cue.scene_id, fade_ms=auto_cue.transition.fade_in_ms)

        if self._fade_state is not None:
            elapsed_ms = int((time.time() - self._fade_state.started_at) * 1000)
            progress = 1.0 if self._fade_state.duration_ms <= 0 else elapsed_ms / self._fade_state.duration_ms
            blended = self.fade_engine.interpolate(
                self._fade_state.start_states,
                self._fade_state.end_states,
                progress,
            )
            self._render_base_states(blended, dirty=self.state.live_override.active)
            if progress >= 1.0:
                if self._fade_state.destination_scene_id is not None:
                    self.state_manager.set_current_scene(self._fade_state.destination_scene_id)
                self._fade_state = None
        elif self._pending_render:
            self._queue_output(self.get_effective_live_states())
            self._pending_render = False

        if self.output_engine is not None:
            return self.output_engine.flush()
        return None

    def get_live_output_states(self) -> dict[int, FixtureState]:
        if self.state.current_output:
            return {fixture_id: state.normalized() for fixture_id, state in self.state.current_output.items()}
        return self._zero_states()

    def get_base_scene_states(self) -> dict[int, FixtureState]:
        if self.state.base_output:
            return {fixture_id: state.normalized() for fixture_id, state in self.state.base_output.items()}
        return self._zero_states()

    def get_effective_live_states(self) -> dict[int, FixtureState]:
        return self.scene_engine.merge_override(self.get_base_scene_states(), self.state.live_override)

    def build_show_file(self) -> ShowFile:
        fixture_patches = [
            FixturePatch(
                fixture_id=fixture.fixture_id,
                start_address=fixture.start_address,
                num_channels=fixture.num_channels,
                position=fixture.position,
                angle=fixture.angle,
            )
            for fixture in self.fixtures
        ]
        scenes = list(self.state.scenes.values())
        sequences = list(self.state.sequences.values())
        return ShowFile(fixtures=fixture_patches, groups=self.groups, scenes=scenes, sequences=sequences)

    def load_show_file(self, show_file: ShowFile) -> None:
        self.fixtures[:] = [
            Fixture(
                fixture_id=patch.fixture_id,
                start_address=patch.start_address,
                num_channels=patch.num_channels,
                position=patch.position,
                angle=patch.angle,
            )
            for patch in show_file.fixtures
        ]
        self.groups = list(show_file.groups)
        self.state.scenes.clear()
        self.state.sequences.clear()
        for scene in show_file.scenes:
            self.add_scene(scene)
        for sequence in show_file.sequences:
            self._store_sequence(sequence)
        self._loaded_sequence_id = None
        if self.output_engine is not None:
            self.output_engine = OutputEngine(self.fixtures, self.output_engine._update_manager)
        first_scene_id = next(iter(self.state.scenes), None)
        self.state_manager.set_current_scene(first_scene_id)
        self.state_manager.clear_override()
        if first_scene_id is not None:
            self._render_base_states(self._scene_to_base_output(self.state.scenes[first_scene_id]), dirty=False)

    def update_fixture_patch(
        self,
        fixture_id: int,
        *,
        start_address: int | None = None,
        num_channels: int | None = None,
        position: tuple[int, int] | None = None,
        angle: int | None = None,
    ) -> None:
        fixture = self._fixture_by_id(fixture_id)
        requires_output_rebuild = False
        if start_address is not None:
            requires_output_rebuild = requires_output_rebuild or start_address != fixture.start_address
            fixture.start_address = start_address
        if num_channels is not None:
            requires_output_rebuild = requires_output_rebuild or num_channels != fixture.num_channels
            fixture.num_channels = num_channels
        if position is not None:
            fixture.position = position
        if angle is not None:
            fixture.angle = angle
        if requires_output_rebuild and self.output_engine is not None:
            self.output_engine = OutputEngine(self.fixtures, self.output_engine._update_manager)
        self._pending_render = True

    def _render_live_states(self, states: dict[int, FixtureState], *, dirty: bool) -> None:
        normalized = {fixture_id: state.normalized() for fixture_id, state in states.items()}
        self.state_manager.set_output(normalized, dirty=dirty)
        self._queue_output(normalized)

    def _render_base_states(self, states: dict[int, FixtureState], *, dirty: bool) -> None:
        normalized = {fixture_id: state.normalized() for fixture_id, state in states.items()}
        self.state_manager.set_base_output(normalized, dirty=dirty)
        effective = self.scene_engine.merge_override(normalized, self.state.live_override)
        if self.state.live_override.active:
            self.state_manager.set_output(effective, dirty=True)
        self._queue_output(effective)

    def _queue_output(self, states: dict[int, FixtureState]) -> None:
        if self.output_engine is None:
            return
        if self.state.blackout:
            zeroed = {fixture.fixture_id: FixtureState(fixture_id=fixture.fixture_id) for fixture in self.fixtures}
            self.output_engine.render(zeroed)
        else:
            self.output_engine.render(states)

    def _fixture_by_id(self, fixture_id: int) -> Fixture:
        for fixture in self.fixtures:
            if fixture.fixture_id == fixture_id:
                return fixture
        raise KeyError(f"Unknown fixture id: {fixture_id}")

    def _store_sequence(self, sequence: Sequence) -> None:
        self.state_manager.set_sequence(sequence)
        if self._loaded_sequence_id == sequence.id:
            self.sequence_engine.sync(sequence)

    def _scene_to_base_output(self, scene: Scene) -> dict[int, FixtureState]:
        return self.scene_engine.overlay_states(self.get_base_scene_states(), self.scene_engine.resolve_scene(scene))

    def _zero_states(self) -> dict[int, FixtureState]:
        return {
            fixture.fixture_id: FixtureState(fixture_id=fixture.fixture_id)
            for fixture in self.fixtures
        }

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"