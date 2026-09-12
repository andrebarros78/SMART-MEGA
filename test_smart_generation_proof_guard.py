from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import smart_current_epoch_contract as contract
import smart_operator as operator
from smart_learning_epoch_reset import SCHEMA as EPOCH_SCHEMA, write_active_epoch

ROOT = Path(__file__).resolve().parent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _synthetic_epoch(tmp_path: Path, *, with_original: bool) -> None:
    epoch = tmp_path / "runtime" / "learning_epochs" / "guard-test"
    epoch.mkdir(parents=True)
    data = epoch / "data.xlsx"; data.write_bytes(b"immutable-data")
    ledger = epoch / "ledger.json"; ledger.write_text('{"events": []}\n', encoding="utf-8")
    freeze = epoch / "freeze.json"
    freeze.write_text(json.dumps({"target_contest": 10, "cutoff_contest": 9, "champion": {"top6": [1,2,3,4,5,6]}}) + "\n", encoding="utf-8")
    active = write_active_epoch(tmp_path / "SMART_ACTIVE_EPOCH.json", {
        "schema": EPOCH_SCHEMA, "status": "FROZEN", "project": "SMART-MEGA", "epoch_id": "guard-test",
        "product_certification_file": "SMART_PRODUCT_CERTIFICATION.json", "product_certification_sha256": "a" * 64,
        "operator_selected_target": True,
        "state_paths": {"ledger": str(ledger.relative_to(tmp_path)), "state": str((epoch / "state.json").relative_to(tmp_path)),
                        "activation_authority": str((epoch / "auth.json").relative_to(tmp_path)), "expansion_registry": str((epoch / "exp.json").relative_to(tmp_path)),
                        "freeze": str(freeze.relative_to(tmp_path))},
        "data_file": str(data.relative_to(tmp_path)), "data_sha256": _sha(data), "immutable_history_snapshot": True,
        "cutoff_contest": 9, "target_contest": 10, "result_used": False,
        "freeze_authority": {"file": str(freeze.relative_to(tmp_path)), "sha256": _sha(freeze)},
        "learning_state_authority": {"file": str((epoch / "state.json").relative_to(tmp_path)), "sha256": "b" * 64},
        "authority_mode": "OPERATOR_SELECTED_TARGET", "current_engineering_role": "PRODUCT_CERTIFIED_OPERATION",
    })
    if with_original:
        proof = {"schema": "SMART_FULL_PROCESS_PROOF_2", "status": "PASS", "project": "SMART-MEGA", "epoch_id": "guard-test",
                 "active_epoch_sha256": active["sha256"], "target_contest": 10, "cutoff_contest": 9,
                 "freeze_sha256": _sha(freeze), "trace_checks": {"causal": True}, "result_used": False}
        proof["sha256"] = _json_sha(proof)
        (epoch / "FULL_PROCESS_PROOF.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")


def test_live_frozen_epoch_generation_proof_is_valid() -> None:
    current = contract.resolve(ROOT)
    if current["status"] == "FROZEN":
        assert current["generation_proof_valid"] is True
        assert current["generation_proof_mode"] in {"ORIGINAL_FULL_PROCESS_PROOF", "RECOVERED_FULL_PROCESS_PROOF", "CARRY_FORWARD_AUTHORITY_LOCK"}
        assert (ROOT / current["generation_proof_file"]).is_file()


def test_current_engineering_frozen_epoch_fails_closed_without_generation_proof(tmp_path: Path) -> None:
    _synthetic_epoch(tmp_path, with_original=False)
    with pytest.raises(ValueError, match="missing generation proof"):
        contract.resolve(tmp_path)


def test_original_full_process_proof_is_accepted(tmp_path: Path) -> None:
    _synthetic_epoch(tmp_path, with_original=True)
    current = contract.resolve(tmp_path)
    assert current["generation_proof_valid"] is True
    assert current["generation_proof_mode"] == "ORIGINAL_FULL_PROCESS_PROOF"


def test_tampered_original_generation_proof_is_rejected(tmp_path: Path) -> None:
    _synthetic_epoch(tmp_path, with_original=True)
    proof = next(tmp_path.rglob("FULL_PROCESS_PROOF.json"))
    doc = json.loads(proof.read_text(encoding="utf-8")); doc["freeze_sha256"] = "0" * 64
    proof.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="self-hash invalid"):
        contract.resolve(tmp_path)


def test_operator_adjudication_reconciles_generation_proof_and_ledger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(operator, "verify_active_epoch", lambda p: {"target_contest": 4, "state_paths": {"ledger": "ledger.json"}})
    monkeypatch.setattr(operator, "resolve_current_epoch", lambda root: {"status": "FROZEN", "freeze_authority_present": True, "target_contest": 4,
                                                                          "generation_proof_valid": True, "freeze_sha256": "a" * 64})
    monkeypatch.setattr(operator, "load_ledger", lambda p: {"events": []})
    monkeypatch.setattr(operator, "active_freeze", lambda ledger, target: {"freeze_sha256": "b" * 64})
    with pytest.raises(ValueError, match="differs from signal ledger"):
        operator.adjudicate_operation(tmp_path, 4, "result.xlsx")
