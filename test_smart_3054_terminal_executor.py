from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import smart_3054_terminal_executor as te


def _freeze(path: Path, top6=None):
    top6 = top6 or [10, 11, 27, 30, 35, 38]
    doc = {
        "target_contest": 3054,
        "cutoff_contest": 3053,
        "frozen_before_result": True,
        "causal_cutoff": True,
        "champion_remains_active": True,
        "production_switch_performed": False,
        "champion": {"top6": top6},
        "challenger": {"top6": top6},
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return doc


def _ledger(freeze_path: Path, freeze_sha: str, actual, hits, *, retroactive=False, extra_adjudications=0):
    freeze_event = {
        "event_type": "FREEZE",
        "target_contest": 3054,
        "cutoff_contest": 3053,
        "frozen_before_result": True,
        "causal_cutoff": True,
        "freeze_file": str(freeze_path),
        "freeze_sha256": freeze_sha,
    }
    events = [freeze_event, {
        "event_type": "ADJUDICATION",
        "target_contest": 3054,
        "freeze_sha256": freeze_sha,
        "actual_numbers": actual,
        "champion_hits": hits,
        "challenger_hits": hits,
        "retroactive_rewrite": retroactive,
    }]
    for index in range(extra_adjudications):
        events.append({"event_type": "ADJUDICATION", "target_contest": 3000 + index})
    return {"schema": "SMART_SIGNAL_LEDGER_1", "events": events}


def _consensus(actual, corroborated=True):
    return {
        "target_contest": 3054,
        "primary": {"validated": True, "numbers": actual, "draw_date": "05/09/2026"},
        "status": "DUAL_CAIXA_CHANNEL_CONSENSUS" if corroborated else "PRIMARY_CAIXA_API_VALID_SECONDARY_DOWNLOAD_STALE",
        "terminal_source_corroboration_authorized": corroborated,
    }


def _audit(pair_count):
    return {
        "status": "PASS",
        "prospective_ledger": {
            "status": "PASS",
            "pair_count": pair_count,
            "no_future_leakage": True,
        },
    }


def _sequence():
    return {"valid": True, "proof_recorded": True, "sequence_sha256": "a" * 64}


def test_terminal_rule_miss_remains_active(tmp_path: Path, monkeypatch):
    freeze_path = tmp_path / "freeze.json"
    _freeze(freeze_path)
    sha = te.sha256_file(freeze_path)
    monkeypatch.setattr(te, "EXPECTED_FREEZE_SHA256", sha)
    actual = [1, 2, 3, 4, 5, 6]
    ledger = _ledger(freeze_path, sha, actual, 0)
    out = te.evaluate_terminal_rule(tmp_path, ledger, _consensus(actual), _audit(1), _sequence())
    assert out["status"] == "MISSION_ACTIVE_RESULT_ADJUDICATED_NO_6OF6"
    assert out["eligible_for_mission_proven"] is False
    assert out["checks"]["all_attempts_counted"] is True


def test_terminal_rule_exact_6of6_requires_source_corroboration(tmp_path: Path, monkeypatch):
    freeze_path = tmp_path / "freeze.json"
    top6 = [10, 11, 27, 30, 35, 38]
    _freeze(freeze_path, top6)
    sha = te.sha256_file(freeze_path)
    monkeypatch.setattr(te, "EXPECTED_FREEZE_SHA256", sha)
    ledger = _ledger(freeze_path, sha, top6, 6)
    out = te.evaluate_terminal_rule(tmp_path, ledger, _consensus(top6, False), _audit(1), _sequence())
    assert out["status"] == "MISSION_ACTIVE_6OF6_PENDING_SOURCE_CORROBORATION"
    assert out["eligible_for_mission_proven"] is False
    assert out["checks"]["exact_6of6"] is True


def test_terminal_rule_exact_6of6_all_guards_is_eligible(tmp_path: Path, monkeypatch):
    freeze_path = tmp_path / "freeze.json"
    top6 = [10, 11, 27, 30, 35, 38]
    _freeze(freeze_path, top6)
    sha = te.sha256_file(freeze_path)
    monkeypatch.setattr(te, "EXPECTED_FREEZE_SHA256", sha)
    ledger = _ledger(freeze_path, sha, top6, 6)
    out = te.evaluate_terminal_rule(tmp_path, ledger, _consensus(top6, True), _audit(1), _sequence())
    assert out["status"] == "MISSION_PROVEN_ELIGIBLE"
    assert out["eligible_for_mission_proven"] is True
    assert all(out["checks"].values())


def test_terminal_rule_refuses_uncounted_attempts_and_retroactive_event(tmp_path: Path, monkeypatch):
    freeze_path = tmp_path / "freeze.json"
    top6 = [10, 11, 27, 30, 35, 38]
    _freeze(freeze_path, top6)
    sha = te.sha256_file(freeze_path)
    monkeypatch.setattr(te, "EXPECTED_FREEZE_SHA256", sha)
    ledger = _ledger(freeze_path, sha, top6, 6, retroactive=True)
    out = te.evaluate_terminal_rule(tmp_path, ledger, _consensus(top6), _audit(0), _sequence())
    assert out["eligible_for_mission_proven"] is False
    assert out["checks"]["all_attempts_counted"] is False
    assert out["checks"]["retroactive_rewrite_absent"] is False


def test_consensus_upgrade_is_monotonic_and_conflict_fails(tmp_path: Path):
    actual = [10, 11, 27, 30, 35, 38]
    stale = _consensus(actual, False)
    dual = _consensus(actual, True)
    first = te._ensure_monotonic_consensus(tmp_path, stale)
    assert first["terminal_source_corroboration_authorized"] is False
    upgraded = te._ensure_monotonic_consensus(tmp_path, dual)
    assert upgraded["terminal_source_corroboration_authorized"] is True
    preserved = te._ensure_monotonic_consensus(tmp_path, stale)
    assert preserved["terminal_source_corroboration_authorized"] is True
    conflict = _consensus([1, 2, 3, 4, 5, 6], True)
    with pytest.raises(ValueError, match="primary observation changed"):
        te._ensure_monotonic_consensus(tmp_path, conflict)


def test_probe_before_result_is_write_free(tmp_path: Path, monkeypatch):
    freeze_path = tmp_path / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json"
    _freeze(freeze_path)
    monkeypatch.setattr(te, "EXPECTED_FREEZE_SHA256", te.sha256_file(freeze_path))
    (tmp_path / "SMART_SIGNAL_LEDGER.json").write_text(json.dumps({"schema": "SMART_SIGNAL_LEDGER_1", "events": []}), encoding="utf-8")
    monkeypatch.setattr(te.preflight, "build_preflight", lambda root: {"readiness_status": "PASS"})

    def unavailable(_target):
        raise RuntimeError("not drawn")

    result = te.probe(tmp_path, fetcher=unavailable)
    assert result["status"] == "WAITING_OFFICIAL_RESULT"
    assert result["canonical_writes_performed"] is False
    assert not (tmp_path / te.PRIMARY_PAYLOAD).exists()
    assert not (tmp_path / te.CONSENSUS_FILE).exists()


def _frame(contests):
    rows = []
    for contest in contests:
        row = {"Concurso": contest, "Data do Sorteio": pd.Timestamp("2026-09-01")}
        for index, number in enumerate([1, 2, 3, 4, 5, 6], 1):
            row[f"Bola{index}"] = number
        rows.append(row)
    return pd.DataFrame(rows)


def test_result_store_advance_is_atomic_and_idempotent(tmp_path: Path):
    canonical = tmp_path / "Mega-Sena.xlsx"
    through = tmp_path / te.RESULT_DATA
    _frame([3052, 3053]).to_excel(canonical, index=False)
    _frame([3052, 3053, 3054]).to_excel(through, index=False)
    proof = te._advance_canonical_result_store(tmp_path)
    assert proof["status"] == "PASS"
    assert te._contest_max(canonical) == 3054
    second = te._advance_canonical_result_store(tmp_path)
    assert second["canonical_sha256_after"] == proof["canonical_sha256_after"]


def test_terminal_promotion_requires_eligible_evaluation(tmp_path: Path):
    with pytest.raises(ValueError, match="fully eligible"):
        te._promote_terminal_mission(tmp_path, {"eligible_for_mission_proven": False}, {}, {}, {})
