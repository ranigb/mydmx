from __future__ import annotations

import time

from .models import Cue, Sequence, TriggerMode


class SequenceEngine:
    def __init__(self) -> None:
        self._sequence: Sequence | None = None
        self._cue_index = -1
        self._cue_started_at = 0.0
        self._paused = False

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

    def go(self) -> Cue | None:
        if self._sequence is None:
            return None
        next_index = self._next_index()
        if next_index is None:
            return None
        self._cue_index = next_index
        self._cue_started_at = time.time()
        return self.current_cue

    def back(self) -> Cue | None:
        if self._sequence is None:
            return None
        previous_index = self._previous_index()
        if previous_index is None:
            return None
        self._cue_index = previous_index
        self._cue_started_at = time.time()
        return self.current_cue

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def poll_auto_advance(self) -> Cue | None:
        cue = self.current_cue
        if cue is None or self._paused or cue.trigger_mode != TriggerMode.AUTO:
            return None
        elapsed_ms = (time.time() - self._cue_started_at) * 1000
        if elapsed_ms >= cue.transition.hold_ms:
            return self.go()
        return None

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