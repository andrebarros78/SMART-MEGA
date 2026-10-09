"""Calibrated probability evidence: fail closed without rewriting past reports."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from smart_calibration_safety_gate import (
    _digest, evaluate, historical_baseline, verify_freeze_calibration,
)


ROOT = Path(__file__).resolve().parent


def _frozen_3068_evidence() -> tuple[dict, Path]:
    """Resolve immutable epoch evidence, whether live or canonically archived."""
    epoch_id = "operator-3068-acc6a34c9e27-20261008T222652499219Z"
    live = ROOT / "runtime" / "learning_epochs" / epoch_id
    archived = ROOT / "SMART_STATE_ARCHIVE" / "adjudicated-epochs" / "3068" / epoch_id / "epoch"
    parent = live if (live / "FULL_PROCESS_PROOF.json").is_file() else archived
    proof = json.loads((parent / "FULL_PROCESS_PROOF.json").read_text(encoding="utf-8-sig"))
    source = parent / "SMART_3068_CHAMPION_CHALLENGER_FREEZE.json"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == proof["freeze_sha256"]
    return proof, source


def _isolated_freeze(tmp_path: Path, *, strength: float = 0.0,
                     level: float = 0.1, policy: str | None = None):
    p, source = _frozen_3068_evidence()
    original = json.loads(source.read_text(encoding="utf-8-sig"))
    freeze = deepcopy(original)
    c = freeze["challenger"]["rank_score_calibration"]
    c["strength"] = strength
    c["neutralized"] = strength == 0
    c["calibration_mode"] = "NEUTRALIZED" if strength == 0 else "SHRUNK_ISOTONIC"
    if policy is not None:
        c["policy_id"] = policy
    c["probabilities_by_number"] = {str(i):level for i in range(1, 61)}
    c["probability_sum"] = sum(c["probabilities_by_number"].values())
    freeze["promotion_lineage"]["calibration_strength"] = strength
    body = dict(c)
    body.pop("probabilities_by_number", None)
    body.pop("sha256", None)
    c["sha256"] = _digest(body)
    rel = "runtime/learning_epochs/test/FREEZE.json"
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(freeze, ensure_ascii=False), encoding="utf-8")
    p.update({"freeze_file": rel, "freeze_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return p, freeze


def test_original_historical_candidate_failure_remains_visible():
    d = historical_baseline(ROOT)
    assert d["rejected_candidate_strength"] == 0.5
    assert d["rejected_final_holdout_n"] == 250
    assert d["rejected_final_holdout_brier"] > d["uniform_final_holdout_brier"]
    assert d["adopted_strength"] == 0.0
    assert d["adopted_delta_vs_uniform"] == 0.0


def test_existing_frozen_3068_is_prospectively_neutralized(tmp_path):
    proof, _ = _isolated_freeze(tmp_path)
    result = verify_freeze_calibration(tmp_path, proof)
    assert result["target_contest"] == 3068
    assert result["cutoff_contest"] == 3067
    assert result["production_brier_reference"] == 0.09
    assert result["all_60_probabilities_uniform"]
    assert result["future_result_used"] is False


def test_f13_audit_preserves_rejected_history_and_no_superiority_claim():
    report = json.loads((ROOT / "SMART_F13_CALIBRATION_SAFETY.json").read_text(encoding="utf-8-sig"))
    signature = report["sha256"]
    assert _digest({k: v for k, v in report.items() if k != "sha256"}) == signature
    assert report["status"] == "PASS"
    assert not report["prospective_superiority_proven"]
    assert not report["six_of_six_proven"]
    assert report["historical_evidence"] == historical_baseline(ROOT)
    _, source = _frozen_3068_evidence()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == report["production_evidence"]["freeze_sha256"]


@pytest.mark.parametrize("strength,level,policy", [
    (0.5, 0.1, None),
    (0.25, 0.1, None),
    (0.0, 0.101, None),
    (0.0, 0.1, "UNAPPROVED_POLICY"),
])
def test_rejects_unproved_calibration_even_if_freeze_hash_is_consistent(tmp_path, strength, level, policy):
    proof, _ = _isolated_freeze(tmp_path, strength=strength, level=level, policy=policy)
    with pytest.raises(ValueError, match="unproved|uniform"):
        verify_freeze_calibration(tmp_path, proof)


def test_accepts_valid_isolated_neutralized_freeze(tmp_path):
    proof, _ = _isolated_freeze(tmp_path)
    out = verify_freeze_calibration(tmp_path, proof)
    assert out["all_60_probabilities_uniform"]
    assert out["target_contest"] == 3068


def test_rejects_modified_calibration_without_matching_freeze_hash(tmp_path):
    proof, freeze = _isolated_freeze(tmp_path)
    freeze["challenger"]["rank_score_calibration"]["probabilities_by_number"]["1"] = 0.99
    (tmp_path / proof["freeze_file"]).write_text(json.dumps(freeze), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_freeze_calibration(tmp_path, proof)


def test_rejects_future_result_or_invalid_cutoff(tmp_path):
    proof, _ = _isolated_freeze(tmp_path)
    proof["result_used"] = True
    with pytest.raises(ValueError, match="future results"):
        verify_freeze_calibration(tmp_path, proof)
    proof["result_used"] = False
    proof["cutoff_contest"] = 3066
    with pytest.raises(ValueError, match="cutoff"):
        verify_freeze_calibration(tmp_path, proof)


def test_rejects_tampered_p06_archival_reference(tmp_path):
    for name in ("SMART_P06_FINAL_HOLDOUT.json", "SMART_P06_NEUTRALIZED_VALIDATION.json",
                 "SMART_P06_DECISION.json"):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    p = tmp_path / "SMART_P06_FINAL_HOLDOUT.json"
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    data["final_holdout"]["mean_brier"] = 0.089
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="self-hash"):
        historical_baseline(tmp_path)
