from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from river import drift

N_NUMBERS = 60
RECENT_WINDOW = 100
REFERENCE_WINDOW = 300
TOTAL_WINDOW = RECENT_WINDOW + REFERENCE_WINDOW
REGIME_L1_THRESHOLD = 0.0355
CONTEXT_COOLDOWN = 25

# Calibrated on the canonical synthetic calibration set and validated on 120
# disjoint seeds per IID/gradual/abrupt scenario before production adoption.
CALIBRATION_ID = 'SMART_CONTEXT_CAL_20260831_C'


def _zero_counts() -> np.ndarray:
    return np.zeros(N_NUMBERS, dtype=float)


def _onehot_draw(draw) -> np.ndarray:
    arr = np.asarray(draw, dtype=int)
    if arr.shape != (6,) or len(set(arr.tolist())) != 6 or arr.min() < 1 or arr.max() > 60:
        raise ValueError('draw must contain six unique numbers in [1, 60]')
    x = np.zeros(N_NUMBERS, dtype=float)
    x[arr - 1] = 1.0
    return x


def signal_memory(name: str) -> float:
    if name == 'freq_global':
        return 1000.0
    if name.startswith('freq'):
        return float(name[4:])
    if name.startswith('ewma'):
        return float(name[4:])
    raise ValueError(f'unknown signal {name}')


@dataclass
class ContextRegimeEngine:
    recent_rows: deque = field(default_factory=deque, repr=False)
    observations: int = 0
    detection_count: int = 0
    last_detection_step: int | None = None
    cooldown: int = 0
    last_score: float = 0.0
    score_detector: Any = field(default_factory=lambda: drift.ADWIN(delta=0.002), repr=False)
    reference_sum: np.ndarray = field(default_factory=_zero_counts, repr=False)
    recent_sum: np.ndarray = field(default_factory=_zero_counts, repr=False)

    def update(self, draw) -> None:
        if self.cooldown > 0:
            self.cooldown -= 1

        x = _onehot_draw(draw)
        if len(self.recent_rows) < TOTAL_WINDOW:
            self.recent_rows.append(x)
            if len(self.recent_rows) == TOTAL_WINDOW:
                rows = list(self.recent_rows)
                self.reference_sum = np.sum(rows[:REFERENCE_WINDOW], axis=0)
                self.recent_sum = np.sum(rows[REFERENCE_WINDOW:], axis=0)
        else:
            oldest = self.recent_rows.popleft()
            transition = self.recent_rows[REFERENCE_WINDOW - 1]
            self.reference_sum += transition - oldest
            self.recent_sum += x - transition
            self.recent_rows.append(x)

        self.observations += 1
        score = self._score()
        self.last_score = score
        self.score_detector.update(score)
        if len(self.recent_rows) == TOTAL_WINDOW and score >= REGIME_L1_THRESHOLD and self.cooldown == 0:
            self.detection_count += 1
            self.last_detection_step = self.observations
            self.cooldown = CONTEXT_COOLDOWN

    def _score(self) -> float:
        if len(self.recent_rows) < TOTAL_WINDOW:
            return 0.0
        ref = self.reference_sum / REFERENCE_WINDOW
        recent = self.recent_sum / RECENT_WINDOW
        return float(np.mean(np.abs(recent - ref)))

    @property
    def active(self) -> bool:
        return bool(len(self.recent_rows) == TOTAL_WINDOW and (self.last_score >= REGIME_L1_THRESHOLD or self.cooldown > 0))

    def factor_for_signal(self, name: str) -> float:
        if not self.active:
            return 1.0
        memory = signal_memory(name)
        return float(max(0.35, 1.0 / (1.0 + memory / 500.0)))

    def metrics(self) -> dict[str, Any]:
        return {
            'schema': 'SMART_CONTEXT_REGIME_1',
            'observations': self.observations,
            'recent_window': RECENT_WINDOW,
            'reference_window': REFERENCE_WINDOW,
            'l1_score': self.last_score,
            'l1_threshold': REGIME_L1_THRESHOLD,
            'active': self.active,
            'detection_count': self.detection_count,
            'last_detection_step': self.last_detection_step,
            'cooldown': self.cooldown,
            'river_adwin_width': int(self.score_detector.width),
            'river_adwin_estimation': float(self.score_detector.estimation),
            'river_adwin_drift_detected': bool(self.score_detector.drift_detected),
            'calibration_id': CALIBRATION_ID,
            'causal': True,
        }
