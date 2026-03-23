from __future__ import annotations

from .models import FixtureState


class FadeEngine:
    def interpolate(
        self,
        start_states: dict[int, FixtureState],
        end_states: dict[int, FixtureState],
        progress: float,
    ) -> dict[int, FixtureState]:
        clamped_progress = max(0.0, min(1.0, progress))
        fixture_ids = set(start_states) | set(end_states)
        blended: dict[int, FixtureState] = {}

        for fixture_id in fixture_ids:
            start = start_states.get(fixture_id, FixtureState(fixture_id=fixture_id))
            end = end_states.get(fixture_id, FixtureState(fixture_id=fixture_id))
            blended[fixture_id] = FixtureState(
                fixture_id=fixture_id,
                intensity=round(start.intensity + (end.intensity - start.intensity) * clamped_progress),
                red=round(start.red + (end.red - start.red) * clamped_progress),
                green=round(start.green + (end.green - start.green) * clamped_progress),
                blue=round(start.blue + (end.blue - start.blue) * clamped_progress),
                white=round(start.white + (end.white - start.white) * clamped_progress),
            ).normalized()

        return blended