from pathlib import Path

import pytest

import smart_agent_skill_orchestration as orchestration
import smart_finalize_deployment as finalizer
from smart_mission_status import write_mission_status
import smart_operator as operator
import smart_product_certification as certification

ROOT = Path(__file__).resolve().parent


def test_product_completion_is_independent_of_active_operation():
    proof = finalizer._operation_observation(ROOT)
    assert proof["construction_authority"] is False
    source = (ROOT / "smart_product_certification.py").read_text(encoding="utf-8")
    assert "resolve_current_epoch" not in source
    assert 'phase="BUILD"' in source


def test_build_orchestration_is_non_operational_and_has_no_freeze_authority(monkeypatch):
    real_read = orchestration._read_json
    def guarded(path):
        if path.name == "SMART_ACTIVE_EPOCH.json":
            raise AssertionError("BUILD must not read SMART_ACTIVE_EPOCH.json")
        return real_read(path)
    monkeypatch.setattr(orchestration, "_read_json", guarded)
    doc = orchestration.build_orchestration(ROOT, phase="BUILD")
    assert doc["integration_status"] == "PASS"
    assert doc["phase"] == "BUILD"
    ctx = doc["active_context"]
    assert ctx["context_role"] == "NON_OPERATIONAL_CONSTRUCTION_PROBE"
    assert ctx["operator_target_selected"] is False
    assert ctx["freeze_file"] is None
    assert ctx["signal_state_file"] is None


def test_operator_selects_arbitrary_target_when_prior_history_is_complete():
    assert operator.validate_target_sequence([8998, 8999, 9000], 9001) == {
        "target_contest": 9001,
        "cutoff_contest": 9000,
        "history_max": 9000,
    }
    with pytest.raises(ValueError, match="requires canonical history through contest 9001"):
        operator.validate_target_sequence([8998, 8999, 9000], 9002)


def test_operator_contract_keeps_freeze_and_adjudication_out_of_construction_gate():
    c = operator.contract()
    assert c["product_completion_independent_of_operation"] is True
    assert c["operator_selects_target"] is True
    assert c["freeze_is_operational_not_construction_gate"] is True
    assert c["adjudication_is_operational_not_construction_gate"] is True
    assert c["scientific_terminal_claim_independent_of_product_completion"] is True


def test_product_certification_contract_is_construction_only():
    assert certification.SCHEMA == "SMART_PRODUCT_CERTIFICATION_V1"
    source = (ROOT / "smart_product_certification.py").read_text(encoding="utf-8")
    assert "No contest, freeze, generated combination or adjudication is required" in source
    assert 'phase="BUILD"' in source


def test_rendered_continuity_explicitly_separates_construction_operation_and_science():
    synthetic = {
        "generated_at_utc": "2026-09-07T00:00:00+00:00",
        "construction_status": "CONSTRUCTION_PROVEN",
        "mission_state": "MISSION_ACTIVE",
        "product_certification": {
            "status": "CONSTRUCTION_PROVEN",
            "regression": {"tests": 1, "failures": 0, "errors": 0},
            "checks": {"build_runtime_pass": True, "build_total_integration_pass": True, "zero_open_material_deficiencies": True},
        },
        "operation_observation": {"status": "NO_ACTIVE_OPERATION"},
        "checks": {"wmcp_execution_proof_pass": True},
    }
    text = finalizer.render_continuity(synthetic)
    assert "Nenhum concurso" in text
    assert "SMART_ACTIVE_EPOCH.json" in text
    assert "nao possui autoridade sobre a conclusao da construcao" in text
    assert "MISSION_ACTIVE` cientifico nao significa produto inacabado" in text


def _synthetic_finalizer_dependencies(monkeypatch, tmp_path, *, mode, wmcp_result):
    write_mission_status(tmp_path / "SMART_MISSION_STATUS.json", {
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
    }, root=tmp_path)
    (tmp_path / "SMART_WMCP_EXECUTION_PROOF_20260905.json").write_text('{"status":"PASS"}', encoding="utf-8")
    product = {
        "status": "CONSTRUCTION_PROVEN",
        "checks": {"build_runtime_pass": True, "build_total_integration_pass": True, "zero_open_material_deficiencies": True},
        "regression": {"tests": 1, "failures": 0, "errors": 0},
    }
    monkeypatch.setattr(finalizer, "build_product_certification", lambda root: product)
    monkeypatch.setattr(finalizer, "_operation_observation", lambda root: {"status": "NO_ACTIVE_OPERATION", "construction_authority": False})
    monkeypatch.setattr(finalizer, "_control_plane_mode", lambda: mode)
    monkeypatch.setattr(finalizer.consolidation_module, "_wmcp_execution_valid", wmcp_result)
    return product


def test_external_control_plane_does_not_block_construction_certification(monkeypatch, tmp_path):
    _synthetic_finalizer_dependencies(monkeypatch, tmp_path, mode="EXTERNAL", wmcp_result=lambda doc, require_fresh=False: not require_fresh)
    proof = finalizer.build(tmp_path, require_fresh_wmcp=True)
    assert proof["construction_status"] == "CONSTRUCTION_PROVEN"
    assert proof["deployment_status"] == "EXTERNAL_CONTROL_PLANE_REQUIRED"
    assert proof["control_plane"]["construction_authority"] is False
    assert proof["checks"]["wmcp_execution_proof_pass"] is False
    assert proof["checks"]["wmcp_historical_artifact_valid"] is True


def test_local_control_plane_requires_fresh_wmcp_for_deployment_pass(monkeypatch, tmp_path):
    calls=[]
    def validate(doc, require_fresh=False):
        calls.append(require_fresh)
        return True
    _synthetic_finalizer_dependencies(monkeypatch, tmp_path, mode="LOCAL", wmcp_result=validate)
    proof = finalizer.build(tmp_path, require_fresh_wmcp=True)
    assert proof["construction_status"] == "CONSTRUCTION_PROVEN"
    assert proof["deployment_status"] == "PASS"
    assert True in calls
    assert proof["checks"]["wmcp_execution_proof_pass"] is True


def test_inconsistent_local_control_plane_fails_closed_without_blocking_build_fact(monkeypatch, tmp_path):
    _synthetic_finalizer_dependencies(monkeypatch, tmp_path, mode="INCONSISTENT", wmcp_result=lambda doc, require_fresh=False: True)
    proof = finalizer.build(tmp_path, require_fresh_wmcp=True)
    assert proof["construction_status"] == "CONSTRUCTION_PROVEN"
    assert proof["deployment_status"] == "FAIL"
    assert proof["checks"]["wmcp_control_plane_layout_consistent"] is False
