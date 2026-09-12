from pathlib import Path
import hashlib
import json
import pytest

from smart_mission_status import load_mission_status, write_mission_status

ROOT = Path(__file__).resolve().parent


def _base():
    return {
        "schema": "SMART_MISSION_STATUS_V2",
        "status": "MISSION_ACTIVE",
        "terminal_6of6_proven": False,
        "engineering_governance_status": "PROVEN",
        "scientific_predictive_status": "UNPROVEN",
        "prospective_advantage_status": "INSUFFICIENT_EVIDENCE",
        "supersedes_terminal_authority_of": [],
        "terminal_authority_inventory_rule": {
            "unclassified_terminal_claims_fail_closed": True,
            "hash_binding_required": True,
            "canonical_authority": "SMART_MISSION_STATUS.json",
        },
    }


def test_current_mission_status_is_self_hashed_and_valid():
    doc = load_mission_status(ROOT / "SMART_MISSION_STATUS.json", root=ROOT)
    assert len(doc["sha256"]) == 64
    assert doc["status"] == "MISSION_ACTIVE"
    assert doc["terminal_6of6_proven"] is False


def test_mission_status_tamper_fails_closed(tmp_path):
    path = tmp_path / "SMART_MISSION_STATUS.json"
    write_mission_status(path, _base(), root=tmp_path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["scientific_predictive_status"] = "TAMPERED"
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="self-hash invalid"):
        load_mission_status(path, root=tmp_path)


def test_active_mission_rejects_unclassified_terminal_claim(tmp_path):
    path = tmp_path / "SMART_MISSION_STATUS.json"
    write_mission_status(path, _base(), root=tmp_path)
    (tmp_path / "rogue.json").write_text('{"status":"MISSION_PROVEN"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unclassified or stale terminal claim"):
        load_mission_status(path, root=tmp_path)


def _valid_terminal_fixture(tmp_path):
    target = 9999
    top6 = [1, 2, 3, 4, 5, 6]
    freeze = {
        "target_contest": target, "cutoff_contest": target - 1,
        "frozen_before_result": True, "causal_cutoff": True,
        "governed_challenger_top6": top6,
    }
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
    freeze_sha = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    ledger = {"events": [
        {"event_type": "FREEZE", "target_contest": target, "freeze_sha256": freeze_sha},
        {"event_type": "ADJUDICATION", "target_contest": target, "freeze_sha256": freeze_sha, "actual_numbers": top6},
    ]}
    ledger_path = tmp_path / "ledger.json"; ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    audit_path = tmp_path / "audit.json"; audit_path.write_text('{"status":"PASS"}', encoding="utf-8")
    official_path = tmp_path / "official.json"; official_path.write_text('{"terminal_source_corroboration_authorized":true}', encoding="utf-8")
    rule = "unique pre-result exact 6/6 terminal rule"
    proof = {
        "schema": "SMART_TERMINAL_6OF6_PROOF_1", "status": "MISSION_PROVEN",
        "target_contest": target, "terminal_rule": rule,
        "evaluation": {
            "status": "MISSION_PROVEN_ELIGIBLE", "eligible_for_mission_proven": True,
            "target_contest": target, "frozen_top6": top6, "actual_numbers": top6,
            "recomputed_hits": 6, "adjudication_count": 1,
            "checks": {"exact_6of6": True, "all_attempts_counted": True, "source_corroborated": True, "independent_audit_pass": True},
        },
        "freeze_file": freeze_path.name, "freeze_sha256": freeze_sha,
        "signal_ledger_file": ledger_path.name, "signal_ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "official_evidence_file": official_path.name, "official_evidence_sha256": hashlib.sha256(official_path.read_bytes()).hexdigest(),
        "independent_audit_file": audit_path.name, "independent_audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "sequence_sha256": "a" * 64,
        "all_attempts_counted": True, "independent_audit_pass": True, "source_corroborated": True,
        "retroactive_selection_prohibited": True,
    }
    canonical = dict(proof)
    proof["sha256"] = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    proof_path = tmp_path / "terminal.json"; proof_path.write_text(json.dumps(proof), encoding="utf-8")
    doc = _base()
    doc.update({
        "status": "MISSION_PROVEN", "terminal_6of6_proven": True,
        "scientific_predictive_status": "TERMINAL_PROSPECTIVE_6OF6_OBSERVED",
        "terminal_rule": rule, "proven_target_contest": target, "proven_top6": top6, "official_actual_numbers": top6,
        "terminal_proof_file": proof_path.name, "terminal_proof_sha256": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        "independent_audit_file": audit_path.name, "official_evidence_file": official_path.name,
    })
    return doc, proof_path, audit_path


def test_terminal_transition_accepts_fully_bound_semantic_terminal_proof(tmp_path):
    doc, _, _ = _valid_terminal_fixture(tmp_path)
    written = write_mission_status(tmp_path / "SMART_MISSION_STATUS.json", doc, root=tmp_path)
    assert written["terminal_6of6_proven"] is True


def test_terminal_transition_rejects_minimal_status_only_proof(tmp_path):
    proof = tmp_path / "terminal.json"
    proof.write_text('{"status":"MISSION_PROVEN"}', encoding="utf-8")
    doc = _base(); doc.update({
        "status": "MISSION_PROVEN", "terminal_6of6_proven": True,
        "scientific_predictive_status": "TERMINAL_PROSPECTIVE_6OF6_OBSERVED",
        "terminal_proof_file": proof.name, "terminal_proof_sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
    })
    with pytest.raises(ValueError, match="schema/status invalid"):
        write_mission_status(tmp_path / "SMART_MISSION_STATUS.json", doc, root=tmp_path)


def test_terminal_transition_rejects_stale_independent_audit_binding(tmp_path):
    doc, _, audit_path = _valid_terminal_fixture(tmp_path)
    audit_path.write_text('{"status":"FAIL"}', encoding="utf-8")
    with pytest.raises(ValueError, match="independent audit binding stale"):
        write_mission_status(tmp_path / "SMART_MISSION_STATUS.json", doc, root=tmp_path)


def test_terminal_writer_emits_self_hashed_causal_proof_contract():
    source = (ROOT / "smart_3054_terminal_executor.py").read_text(encoding="utf-8")
    for token in ("freeze_file", "signal_ledger_file", "official_evidence_file", "independent_audit_file", 'proof["sha256"] = mission_sha256_json(proof)'):
        assert token in source

def test_critical_mission_consumers_use_validated_contract():
    required = {
        "smart_3054_terminal_executor.py": ("load_mission_status", "write_mission_status"),
        "smart_agent_runtime.py": ("load_mission_status",),
        "smart_agent_skill_orchestration.py": ("load_mission_status",),
        "smart_continuity_consolidator.py": ("load_mission_status",),
        "smart_execution_checkpoint.py": ("load_mission_status",),
        "smart_finalize_deployment.py": ("load_mission_status",),
    }
    for name, tokens in required.items():
        source = (ROOT / name).read_text(encoding="utf-8")
        for token in tokens:
            assert token in source


def test_terminal_transition_accepts_epoch_scoped_bound_terminal_proof(tmp_path):
    doc, proof_path, _ = _valid_terminal_fixture(tmp_path)
    epoch = tmp_path / "runtime" / "learning_epochs" / "synthetic"
    epoch.mkdir(parents=True)
    nested = epoch / proof_path.name
    proof_path.replace(nested)
    doc["terminal_proof_file"] = nested.relative_to(tmp_path).as_posix()
    doc["terminal_proof_sha256"] = hashlib.sha256(nested.read_bytes()).hexdigest()
    written = write_mission_status(tmp_path / "SMART_MISSION_STATUS.json", doc, root=tmp_path)
    assert written["terminal_6of6_proven"] is True


def test_active_mission_ignores_unbound_epoch_scoped_terminal_candidate(tmp_path):
    path = tmp_path / "SMART_MISSION_STATUS.json"
    write_mission_status(path, _base(), root=tmp_path)
    epoch = tmp_path / "runtime" / "learning_epochs" / "synthetic"
    epoch.mkdir(parents=True)
    (epoch / "candidate.json").write_text('{"status":"MISSION_PROVEN"}', encoding="utf-8")
    loaded = load_mission_status(path, root=tmp_path)
    assert loaded["status"] == "MISSION_ACTIVE"
    assert loaded["terminal_6of6_proven"] is False
