from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from river import drift

EXPECTED_HITS = 0.6
DRIFT_COOLDOWN = 25
RECENT_WINDOW = 100
PROFILE_DIMENSIONS = 60
PROFILE_PROJECTION_COUNT = 4
PROFILE_MIN_PROJECTION_ALERTS = 2
PROFILE_CONSENSUS_HORIZON = 128
PROFILE_BURN_IN = 75
PROFILE_SEED = 20260828
PROFILE_DRIFT_HEALTH = 0.70
PERFORMANCE_DRIFT_HEALTH = 0.50


def _build_projections() -> np.ndarray:
    rng = np.random.default_rng(PROFILE_SEED)
    P = rng.normal(size=(PROFILE_PROJECTION_COUNT, PROFILE_DIMENSIONS))
    P -= P.mean(axis=1, keepdims=True)
    scale = np.sum(np.abs(P), axis=1, keepdims=True)
    return np.divide(P, scale, out=np.zeros_like(P), where=scale > 0)


PROFILE_PROJECTIONS = _build_projections()


def _profile_detectors():
    return [drift.ADWIN(delta=0.002) for _ in range(PROFILE_PROJECTION_COUNT)]


@dataclass
class SignalQualityState:
    name: str
    family: str
    n: int = 0
    mean_hits: float = 0.0
    m2_hits: float = 0.0
    performance_drift_count: int = 0
    performance_drift_cooldown: int = 0
    last_performance_drift_step: int | None = None
    profile_n: int = 0
    profile_drift_count: int = 0
    profile_drift_dimensions_total: int = 0
    profile_drift_cooldown: int = 0
    last_profile_drift_step: int | None = None
    recent_hits: deque = field(default_factory=lambda: deque(maxlen=RECENT_WINDOW), repr=False)
    detector: Any = field(default_factory=lambda: drift.ADWIN(delta=0.002), repr=False)
    profile_detectors: list = field(default_factory=_profile_detectors, repr=False)
    profile_alert_cooldowns: list[int] = field(default_factory=lambda: [0] * PROFILE_PROJECTION_COUNT, repr=False)
    last_profile_projection_values: list[float] = field(default_factory=list, repr=False)

    def update_profile(self, values) -> int:
        arr = np.asarray(values, dtype=float)
        if arr.shape != (PROFILE_DIMENSIONS,):
            raise ValueError('signal profile must contain exactly 60 values')
        if not np.all(np.isfinite(arr)):
            raise ValueError('signal profile contains non-finite values')
        if self.profile_drift_cooldown > 0:
            self.profile_drift_cooldown -= 1
        self.profile_alert_cooldowns = [max(0, x - 1) for x in self.profile_alert_cooldowns]
        self.profile_n += 1

        projected = PROFILE_PROJECTIONS @ arr
        self.last_profile_projection_values = [float(x) for x in projected]
        for i, (detector, value) in enumerate(zip(self.profile_detectors, projected)):
            detector.update(float(value))
            if self.profile_n >= PROFILE_BURN_IN and detector.drift_detected:
                self.profile_alert_cooldowns[i] = PROFILE_CONSENSUS_HORIZON

        active_alerts = sum(x > 0 for x in self.profile_alert_cooldowns)
        accepted = bool(
            self.profile_n >= PROFILE_BURN_IN
            and self.profile_drift_cooldown == 0
            and active_alerts >= PROFILE_MIN_PROJECTION_ALERTS
        )
        if accepted:
            self.profile_drift_count += 1
            self.profile_drift_dimensions_total += active_alerts
            self.profile_drift_cooldown = DRIFT_COOLDOWN
            self.last_profile_drift_step = self.profile_n
            self.profile_alert_cooldowns = [0] * PROFILE_PROJECTION_COUNT
        return active_alerts if accepted else 0

    def update(self, hits: int) -> None:
        if not 0 <= int(hits) <= 6:
            raise ValueError('hits must be in [0, 6]')
        if self.performance_drift_cooldown > 0:
            self.performance_drift_cooldown -= 1
        self.n += 1
        delta = float(hits) - self.mean_hits
        self.mean_hits += delta / self.n
        self.m2_hits += delta * (float(hits) - self.mean_hits)
        self.recent_hits.append(float(hits))
        self.detector.update(float(hits) / 6.0)
        if self.detector.drift_detected:
            self.performance_drift_count += 1
            self.performance_drift_cooldown = DRIFT_COOLDOWN
            self.last_performance_drift_step = self.n

    @property
    def std_hits(self) -> float:
        return math.sqrt(self.m2_hits / (self.n - 1)) if self.n > 1 else 0.0

    def metrics(self, redundancy: float, freshness: float = 1.0) -> dict[str, Any]:
        recent = np.asarray(self.recent_hits, dtype=float)
        recent_mean = float(recent.mean()) if len(recent) else EXPECTED_HITS
        recent_std = float(recent.std(ddof=1)) if len(recent) > 1 else 0.0
        recent_excess = recent_mean - EXPECTED_HITS
        learned_utility = math.exp(max(-2.0, min(2.0, 0.8 * recent_excess)))
        stability = 1.0 / (1.0 + recent_std)
        perf_score = 1.0 / (1.0 + math.exp(-2.0 * recent_excess))
        performance_drift_active = self.performance_drift_cooldown > 0
        profile_drift_active = self.profile_drift_cooldown > 0
        drift_active = performance_drift_active or profile_drift_active
        drift_health = min(
            PERFORMANCE_DRIFT_HEALTH if performance_drift_active else 1.0,
            PROFILE_DRIFT_HEALTH if profile_drift_active else 1.0,
        )
        quality = max(0.05, min(1.0, 0.45 * stability + 0.35 * perf_score + 0.20 * drift_health))
        sample_conf = 1.0 - math.exp(-self.n / 100.0)
        confidence = max(0.10, min(1.0, 0.15 + 0.85 * sample_conf * stability))
        context = drift_health
        redundancy = max(0.05, min(1.0, float(redundancy)))
        freshness = max(0.0, min(1.0, float(freshness)))
        quality *= freshness
        widths = [int(d.width) for d in self.profile_detectors]
        estimations = [float(d.estimation) for d in self.profile_detectors]
        return {
            'n_oos': self.n,
            'profile_observations': self.profile_n,
            'oos_mean_hits': self.mean_hits,
            'oos_excess_vs_uniform': self.mean_hits - EXPECTED_HITS if self.n else 0.0,
            'recent_mean_hits': recent_mean,
            'recent_excess_vs_uniform': recent_excess,
            'recent_std_hits': recent_std,
            'stability': stability,
            'freshness': freshness,
            'redundancy_penalty': redundancy,
            'performance_drift_count': self.performance_drift_count,
            'profile_drift_count': self.profile_drift_count,
            'profile_drift_dimensions_total': self.profile_drift_dimensions_total,
            'drift_count': self.performance_drift_count + self.profile_drift_count,
            'performance_drift_cooldown': self.performance_drift_cooldown,
            'profile_drift_cooldown': self.profile_drift_cooldown,
            'last_performance_drift_step': self.last_performance_drift_step,
            'last_profile_drift_step': self.last_profile_drift_step,
            'profile_active_projection_alerts': sum(x > 0 for x in self.profile_alert_cooldowns),
            'drift_active': drift_active,
            'performance_drift_active': performance_drift_active,
            'profile_drift_active': profile_drift_active,
            'drift_health': drift_health,
            'adwin_width': int(self.detector.width),
            'adwin_estimation': float(self.detector.estimation),
            'profile_adwin_min_width': min(widths) if widths else 0,
            'profile_adwin_mean_width': float(np.mean(widths)) if widths else 0.0,
            'profile_adwin_estimations': estimations,
            'profile_projection_values': list(self.last_profile_projection_values),
            'profile_projection_seed': PROFILE_SEED,
            'profile_drift_penalty_enabled': True,
            'utility': learned_utility,
            'quality': quality,
            'confidence': confidence,
            'context': context,
        }

    def audit_state(self, redundancy: float = 1.0) -> dict[str, Any]:
        return {'name': self.name, 'family': self.family, **self.metrics(redundancy)}
