from __future__ import annotations

import time

from .models import Cue, Sequence, TriggerMode


class SequenceEngine:
    def __init__(self) -> None:
        self._sequence: Sequence | None = None
        self._cue_index = -1
        self._cue_started_at = 0.0
        self._paused = False
        self._rhythm_enabled = False
        self._rhythm_bpm = 120.0
        self._next_rhythm_at = 0.0

    @property
    def sequence(self) -> Sequence | None:
        return self._sequence

    @property
    def cue_index(self) -> int:
        return self._cue_index

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_rhythm_enabled(self) -> bool:
        return self._rhythm_enabled

    @property
    def rhythm_bpm(self) -> float:
        return self._rhythm_bpm

    @property
    def current_cue(self) -> Cue | None:
        if self._sequence is None or self._cue_index < 0 or self._cue_index >= len(self._sequence.cues):
            return None
        return self._sequence.cues[self._cue_index]

    @property
    def next_cue(self) -> Cue | None:
        if self._sequence is None:
            return None
        next_index = self._next_index()
        if next_index is None:
            return None
        return self._sequence.cues[next_index]

    def sync(self, sequence: Sequence) -> None:
        current_cue_id = self.current_cue.id if self.current_cue is not None else None
        self._sequence = sequence
        if not sequence.cues:
            self._cue_index = -1
            self._cue_started_at = 0.0
            self._next_rhythm_at = 0.0
            return
        if current_cue_id is None:
            if self._cue_index >= len(sequence.cues):
                self._cue_index = 0 if sequence.cyclic else len(sequence.cues) - 1
            return
        for index, cue in enumerate(sequence.cues):
            if cue.id == current_cue_id:
                self._cue_index = index
                return
        self._cue_index = min(self._cue_index, len(sequence.cues) - 1)

    def load(self, sequence: Sequence) -> None:
        self._sequence = sequence
        self._cue_index = -1
        self._cue_started_at = 0.0
        self._paused = False
        self._rhythm_enabled = False
        self._next_rhythm_at = 0.0

    def go(self) -> Cue | None:
        if self._sequence is None:
            return None
        next_index = self._next_index()
        if next_index is None:
            return None
        self._cue_index = next_index
        self._cue_started_at = time.time()
        if self._rhythm_enabled:
            self._schedule_next_rhythm_tick(self._cue_started_at)
        return self.current_cue

    def back(self) -> Cue | None:
        if self._sequence is None:
            return None
        previous_index = self._previous_index()
        if previous_index is None:
            return None
        self._cue_index = previous_index
        self._cue_started_at = time.time()
        if self._rhythm_enabled:
            self._schedule_next_rhythm_tick(self._cue_started_at)
        return self.current_cue

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        if self._rhythm_enabled and self.current_cue is not None:
            self._schedule_next_rhythm_tick(time.time())

    def set_rhythm_bpm(self, bpm: float) -> None:
        self._rhythm_bpm = max(1.0, min(300.0, float(bpm)))
        if self._rhythm_enabled and self.current_cue is not None:
            self._schedule_next_rhythm_tick(time.time())

    def start_rhythm(self) -> Cue | None:
        self._rhythm_enabled = True
        cue = self.current_cue
        if cue is None:
            cue = self.go()
        elif self.next_cue is None and self._sequence is not None and not self._sequence.cyclic:
            self._cue_index = -1
            cue = self.go()
        elif not self._paused:
            self._schedule_next_rhythm_tick(time.time())
        return cue

    def stop_rhythm(self) -> None:
        self._rhythm_enabled = False
        self._next_rhythm_at = 0.0

    def poll_auto_advance(self) -> Cue | None:
        cue = self.current_cue
        if cue is None or self._paused:
            return None
        if self._rhythm_enabled:
            if self._next_rhythm_at <= 0.0:
                self._schedule_next_rhythm_tick(self._cue_started_at or time.time())
                return None
            if time.time() >= self._next_rhythm_at:
                advanced_cue = self.go()
                if advanced_cue is None:
                    self.stop_rhythm()
                return advanced_cue
            return None
        if cue.trigger_mode != TriggerMode.AUTO:
            return None
        elapsed_ms = (time.time() - self._cue_started_at) * 1000
        if elapsed_ms >= cue.transition.hold_ms:
            return self.go()
        return None

    def _schedule_next_rhythm_tick(self, start_time: float) -> None:
        self._next_rhythm_at = start_time + (60.0 / self._rhythm_bpm)

    def _next_index(self) -> int | None:
        if self._sequence is None or not self._sequence.cues:
            return None
        next_index = self._cue_index + 1
        if next_index < len(self._sequence.cues):
            return next_index
        if self._sequence.cyclic:
            return 0
        return None

    def _previous_index(self) -> int | None:
        if self._sequence is None or not self._sequence.cues or self._cue_index < 0:
            return None
        previous_index = self._cue_index - 1
        if previous_index >= 0:
            return previous_index
        if self._sequence.cyclic:
            return len(self._sequence.cues) - 1
        return None