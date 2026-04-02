from __future__ import annotations

from .models import FixtureState, LiveOverride, Scene


class SceneEngine:
    def resolve_scene(self, scene: Scene) -> dict[int, FixtureState]:
        return {fixture_id: state.normalized() for fixture_id, state in scene.fixture_states.items()}

    def overlay_states(
        self,
        base_states: dict[int, FixtureState],
        scene_states: dict[int, FixtureState],
    ) -> dict[int, FixtureState]:
        merged = {fixture_id: state.normalized() for fixture_id, state in base_states.items()}
        for fixture_id, state in scene_states.items():
            merged[fixture_id] = state.normalized()
        return merged

    def merge_override(
        self,
        base_states: dict[int, FixtureState],
        live_override: LiveOverride,
    ) -> dict[int, FixtureState]:
        merged = dict(base_states)
        if not live_override.active:
            return merged

        for fixture_id, state in live_override.fixture_states.items():
            merged[fixture_id] = state.normalized()
        return merged

    def record_override(self, scene: Scene, live_override: LiveOverride) -> Scene:
        if not live_override.active:
            return scene
        return scene.with_updates(list(live_override.fixture_states.values()))