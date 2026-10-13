from __future__ import annotations

import hashlib
import json
from pathlib import Path

from smart_visual_learning_shadow import _hash_json, inspect_visual_learning_shadow


def _fixture(root: Path, target: int = 3069, contests: list[int] | None = None):
    contests = contests or [3066, 3067, 3068]
    doc = {
        "schema": "SMART_VISUAL_LEARNING_STATE_V1",
        "next_contest": str(target),
        "extractor_version": "1.3.1",
        "source_host": "youtube.com",
        "hypothesis_id": None,
        "observation_prior": {
            "status": "ACTIVE",
            "active": True,
            "predictive_evidence": "NOT_ESTABLISHED",
        },
        "training_contests": contests,
        "training_sha256": {str(n): hashlib.sha256(str(n).encode()).hexdigest() for n in contests},
        "training_observations": len(contests),
        "promotion_authorized": False,
        "same_contest_predictive_weight_authorized": False,
        "predictive_evidence": "NOT_ESTABLISHED",
    }
    doc["sha256"] = _hash_json(doc)
    p = root / "runtime" / "video_observation" / "SMART_VISUAL_LEARNING_STATE.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p, doc


def test_shadow_absent_never_blocks_or_promotes(tmp_path):
    result = inspect_visual_learning_shadow(tmp_path, 3069, 3068)
    assert result["status"] == "UNAVAILABLE"
    assert result["production_influence"] is False
    assert result["probability_weights_changed"] is False


def test_shadow_accepts_prior_checkpoint_provenance_without_predictive_use(tmp_path):
    _fixture(tmp_path)
    state = inspect_visual_learning_shadow(tmp_path, 3069, 3068)
    assert state["status"] == "SHADOW_AVAILABLE"
    assert state["training_observations"] == 3
    assert state["training_contests"] == [3066, 3067, 3068]
    assert state["production_influence"] is False
    assert state["candidate_ranking_changed"] is False
    assert state["predictive_evidence"] == "NOT_ESTABLISHED"
    assert len(state["source_file_sha256"]) == 64


def test_shadow_rejects_leakage_and_weight_promotion(tmp_path):
    path, doc = _fixture(tmp_path)
    doc["training_contests"].append(3069)
    doc["training_sha256"]["3069"] = hashlib.sha256(b"3069").hexdigest()
    doc["training_observations"] += 1
    doc["sha256"] = _hash_json({k: v for k, v in doc.items() if k != "sha256"})
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert inspect_visual_learning_shadow(tmp_path, 3069, 3068)["status"] == "REJECTED_CAUSALITY"

    doc["training_contests"].remove(3069)
    doc["training_sha256"].pop("3069")
    doc["training_observations"] -= 1
    doc["promotion_authorized"] = True
    doc["sha256"] = _hash_json({k: v for k, v in doc.items() if k != "sha256"})
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert inspect_visual_learning_shadow(tmp_path, 3069, 3068)["status"] == "REJECTED_CAUSALITY"


def test_shadow_rejects_tampered_or_wrong_target(tmp_path):
    path, doc = _fixture(tmp_path)
    doc["observation_prior"]["status"] = "CANDIDATE"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert inspect_visual_learning_shadow(tmp_path, 3069, 3068)["status"] == "REJECTED_INTEGRITY"
    _fixture(tmp_path, target=3070)
    assert inspect_visual_learning_shadow(tmp_path, 3069, 3068)["status"] == "REJECTED_CAUSALITY"


def test_proof_records_shadow_only_after_card_selection():
    source = Path("smart_full_process_pipeline.py").read_text(encoding="utf-8")
    assert "inspect_visual_learning_shadow(root, target, cutoff)" in source
    assert source.index("primary_card_numbers = list(primary_card") < source.index(
        "inspect_visual_learning_shadow(root, target, cutoff)"
    )
    assert "production_influence" not in source.split("trace_checks = {")[1].split("if not all(trace_checks")[0]
