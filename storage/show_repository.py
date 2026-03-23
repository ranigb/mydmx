from __future__ import annotations

import json
from pathlib import Path

from engine.models import Cue, FixtureGroup, FixturePatch, FixtureState, Scene, Sequence, ShowFile, Transition, TriggerMode


class ShowRepository:
    def load(self, path: str | Path) -> ShowFile:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        fixtures = [
            FixturePatch(
                fixture_id=item["fixture_id"],
                start_address=item["start_address"],
                num_channels=item["num_channels"],
                position=(item.get("position", [0, 0])[0], item.get("position", [0, 0])[1]),
                angle=item.get("angle", 0),
            )
            for item in payload.get("fixtures", [])
        ]
        groups = [
            FixtureGroup(
                id=item["id"],
                name=item["name"],
                fixture_ids=list(item.get("fixture_ids", [])),
            )
            for item in payload.get("groups", [])
        ]
        scenes = [self._deserialize_scene(item) for item in payload.get("scenes", [])]
        sequences = [self._deserialize_sequence(item) for item in payload.get("sequences", [])]
        return ShowFile(
            fixtures=fixtures,
            groups=groups,
            scenes=scenes,
            sequences=sequences,
            schema_version=payload.get("schema_version", 1),
        )

    def save(self, path: str | Path, show_file: ShowFile) -> None:
        payload = {
            "schema_version": show_file.schema_version,
            "fixtures": [self._serialize_fixture_patch(patch) for patch in show_file.fixtures],
            "groups": [self._serialize_group(group) for group in show_file.groups],
            "scenes": [self._serialize_scene(scene) for scene in show_file.scenes],
            "sequences": [self._serialize_sequence(sequence) for sequence in show_file.sequences],
        }
        with Path(path).open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _serialize_fixture_patch(self, patch: FixturePatch) -> dict:
        return {
            "fixture_id": patch.fixture_id,
            "start_address": patch.start_address,
            "num_channels": patch.num_channels,
            "position": [patch.position[0], patch.position[1]],
            "angle": patch.angle,
        }

    def _serialize_group(self, group: FixtureGroup) -> dict:
        return {
            "id": group.id,
            "name": group.name,
            "fixture_ids": list(group.fixture_ids),
        }

    def _serialize_scene(self, scene: Scene) -> dict:
        return {
            "id": scene.id,
            "name": scene.name,
            "notes": scene.notes,
            "fixture_states": [self._serialize_fixture_state(state) for state in scene.fixture_states.values()],
        }

    def _serialize_sequence(self, sequence: Sequence) -> dict:
        return {
            "id": sequence.id,
            "name": sequence.name,
            "notes": sequence.notes,
            "cyclic": sequence.cyclic,
            "cues": [self._serialize_cue(cue) for cue in sequence.cues],
        }

    def _serialize_cue(self, cue: Cue) -> dict:
        return {
            "id": cue.id,
            "scene_id": cue.scene_id,
            "notes": cue.notes,
            "trigger_mode": cue.trigger_mode.value,
            "transition": {
                "fade_in_ms": cue.transition.fade_in_ms,
                "fade_out_ms": cue.transition.fade_out_ms,
                "hold_ms": cue.transition.hold_ms,
            },
        }

    def _serialize_fixture_state(self, state: FixtureState) -> dict:
        return {
            "fixture_id": state.fixture_id,
            "intensity": state.intensity,
            "red": state.red,
            "green": state.green,
            "blue": state.blue,
            "white": state.white,
        }

    def _deserialize_scene(self, payload: dict) -> Scene:
        states = [self._deserialize_fixture_state(item) for item in payload.get("fixture_states", [])]
        return Scene(
            id=payload["id"],
            name=payload["name"],
            notes=payload.get("notes", ""),
            fixture_states={state.fixture_id: state for state in states},
        )

    def _deserialize_sequence(self, payload: dict) -> Sequence:
        cues = [self._deserialize_cue(item) for item in payload.get("cues", [])]
        return Sequence(
            id=payload["id"],
            name=payload["name"],
            notes=payload.get("notes", ""),
            cyclic=payload.get("cyclic", False),
            cues=cues,
        )

    def _deserialize_cue(self, payload: dict) -> Cue:
        transition_payload = payload.get("transition", {})
        transition = Transition(
            fade_in_ms=transition_payload.get("fade_in_ms", 0),
            fade_out_ms=transition_payload.get("fade_out_ms", 0),
            hold_ms=transition_payload.get("hold_ms", 0),
        )
        return Cue(
            id=payload["id"],
            scene_id=payload["scene_id"],
            notes=payload.get("notes", ""),
            trigger_mode=TriggerMode(payload.get("trigger_mode", TriggerMode.MANUAL.value)),
            transition=transition,
        )

    def _deserialize_fixture_state(self, payload: dict) -> FixtureState:
        return FixtureState(
            fixture_id=payload["fixture_id"],
            intensity=payload.get("intensity", 0),
            red=payload.get("red", 0),
            green=payload.get("green", 0),
            blue=payload.get("blue", 0),
            white=payload.get("white", 0),
        )