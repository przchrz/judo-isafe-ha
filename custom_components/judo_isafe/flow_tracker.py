"""Derives a flow rate from the cumulative water counter (command 28)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class FlowSample:
    at: datetime
    total_l: int


class FlowTracker:
    """The i-SAFE never reports instantaneous flow, so differentiate the totaliser.

    Sensitivity trades against latency: the 1-litre counter granularity means the
    smallest detectable rate is one litre per averaging window.
    """

    def __init__(self, window: timedelta = timedelta(seconds=120)) -> None:
        self._window = window
        self._samples: deque[FlowSample] = deque()

    def add(self, total_l: int, at: datetime) -> None:
        if self._samples and total_l < self._samples[-1].total_l:
            # A shrinking counter means a device swap or reset, not backflow.
            self._samples.clear()
        self._samples.append(FlowSample(at, total_l))
        # Keep the oldest sample that still leaves the window fully covered.
        while len(self._samples) > 2 and at - self._samples[1].at >= self._window:
            self._samples.popleft()

    def reset(self) -> None:
        self._samples.clear()

    @property
    def flow_l_per_min(self) -> float | None:
        if len(self._samples) < 2:
            return None
        first = self._samples[0]
        last = self._samples[-1]
        elapsed = (last.at - first.at).total_seconds()
        if elapsed <= 0:
            return None
        return round((last.total_l - first.total_l) / elapsed * 60, 2)

    @property
    def is_flowing(self) -> bool:
        return bool(self.flow_l_per_min)
