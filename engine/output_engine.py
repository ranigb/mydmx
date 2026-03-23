from __future__ import annotations

from fixture import Fixture

from .models import FixtureState


class OutputEngine:
    def __init__(self, fixtures: list[Fixture], update_manager) -> None:
        self._fixtures = {fixture.fixture_id: fixture for fixture in fixtures}
        self._update_manager = update_manager
        self._current_values = [0] * 512

    def render(self, fixture_states: dict[int, FixtureState]) -> None:
        for fixture_id, state in fixture_states.items():
            fixture = self._fixtures.get(fixture_id)
            if fixture is None:
                continue
            self._update_manager.queue_multi_update(fixture.start_address - 1, self._fixture_to_channels(state, fixture))

    def flush(self) -> tuple[bool, list[int] | None]:
        return self._update_manager.process_updates(self._current_values)

    def set_master_dimmer(self, value: float) -> None:
        self._update_manager.set_master_dimmer(value)

    def _fixture_to_channels(self, state: FixtureState, fixture: Fixture) -> list[int]:
        channel_values = [0] * fixture.num_channels
        ordered_values = [
            state.intensity,
            state.red,
            state.green,
            state.blue,
            state.white,
        ]
        for index in range(min(fixture.num_channels, len(ordered_values))):
            channel_values[index] = ordered_values[index]
        return channel_values