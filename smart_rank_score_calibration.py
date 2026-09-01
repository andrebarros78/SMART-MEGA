from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

SCHEMA = 'SMART_RANK_SCORE_CALIBRATION_1'
N_NUMBERS = 60
DRAW_SIZE = 6
UNIFORM_PROB = DRAW_SIZE / N_NUMBERS
PRIOR_STRENGTH = 20.0
DEFAULT_CALIBRATION_STRENGTH = 0.0
CALIBRATION_POLICY_ID = 'P06_NEUTRALIZED_AFTER_FINAL_HOLDOUT_20260830'
EPS = 1e-15


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _validate_ranking(ranking60) -> list[int]:
    ranking = [int(x) for x in ranking60]
    if len(ranking) != N_NUMBERS or set(ranking) != set(range(1, N_NUMBERS + 1)):
        raise ValueError('ranking60 must be a permutation of 1..60')
    return ranking


def _validate_actual(actual_numbers) -> set[int]:
    actual = {int(x) for x in actual_numbers}
    if len(actual) != DRAW_SIZE or min(actual) < 1 or max(actual) > N_NUMBERS:
        raise ValueError('actual_numbers must contain six unique numbers in [1,60]')
    return actual


def _pava_nonincreasing(values, weights) -> np.ndarray:
    y = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if y.shape != (N_NUMBERS,) or w.shape != (N_NUMBERS,):
        raise ValueError('PAVA expects 60 values and 60 weights')
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(w)) or np.any(w <= 0):
        raise ValueError('PAVA inputs must be finite with positive weights')
    # Apply ordinary non-decreasing PAVA to -y, then negate.
    levels: list[float] = []
    masses: list[float] = []
    starts: list[int] = []
    ends: list[int] = []
    for i, (value, mass) in enumerate(zip(-y, w)):
        levels.append(float(value)); masses.append(float(mass)); starts.append(i); ends.append(i)
        while len(levels) >= 2 and levels[-2] > levels[-1] + EPS:
            m = masses[-2] + masses[-1]
            v = (levels[-2] * masses[-2] + levels[-1] * masses[-1]) / m
            levels[-2:] = [v]; masses[-2:] = [m]
            starts[-2:] = [starts[-2]]; ends[-2:] = [ends[-1]]
    out = np.zeros(N_NUMBERS, dtype=float)
    for level, start, end in zip(levels, starts, ends):
        out[start:end + 1] = -level
    return out


def brier_score(probabilities: dict[int, float] | dict[str, float], actual_numbers) -> float:
    actual = _validate_actual(actual_numbers)
    if len(probabilities) != N_NUMBERS:
        raise ValueError('probabilities must contain 60 numbers')
    vals = []
    for n in range(1, N_NUMBERS + 1):
        key = n if n in probabilities else str(n)
        if key not in probabilities:
            raise ValueError('probabilities must contain keys 1..60')
        p = float(probabilities[key])
        if not math.isfinite(p) or not 0.0 <= p <= 1.0:
            raise ValueError('probabilities must be finite in [0,1]')
        vals.append((p - (1.0 if n in actual else 0.0)) ** 2)
    return float(np.mean(vals))


@dataclass
class RankScoreCalibrator:
    strength: float = DEFAULT_CALIBRATION_STRENGTH
    prior_strength: float = PRIOR_STRENGTH
    observations: int = 0
    hits_by_rank: np.ndarray = field(default_factory=lambda: np.zeros(N_NUMBERS, dtype=float), repr=False)
    trials_by_rank: np.ndarray = field(default_factory=lambda: np.zeros(N_NUMBERS, dtype=float), repr=False)
    cumulative_brier: float = 0.0
    cumulative_uniform_brier: float = 0.0

    def __post_init__(self):
        self.strength = float(self.strength)
        self.prior_strength = float(self.prior_strength)
        if not math.isfinite(self.strength) or not 0.0 <= self.strength <= 1.0:
            raise ValueError('strength must be in [0,1]')
        if not math.isfinite(self.prior_strength) or self.prior_strength <= 0:
            raise ValueError('prior_strength must be positive')

    def isotonic_posterior_by_rank(self) -> np.ndarray:
        raw = self.raw_posterior_by_rank()
        mass = self.trials_by_rank + self.prior_strength
        return _pava_nonincreasing(raw, mass)

    def posterior_by_rank(self) -> np.ndarray:
        iso = self.isotonic_posterior_by_rank()
        calibrated = UNIFORM_PROB + self.strength * (iso - UNIFORM_PROB)
        return np.clip(calibrated, 0.0, 1.0)

    def raw_posterior_by_rank(self) -> np.ndarray:
        return (self.hits_by_rank + self.prior_strength * UNIFORM_PROB) / (self.trials_by_rank + self.prior_strength)

    def predict(self, ranking60, aggregate_scores: dict[str, float] | dict[int, float] | None = None) -> tuple[dict[str, float], dict[str, Any]]:
        ranking = _validate_ranking(ranking60)
        if aggregate_scores is not None:
            if len(aggregate_scores) != N_NUMBERS:
                raise ValueError('aggregate_scores must contain 60 values')
            score_values = []
            for n in range(1, N_NUMBERS + 1):
                key = n if n in aggregate_scores else str(n)
                if key not in aggregate_scores:
                    raise ValueError('aggregate_scores must contain keys 1..60')
                x = float(aggregate_scores[key])
                if not math.isfinite(x):
                    raise ValueError('aggregate_scores must be finite')
                score_values.append(x)
        else:
            score_values = []

        raw = self.raw_posterior_by_rank()
        isotonic = self.isotonic_posterior_by_rank()
        calibrated = self.posterior_by_rank()
        probabilities = {str(number): float(calibrated[rank]) for rank, number in enumerate(ranking)}
        violations = int(np.sum(raw[:-1] < raw[1:] - EPS))
        spread = float(calibrated[0] - calibrated[-1])
        audit = {
            'schema': SCHEMA,
            'observations': int(self.observations),
            'strength': float(self.strength),
            'prior_strength': float(self.prior_strength),
            'uniform_probability': UNIFORM_PROB,
            'raw_posterior_by_rank': [float(x) for x in raw],
            'isotonic_probability_by_rank': [float(x) for x in isotonic],
            'calibrated_probability_by_rank': [float(x) for x in calibrated],
            'monotonic_violations_before_isotonic': violations,
            'monotonic_after_isotonic': bool(np.all(calibrated[:-1] >= calibrated[1:] - EPS)),
            'top_bottom_probability_spread': spread,
            'neutralized': bool(self.strength <= EPS or spread <= EPS),
            'calibration_mode': 'NEUTRALIZED' if self.strength <= EPS else 'SHRUNK_ISOTONIC',
            'policy_id': CALIBRATION_POLICY_ID,
            'probability_sum': float(calibrated.sum()),
            'cumulative_brier': float(self.cumulative_brier),
            'cumulative_uniform_brier': float(self.cumulative_uniform_brier),
            'mean_brier': float(self.cumulative_brier / self.observations) if self.observations else None,
            'mean_uniform_brier': float(self.cumulative_uniform_brier / self.observations) if self.observations else None,
            'aggregate_score_range': None if not score_values else [float(min(score_values)), float(max(score_values))],
            'causal_semantics': 'rank frequencies are updated only after each observed result; current prediction uses prior outcomes only',
        }
        audit['sha256'] = sha256_json(audit)
        return probabilities, audit

    def update(self, ranking60, actual_numbers, predicted_probabilities: dict[str, float] | dict[int, float] | None = None) -> dict[str, Any]:
        ranking = _validate_ranking(ranking60)
        actual = _validate_actual(actual_numbers)
        if predicted_probabilities is None:
            predicted_probabilities, _ = self.predict(ranking)
        score = brier_score(predicted_probabilities, actual)
        uniform = {str(n): UNIFORM_PROB for n in range(1, N_NUMBERS + 1)}
        uniform_score = brier_score(uniform, actual)
        for rank, number in enumerate(ranking):
            self.trials_by_rank[rank] += 1.0
            if number in actual:
                self.hits_by_rank[rank] += 1.0
        self.observations += 1
        self.cumulative_brier += score
        self.cumulative_uniform_brier += uniform_score
        return {'brier': score, 'uniform_brier': uniform_score, 'delta_vs_uniform': score - uniform_score}

    def state(self) -> dict[str, Any]:
        raw = self.raw_posterior_by_rank(); isotonic = self.isotonic_posterior_by_rank(); calibrated = self.posterior_by_rank()
        payload = {
            'schema': SCHEMA,
            'strength': float(self.strength),
            'calibration_mode': 'NEUTRALIZED' if self.strength <= EPS else 'SHRUNK_ISOTONIC',
            'policy_id': CALIBRATION_POLICY_ID,
            'prior_strength': float(self.prior_strength),
            'observations': int(self.observations),
            'hits_by_rank': [float(x) for x in self.hits_by_rank],
            'trials_by_rank': [float(x) for x in self.trials_by_rank],
            'raw_posterior_by_rank': [float(x) for x in raw],
            'isotonic_probability_by_rank': [float(x) for x in isotonic],
            'calibrated_probability_by_rank': [float(x) for x in calibrated],
            'monotonic_violations_before_isotonic': int(np.sum(raw[:-1] < raw[1:] - EPS)),
            'monotonic_after_isotonic': bool(np.all(calibrated[:-1] >= calibrated[1:] - EPS)),
            'probability_sum': float(calibrated.sum()),
            'cumulative_brier': float(self.cumulative_brier),
            'cumulative_uniform_brier': float(self.cumulative_uniform_brier),
            'mean_brier': float(self.cumulative_brier / self.observations) if self.observations else None,
            'mean_uniform_brier': float(self.cumulative_uniform_brier / self.observations) if self.observations else None,
        }
        payload['sha256'] = sha256_json(payload)
        return payload
