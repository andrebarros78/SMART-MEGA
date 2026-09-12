from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smart_champion_challenger as cc
import smart_learning_activation_authority as aa

ROOT = Path(__file__).resolve().parent


def _dataset(n: int = 35, seed: int = 991) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for contest in range(1, n + 1):
        draw = np.sort(rng.choice(np.arange(1, 61), 6, replace=False))
        rows.append({"Concurso": contest, **{f"Bola{i + 1}": int(draw[i]) for i in range(6)}})
    return pd.DataFrame(rows)


def test_materiality_evidence_all_fail_closed_validation_branches():
    valid = aa.build_materiality_evidence(
        decision_change_count=1,
        validation_gain=1.0,
        holdout_gain=0.5,
        global_gain=0.25,
        independent_holdout=True,
        leakage_free=True,
    )
    cases = [
        ({"validation_gain": float("nan")}, "must be finite"),
        ({"holdout_gain": -0.01}, "regresses baseline"),
        ({"validation_gain": 0.0, "holdout_gain": 0.0, "global_gain": 0.0}, "positive gain"),
        ({"independent_holdout": False}, "independent holdout"),
        ({"leakage_free": False}, "leakage-free"),
        ({"sha256": "0" * 64}, "self-hash invalid"),
    ]
    for changes, pattern in cases:
        candidate = dict(valid)
        candidate.update(changes)
        with pytest.raises(ValueError, match=pattern):
            aa._validate_materiality_evidence(candidate)


def test_freeze_applies_valid_ai_hyperparameter_authority(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    data = tmp_path / "ai-valid.xlsx"
    _dataset().to_excel(data, index=False)
    effective = {"eta": 0.5, "redundancy_threshold": 0.80, "meta_strength": 0.03}
    monkeypatch.setattr(
        cc,
        "load_ai_hyperparameter_authority",
        lambda *args, **kwargs: {"effective_candidate": effective},
    )
    out = tmp_path / "freeze.json"
    result = cc.freeze_champion_challenger(
        data,
        36,
        out,
        tmp_path / "ledger.json",
        tmp_path / "state.json",
        start=20,
        enforce_temporal_guard=False,
    )
    assert result["status"] == "FROZEN"
    frozen = json.loads(out.read_text(encoding="utf-8"))
    assert frozen["ai_hyperparameter_authority"]["effective_candidate"] == effective


def test_freeze_propagates_unexpected_ai_authority_error(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    data = tmp_path / "ai-error.xlsx"
    _dataset(seed=992).to_excel(data, index=False)

    def fail(*args, **kwargs):
        raise ValueError("unexpected authority error")

    monkeypatch.setattr(cc, "load_ai_hyperparameter_authority", fail)
    with pytest.raises(ValueError, match="unexpected authority error"):
        cc.freeze_champion_challenger(
            data,
            36,
            tmp_path / "freeze.json",
            tmp_path / "ledger.json",
            tmp_path / "state.json",
            start=20,
            enforce_temporal_guard=False,
        )