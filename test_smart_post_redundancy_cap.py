"""ECC shadow regression: enforce the expert limit after redundancy penalties.

Changes here are candidate-only until independent historical/prospective proof.
"""
import numpy as np
import pytest

import smart_v2_engine as e
from freeze_next_research import current_policy


def _fixture():
    draws = np.tile(np.arange(1, 7), (50, 1))
    names = [f"freq{w}" for w in e.FREQ_WINDOWS] + ["freq_global"] + [
        f"ewma{s}" for s in e.EWMA_SPANS
    ]
    signals = {}
    for name in names:
        score = np.zeros((len(draws) + 1, 60), dtype=float)
        if name == "freq1000":
            score[:, :6] = 1.0
        else:
            score[:, 54:] = 1.0
        signals[name] = score
    return draws, signals


def _predict(monkeypatch, *, penalties):
    draws, signals = _fixture()
    monkeypatch.setattr(e, "precompute_scores", lambda x: signals)
    monkeypatch.setattr(
        e, "redundancy_penalty",
        lambda sc: ({name: penalties(name) for name in sc}, np.eye(len(sc))),
    )
    return current_policy(draws, start=1)


def test_post_redundancy_expert_cap_is_enforced(monkeypatch):
    pred = _predict(
        monkeypatch,
        penalties=lambda name: 1.0 if name == "freq1000" else 0.15,
    )
    family_mass = pred["family_weights"]["freq"]
    expert_mass = pred["expert_weights"]["freq1000"]
    assert abs(expert_mass / family_mass - e.EXPERT_CAP_WITHIN_FAMILY) < 1e-12
    assert abs(sum(pred["expert_weights"].values()) - 1.0) < 1e-12
    assert all(weight >= 0.0 for weight in pred["expert_weights"].values())


def test_equal_redundancy_penalties_preserve_preexisting_caps(monkeypatch):
    pred = _predict(monkeypatch, penalties=lambda name: 1.0)
    families = pred["family_weights"]
    for name, weight in pred["expert_weights"].items():
        assert weight <= families[e.family_of(name)] * e.EXPERT_CAP_WITHIN_FAMILY + 1e-12


def test_candidate_outputs_complete_card_and_ranked_scores(monkeypatch):
    pred = _predict(
        monkeypatch,
        penalties=lambda name: 1.0 if name == "freq1000" else 0.15,
    )
    assert len(pred["top6"]) == len(set(pred["top6"])) == 6
    assert sorted(pred["ranking60"]) == list(range(1, 61))
    assert set(pred["aggregate_scores"]) == set(map(str, range(1, 61)))
