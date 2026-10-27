"""Fine-tuning authority must never promote from self-hashed retrospective artifacts.

A self-hash checks integrity against accidental change, not independent
prospective authority.  Promotion requires an independently verified gate.
"""
import json

import pytest

import smart_ai_fine_tuning as tuning


def _row(candidate_id):
    return {
        "candidate": {
            "candidate_id": candidate_id,
            "eta": 0.5,
            "redundancy_threshold": 0.85,
            "meta_strength": 0.06,
        },
    }


def test_build_authority_rejects_forged_promoted_report():
    report = {
        "schema": tuning.SCHEMA,
        "status": "PASS",
        "target_contest": 3076,
        "cutoff_contest": 3075,
        "data_sha256": "a" * 64,
        "sha256": "b" * 64,
        "adjudication": {
            "effective_candidate_id": "challenger",
            "promotion_authorized": True,
        },
        "results": [_row("baseline"), _row("challenger")],
    }
    with pytest.raises(ValueError, match="prospective"):
        tuning.build_authority(report)


def test_load_authority_rejects_rehashed_unauthorized_promotion(tmp_path):
    report = {
        "schema": tuning.SCHEMA,
        "status": "PASS",
        "target_contest": 3076,
        "cutoff_contest": 3075,
        "data_sha256": "a" * 64,
        "sha256": "b" * 64,
        "adjudication": {
            "effective_candidate_id": "baseline",
            "promotion_authorized": False,
        },
        "results": [_row("baseline"), _row("challenger")],
    }
    authorized = tuning.build_authority(report)
    authorized["promotion_authorized"] = True
    authorized["status"] = "AUTHORIZED"
    authorized["effective_candidate"] = _row("challenger")["candidate"]
    authorized.pop("sha256")
    authorized["sha256"] = tuning.sha256_json(authorized)
    path = tmp_path / "SMART_AI_HYPERPARAMETERS.json"
    path.write_text(json.dumps(authorized), encoding="utf-8")
    with pytest.raises(ValueError, match="prospective"):
        tuning.load_authority(path, target_contest=3076, data_sha256="a" * 64)



def test_rejected_report_never_leaves_partial_epoch_artifacts(tmp_path):
    report = {
        "schema": tuning.SCHEMA,
        "status": "PASS",
        "target_contest": 3076,
        "cutoff_contest": 3075,
        "data_sha256": "a" * 64,
        "adjudication": {
            "effective_candidate_id": "challenger",
            "promotion_authorized": True,
        },
        "results": [_row("baseline"), _row("challenger")],
    }
    report["sha256"] = tuning.sha256_json(report)
    report_file = tmp_path / "SMART_AI_FINE_TUNING_CURRENT.json"
    authority_file = tmp_path / "SMART_AI_HYPERPARAMETERS.json"
    with pytest.raises(ValueError, match="prospective"):
        tuning.write_report_and_authority(
            report, report_path=report_file, authority_path=authority_file
        )
    assert not report_file.exists()
    assert not authority_file.exists()

