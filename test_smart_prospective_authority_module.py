from __future__ import annotations

import json
from pathlib import Path

import smart_prospective_authority as pa


def test_prospective_authority_builds_from_current_evidence_without_import_side_effect(tmp_path: Path):
    signal = {
        "schema": "SMART_SIGNAL_LEDGER_1",
        "events": [
            {"event_type": "FREEZE", "target_contest": 3054, "freeze_sha256": "a" * 64},
            {"event_type": "ADJUDICATION", "target_contest": 3053},
        ],
    }
    legacy = {"records": []}
    audit = {
        "prospective_ledger": {
            "status": "PASS",
            "pair_count": 3,
            "no_future_leakage": True,
            "hash_integrity": True,
            "e_process_recomputed": True,
        }
    }
    (tmp_path / "SMART_SIGNAL_LEDGER.json").write_text(json.dumps(signal), encoding="utf-8")
    (tmp_path / "SMART_PROSPECTIVE_LEDGER.json").write_text(json.dumps(legacy), encoding="utf-8")
    (tmp_path / "SMART_P14_INDEPENDENT_AUDIT_CURRENT.json").write_text(json.dumps(audit), encoding="utf-8")
    doc = pa.build_authority(tmp_path)
    assert doc["schema"] == pa.SCHEMA
    assert doc["independent_audit"]["pair_count"] == 3
    assert doc["targets"]["3054"]["adjudicated"] is False
    assert doc["targets"]["3054"]["active_or_latest_freeze_hash"] == "a" * 64
    assert not (tmp_path / "SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json").exists()
    written = pa.write_authority(tmp_path)
    assert written["canonical_sequential_ledger_sha256"] == pa.sha256_file(tmp_path / "SMART_SIGNAL_LEDGER.json")
    assert (tmp_path / "SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json").exists()
