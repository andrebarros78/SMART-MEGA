from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import smart_operator as operator
import smart_product_certification as product_cert


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_router_routes_only_completed_immediate_previous_target(tmp_path, monkeypatch):
    ledger = tmp_path / "prev-ledger.json"
    ledger.write_text("{}", encoding="utf-8")
    active = {
        "operator_selected_target": True,
        "target_contest": 3057,
        "state_paths": {"ledger": str(ledger.relative_to(tmp_path))},
    }
    monkeypatch.setattr(operator, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(operator, "load_ledger", lambda path: {"events": [{"event_type": "ADJUDICATION", "target_contest": 3057}]})
    called = {}
    def fake(root, target, *, payload=None, now_utc=None):
        called["target"] = target
        return {"status": "RECOVERED_NO_PREPARED_EPOCH", "target_contest": target}
    monkeypatch.setattr(operator, "recover_missed_unprepared_operation", fake)
    out = operator.recover_missed_unfrozen_operation(tmp_path, 3058)
    assert out["status"] == "RECOVERED_NO_PREPARED_EPOCH"
    assert called["target"] == 3058


def test_router_refuses_nonadjacent_or_uncompleted_previous_target(tmp_path, monkeypatch):
    ledger = tmp_path / "prev-ledger.json"
    ledger.write_text("{}", encoding="utf-8")
    active = {
        "operator_selected_target": True,
        "target_contest": 3057,
        "state_paths": {"ledger": str(ledger.relative_to(tmp_path))},
    }
    monkeypatch.setattr(operator, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(operator, "load_ledger", lambda path: {"events": []})
    with pytest.raises(ValueError, match="does not match missed target"):
        operator.recover_missed_unfrozen_operation(tmp_path, 3058)
    monkeypatch.setattr(operator, "load_ledger", lambda path: {"events": [{"event_type": "ADJUDICATION", "target_contest": 3057}]})
    with pytest.raises(ValueError, match="does not match missed target"):
        operator.recover_missed_unfrozen_operation(tmp_path, 3059)


def test_unprepared_recovery_is_nonpredictive_and_advances_history(tmp_path, monkeypatch):
    root = tmp_path
    active_path = root / operator.ACTIVE_PATH
    active_path.write_text("active-3057", encoding="utf-8")
    ledger = root / "runtime" / "learning_epochs" / "operator-3057-test" / "SMART_SIGNAL_LEDGER.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{}", encoding="utf-8")
    canonical = root / "Mega-Sena.xlsx"
    canonical.write_bytes(b"canonical-through-3057")
    active = {
        "operator_selected_target": True,
        "target_contest": 3057,
        "epoch_id": "operator-3057-test",
        "project": "SMART-MEGA",
        "state_paths": {"ledger": str(ledger.relative_to(root))},
    }
    monkeypatch.setattr(operator, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(operator, "load_ledger", lambda path: {"events": [{"event_type": "ADJUDICATION", "target_contest": 3057}]})
    monkeypatch.setattr(operator, "reconcile_completed_epoch_ledger", lambda *a, **k: {"status": "ALREADY_RECONCILED"})
    monkeypatch.setattr(operator, "advance_completed_epoch", lambda *a, **k: {"status": "ALREADY_CURRENT", "target_contest": 3057})
    monkeypatch.setattr(product_cert, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})

    def fake_history(path, target):
        assert Path(path) == canonical
        if target == 3058:
            return {"target_contest": 3058, "cutoff_contest": 3057, "history_max": 3057, "data_sha256": _sha(canonical)}
        assert target == 3059
        return {"target_contest": 3059, "cutoff_contest": 3058, "history_max": 3058, "data_sha256": _sha(canonical)}
    monkeypatch.setattr(operator, "validate_target_against_history", fake_history)
    monkeypatch.setattr(operator, "resolve_target_schedule", lambda root, target: {"scheduled_datetime": "2026-09-15T21:00:00-03:00"})

    def fake_ingest(source, output, proof, target, payload=None):
        assert Path(source) == canonical and target == 3058
        source_sha = _sha(canonical)
        Path(output).write_bytes(b"canonical-through-3058")
        Path(proof).write_text(json.dumps({"target": 3058}), encoding="utf-8")
        return {
            "source_sha256": source_sha,
            "output_sha256": _sha(Path(output)),
            "actual_numbers": [14, 23, 53, 56, 57, 60],
        }
    monkeypatch.setattr(operator, "ingest_official_result", fake_ingest)

    out = operator.recover_missed_unprepared_operation(
        root,
        3058,
        payload={"numero": 3058},
        now_utc=datetime(2026, 9, 16, 1, 30, tzinfo=timezone.utc),
    )
    assert out["status"] == "RECOVERED_NO_PREPARED_EPOCH"
    assert out["official_result"] == [14, 23, 53, 56, 57, 60]
    assert out["prediction_authority_created"] is False
    assert out["generation_authority_created"] is False
    assert out["prospective_attempt_counted"] is False
    assert out["result_used_for_prediction"] is False
    assert out["ready_for_next_target"] == 3059
    assert not active_path.exists()
    assert canonical.read_bytes() == b"canonical-through-3058"
    proof_path = root / out["proof_file"]
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    observed = proof.pop("sha256")
    expected = hashlib.sha256(json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert observed == expected
