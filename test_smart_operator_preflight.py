from pathlib import Path
import json

import smart_operator as op


def _allow_isolated_root(monkeypatch):
    monkeypatch.setattr(op, "canonical_root", lambda root=None: Path(root).resolve())
    monkeypatch.setattr(op, "reconcile_startup", lambda root, target=None, include_authority_freshness=True: {"status": "OK", "checks": {}})
    monkeypatch.setattr(op, "audit_state_boundaries", lambda root: {"status": "PASS"})



def _active(tmp_path: Path, cert: str = "c" * 64) -> dict:
    epoch = tmp_path / "runtime" / "learning_epochs" / "e3060"
    epoch.mkdir(parents=True)
    data = epoch / "Mega-Sena_cutoff_3059.xlsx"; data.write_bytes(b"history")
    ledger = epoch / "SMART_SIGNAL_LEDGER.json"
    ledger_doc = op.load_ledger(ledger)
    ledger.write_text(json.dumps(ledger_doc), encoding="utf-8")
    freeze = epoch / "SMART_3060_CHAMPION_CHALLENGER_FREEZE.json"
    canonical = tmp_path / "Mega-Sena.xlsx"; canonical.write_bytes(b"history")
    return {
        "operator_selected_target": True, "target_contest": 3060, "cutoff_contest": 3059,
        "status": "RESET_READY", "epoch_id": "e3060", "product_certification_sha256": cert,
        "immutable_history_snapshot": True, "result_used": False, "freeze_authority": None,
        "data_file": str(data.relative_to(tmp_path)).replace("\\", "/"), "data_sha256": op.sha256_file(data),
        "canonical_source_file": "Mega-Sena.xlsx", "canonical_source_sha256_at_prepare": op.sha256_file(canonical),
        "canonical_ledger_seed_sha256": op.sha256_file(ledger),
        "state_paths": {"ledger": str(ledger.relative_to(tmp_path)).replace("\\", "/"), "freeze": str(freeze.relative_to(tmp_path)).replace("\\", "/")},
    }


def _schedule(monkeypatch):
    monkeypatch.setattr(op, "resolve_target_schedule", lambda root, target: {"target_contest": target, "scheduled_datetime": "2099-01-01T00:00:00-03:00"})
    monkeypatch.setattr(op, "assert_pre_draw_window", lambda schedule: {"status": "PASS", "result_used": False})


def test_preflight_ready_to_prepare_is_read_only(tmp_path: Path, monkeypatch) -> None:
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr("smart_product_certification.verify_product_certification", lambda *a, **k: {"sha256": "c" * 64, "status": "CONSTRUCTION_PROVEN"})
    monkeypatch.setattr(op, "_require_next_cycle_authority", lambda root, target: {"sha256": "a" * 64})
    monkeypatch.setattr(op, "validate_target_against_history", lambda path, target: {"target_contest": target, "cutoff_contest": target - 1, "history_max": target - 1})
    _schedule(monkeypatch)
    before = sorted((str(p.relative_to(tmp_path)), p.stat().st_size) for p in tmp_path.rglob("*") if p.is_file())
    out = op.preflight_operation(tmp_path, 3060)
    after = sorted((str(p.relative_to(tmp_path)), p.stat().st_size) for p in tmp_path.rglob("*") if p.is_file())
    assert out["status"] == "READY_TO_PREPARE"
    assert out["schema"] == "SMART_OPERATOR_PREFLIGHT_2"
    assert out["mutated_state"] is False
    assert before == after


def test_preflight_ready_to_freeze_requires_full_integrity(tmp_path: Path, monkeypatch) -> None:
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr("smart_product_certification.verify_product_certification", lambda *a, **k: {"sha256": "c" * 64, "status": "CONSTRUCTION_PROVEN"})
    active_path = tmp_path / op.ACTIVE_PATH; active_path.write_text("{}", encoding="utf-8")
    active = _active(tmp_path)
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    _schedule(monkeypatch)
    out = op.preflight_operation(tmp_path, 3060)
    assert out["status"] == "READY_TO_FREEZE"
    assert out["active_epoch_integrity_pass"] is True
    assert all(out["integrity_checks"].values())
    assert out["mutated_state"] is False


def test_preflight_requires_reprepare_when_active_certification_is_stale(tmp_path: Path, monkeypatch) -> None:
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr("smart_product_certification.verify_product_certification", lambda *a, **k: {"sha256": "n" * 64, "status": "CONSTRUCTION_PROVEN"})
    active_path = tmp_path / op.ACTIVE_PATH; active_path.write_text("{}", encoding="utf-8")
    active = _active(tmp_path, "o" * 64)
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    _schedule(monkeypatch)
    out = op.preflight_operation(tmp_path, 3060)
    assert out["status"] == "REPREPARE_REQUIRED"
    assert out["reason"] == "ACTIVE_EPOCH_PRODUCT_CERTIFICATION_STALE"
    assert out["active_epoch_certification_matches_current"] is False


def test_preflight_blocks_tampered_snapshot(tmp_path: Path, monkeypatch) -> None:
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr("smart_product_certification.verify_product_certification", lambda *a, **k: {"sha256": "c" * 64, "status": "CONSTRUCTION_PROVEN"})
    active_path = tmp_path / op.ACTIVE_PATH; active_path.write_text("{}", encoding="utf-8")
    active = _active(tmp_path)
    (tmp_path / active["data_file"]).write_bytes(b"tampered")
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    _schedule(monkeypatch)
    out = op.preflight_operation(tmp_path, 3060)
    assert out["status"] == "BLOCKED_INTEGRITY"
    assert out["integrity_checks"]["data_snapshot_hash_match"] is False


def test_preflight_blocks_target_event_or_premature_freeze(tmp_path: Path, monkeypatch) -> None:
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr("smart_product_certification.verify_product_certification", lambda *a, **k: {"sha256": "c" * 64, "status": "CONSTRUCTION_PROVEN"})
    active_path = tmp_path / op.ACTIVE_PATH; active_path.write_text("{}", encoding="utf-8")
    active = _active(tmp_path)
    ledger = tmp_path / active["state_paths"]["ledger"]
    ledger_doc = op.load_ledger(ledger)
    ledger_doc["events"] = [{"target_contest":3060,"event_type":"GENERATION"}]
    ledger.write_text(json.dumps(ledger_doc), encoding="utf-8")
    active["canonical_ledger_seed_sha256"] = op.sha256_file(ledger)
    freeze = tmp_path / active["state_paths"]["freeze"]; freeze.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    _schedule(monkeypatch)
    out = op.preflight_operation(tmp_path, 3060)
    assert out["status"] == "BLOCKED_INTEGRITY"
    assert out["integrity_checks"]["target_events_absent"] is False
    assert out["integrity_checks"]["freeze_artifact_absent"] is False


def test_preflight_returns_structured_block_for_stale_product_certification(tmp_path: Path, monkeypatch) -> None:
    _allow_isolated_root(monkeypatch)
    def stale(*a, **k): raise ValueError("SMART product certification is stale for current code")
    monkeypatch.setattr("smart_product_certification.verify_product_certification", stale)
    out = op.preflight_operation(tmp_path, 3060)
    assert out["status"] == "BLOCKED_CERTIFICATION"
    assert out["error_type"] == "ValueError"
    assert out["mutated_state"] is False


def test_operator_contract_advertises_hardened_preflight() -> None:
    c = op.contract()
    assert "preflight" in c["supported_actions"]
    assert c["preflight_is_read_only"] is True
    assert c["preflight_fails_closed_on_stale_certification"] is True
    assert c["preflight_validates_active_epoch_integrity"] is True


def test_preflight_blocks_malformed_ledger_without_traceback(tmp_path: Path, monkeypatch) -> None:
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr("smart_product_certification.verify_product_certification", lambda *a, **k: {"sha256": "c" * 64, "status": "CONSTRUCTION_PROVEN"})
    active_path = tmp_path / op.ACTIVE_PATH; active_path.write_text("{}", encoding="utf-8")
    active = _active(tmp_path)
    ledger = tmp_path / active["state_paths"]["ledger"]
    ledger.write_text("{}", encoding="utf-8")
    active["canonical_ledger_seed_sha256"] = op.sha256_file(ledger)
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    _schedule(monkeypatch)
    out = op.preflight_operation(tmp_path, 3060)
    assert out["status"] == "BLOCKED_INTEGRITY"
    assert out["integrity_checks"]["ledger_valid"] is False


def test_authority_freshness_uses_bound_global_integrity_gate(monkeypatch, tmp_path: Path) -> None:
    import smart_authority_freshness as freshness

    observed = {}

    def fake_verify_global_integrity(root, gate_path, proof_path):
        observed["gate_path"] = Path(gate_path).name
        observed["proof_path"] = Path(proof_path).name
        return {"status": "PASS"}

    monkeypatch.setattr("smart_product_certification.verify_product_certification", lambda *a, **k: {"status": "CONSTRUCTION_PROVEN"})
    monkeypatch.setattr(freshness, "verify_governance", lambda root: {"status": "PASS"})
    monkeypatch.setattr("smart_global_integrity.verify_global_integrity", fake_verify_global_integrity)
    monkeypatch.setattr(freshness, "build_critical_code_manifest", lambda root: {"schema": "SMART_CRITICAL_CODE_MANIFEST_1", "files": {}, "file_count": 0, "fingerprint_sha256": "0" * 64})
    monkeypatch.setattr(freshness, "load_registry", lambda *a, **k: {"open_count": 0})

    result = freshness.audit(tmp_path)

    assert result["authorities"]["global_integrity"]["current"] is True
    assert observed["gate_path"] == "SMART_3052_IMPLEMENTATION_GATE.json"
    assert observed["proof_path"] == "SMART_GLOBAL_INTEGRITY_PROOF.json"

def test_preflight_frozen_epoch_returns_verified_terminal_generation_without_schedule(tmp_path, monkeypatch):
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr("smart_product_certification.verify_product_certification",
                        lambda *a, **k: {"sha256": "c" * 64, "status": "CONSTRUCTION_PROVEN"})
    (tmp_path / op.ACTIVE_PATH).write_text("{}", encoding="utf-8")
    active = _active(tmp_path)
    active["status"] = "FROZEN"
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(op, "assert_lifecycle_state",
                        lambda *a, **k: {"state": "FROZEN", "sha256": "d" * 64})
    monkeypatch.setattr(op, "_existing_frozen_freeze_summary",
                        lambda *a, **k: {"status": "FROZEN", "epoch_id": "e3060",
                                         "active_epoch_sha256": "e" * 64, "freeze_sha256": "f" * 64,
                                         "freeze_file": "runtime/learning_epochs/e3060/freeze.json"})
    monkeypatch.setattr(op, "resolve_target_schedule",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("do not read PDF for frozen contest")))
    before = sorted((str(x.relative_to(tmp_path)), x.read_bytes()) for x in tmp_path.rglob("*") if x.is_file())
    result = op.preflight_operation(tmp_path, 3060)
    after = sorted((str(x.relative_to(tmp_path)), x.read_bytes()) for x in tmp_path.rglob("*") if x.is_file())
    assert result["status"] == "ALREADY_FROZEN"
    assert result["next_permitted_phase"] == "ADJUDICATE"
    assert result["freeze_sha256"] == "f" * 64
    assert result["result_used"] is False and result["mutated_state"] is False
    assert before == after


def test_preflight_frozen_epoch_blocks_broken_hash_lineage(tmp_path, monkeypatch):
    _allow_isolated_root(monkeypatch)
    monkeypatch.setattr("smart_product_certification.verify_product_certification",
                        lambda *a, **k: {"sha256": "c" * 64, "status": "CONSTRUCTION_PROVEN"})
    (tmp_path / op.ACTIVE_PATH).write_text("{}", encoding="utf-8")
    active = _active(tmp_path)
    active["status"] = "FROZEN"
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(op, "assert_lifecycle_state",
                        lambda *a, **k: {"state": "FROZEN", "sha256": "d" * 64})
    def invalid_freeze(*args, **kwargs):
        raise ValueError("existing frozen epoch is not bound to requested target")
    monkeypatch.setattr(op, "_existing_frozen_freeze_summary", invalid_freeze)
    monkeypatch.setattr(op, "resolve_target_schedule",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no schedule access")))
    result = op.preflight_operation(tmp_path, 3060)
    assert result["status"] == "BLOCKED_INTEGRITY"
    assert result["reason"] == "FROZEN_EPOCH_LINEAGE_INVALID"
    assert result["result_used"] is False and result["mutated_state"] is False
