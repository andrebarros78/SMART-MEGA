"""Regression: effective expert cap must survive redundancy normalization.

Synthetic data checks a mathematical invariant only; it does not establish
predictive skill or license changing any frozen lottery card.
"""
from __future__ import annotations

import numpy as np
import smart_v2_engine as engine


def test_effective_frequency_expert_cap_survives_redundancy(monkeypatch):
    """Old walk_forward normalizes penalized weights after enforcing the cap."""
    names = ("freq1000", "freq25", "freq50", "ewma10")
    scores = np.linspace(0.0, 1.0, 60)
    pre = {name: np.stack([scores, scores], axis=0) for name in names}

    def deterministic_penalties(signals):
        return (
            {"freq1000": 1.0, "freq25": 0.15, "freq50": 0.15, "ewma10": 1.0},
            np.eye(len(signals)),
        )

    monkeypatch.setattr(engine, "redundancy_penalty", deterministic_penalties)
    draws = np.array([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]], dtype=int)
    contests = np.array([3073, 3074], dtype=int)
    replay = engine.walk_forward(draws, contests, start=1, pre=pre, allowed=names)
    actual = replay.rows[0]
    family_weight = actual["family_weights"]["freq"]
    relative_weight = actual["weights"]["freq1000"] / family_weight
    assert relative_weight <= engine.EXPERT_CAP_WITHIN_FAMILY + 1e-12
    assert abs(sum(actual["weights"].values()) - 1.0) < 1e-12
    assert len(actual["top6"]) == len(set(actual["top6"])) == 6


def test_redundancy_cap_preserves_weights_when_penalties_are_neutral(monkeypatch):
    names = ("freq1000", "freq25", "freq50", "ewma10")
    scores = np.linspace(1.0, 2.0, 60)
    pre = {name: np.stack([scores, scores], axis=0) for name in names}
    monkeypatch.setattr(
        engine, "redundancy_penalty",
        lambda signals: ({name: 1.0 for name in names}, np.eye(len(names))),
    )
    draws = np.array([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]], dtype=int)
    contests = np.array([3073, 3074], dtype=int)
    replay = engine.walk_forward(draws, contests, start=1, pre=pre, allowed=names)
    row = replay.rows[0]
    family_weight = row["family_weights"]["freq"]
    within = [
        row["weights"][name] / family_weight
        for name in names if name.startswith("freq")
    ]
    assert max(within) <= engine.EXPERT_CAP_WITHIN_FAMILY + 1e-12
    assert abs(sum(within) - 1.0) < 1e-12
