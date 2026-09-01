from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from river import drift

N_NUMBERS = 60
RECENT_WINDOW = 75
REFERENCE_WINDOW = 150
TOTAL_WINDOW = RECENT_WINDOW + REFERENCE_WINDOW
REGIME_L1_THRESHOLD = 0.049
CONTEXT_COOLDOWN = 25

# Fixed before final 2,000-run validation. Calibrated only on disjoint synthetic seeds.
CALIBRATION_ID = 'SMART_CONTEXT_CAL_20260828_B'


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
    recent_rows: deque = field(default_factory=lambda: deque(maxlen=TOTAL_WINDOW), repr=False)
    observations: int = 0
    detection_count: int = 0
    last_detection_step: int | None = None
    cooldown: int = 0
    last_score: float = 0.0
    score_detector: Any = field(default_factory=lambda: drift.ADWIN(delta=0.002), repr=False)

    def update(self, draw) -> None:
        if self.cooldown > 0:
            self.cooldown -= 1
        self.recent_rows.append(_onehot_draw(draw))
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
        M = np.asarray(self.recent_rows, dtype=float)
        ref = M[:REFERENCE_WINDOW].mean(axis=0)
        recent = M[REFERENCE_WINDOW:].mean(axis=0)
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
