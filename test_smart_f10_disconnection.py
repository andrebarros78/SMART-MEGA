from __future__ import annotations

import copy
import json
from pathlib import Path

from smart_disconnection_gate import audit_disconnections
from smart_component_reachability import build_registry as reach
from smart_canonical_component_registry import build_registry as canonical
from smart_skill_adapter_registry import build_registry as skills

ROOT = Path(__file__).resolve().parent


def snapshots():
    return reach(ROOT), canonical(ROOT), skills(ROOT)


def row(rows, key, value):
    return next(x for x in rows if x[key] == value)


def fault(*, r=None, c=None, s=None):
    return audit_disconnections(ROOT, reachability=r, canonical=c, skills=s)


def test_f10_canonical_dependencies_and_legacies_are_isolated():
    result = fault()
    assert result["status"] == "PASS", result["errors"]
    assert all(result["checks"].values())
    assert len(result["required_edges"]) >= 8
    assert "smart_3054_terminal_executor" in result["prohibited_edges"]["smart_terminal_executor.py"]


def test_f10_persisted_failure_gate_matches_fresh_source():
    result = fault()
    saved = json.loads((ROOT / "SMART_F10_DISCONNECTION_GATE.json").read_text(encoding="utf-8"))
    assert saved == result


def test_f10_missing_fine_tuning_edge_causes_failure():
    r, c, s = snapshots()
    r = copy.deepcopy(r)
    pipeline = row(r["components"], "source_file", "smart_full_process_pipeline.py")
    pipeline["producers"].remove("smart_fine_tuning_lifecycle")
    result = fault(r=r, c=c, s=s)
    assert result["status"] == "FAIL"
    assert not result["checks"]["required_production_edges_connected"]


def test_f10_false_active_diagnostic_rejected():
    r, c, s = snapshots()
    c = copy.deepcopy(c)
    diagnostic = row(c["components"], "implementation", "smart_3054_terminal_executor.py")
    diagnostic["state"] = "ACTIVE"
    diagnostic["production_reachable"] = True
    result = fault(r=r, c=c, s=s)
    assert result["status"] == "FAIL"
    assert not result["checks"]["active_labels_match_reachability"]


def test_f10_reintroduced_legacy_runtime_edge_rejected():
    r, c, s = snapshots()
    r = copy.deepcopy(r)
    wrapper = row(r["components"], "source_file", "smart_terminal_executor.py")
    wrapper["producers"].append("smart_3054_terminal_executor")
    result = fault(r=r, c=c, s=s)
    assert result["status"] == "FAIL"
    assert not result["checks"]["forbidden_reverse_edges_absent"]


def test_f10_reintroduced_operator_pipeline_cycle_rejected():
    r, c, s = snapshots()
    r = copy.deepcopy(r)
    row(r["components"], "source_file", "smart_full_process_pipeline.py")["producers"].append("smart_operator")
    result = fault(r=r, c=c, s=s)
    assert result["status"] == "FAIL"
    assert not result["checks"]["forbidden_reverse_edges_absent"]


def test_f10_skill_active_native_promoted_with_rehashed_binding_rejected():
    r, c, s = snapshots()
    s = copy.deepcopy(s)
    alias = next(x for x in s["adapters"] if x["state"] == "NATIVE_ADAPTER")
    alias["state"] = "ACTIVE_NATIVE"
    from smart_disconnection_gate import _hash_json
    alias["binding_sha256"] = _hash_json({k: v for k, v in alias.items() if k != "binding_sha256"})
    s["registry_sha256"] = _hash_json({k: v for k, v in s.items() if k != "registry_sha256"})
    result = fault(r=r, c=c, s=s)
    assert result["status"] == "FAIL"
    assert not result["checks"]["no_unproved_active_skills"]


def test_f10_reference_only_alias_cannot_become_callable():
    r, c, s = snapshots()
    s = copy.deepcopy(s)
    alias = next(x for x in s["adapters"] if x["state"] == "REFERENCE_ONLY")
    alias["callable"] = True
    result = fault(r=r, c=c, s=s)
    assert result["status"] == "FAIL"
    assert not result["checks"]["capability_aliases_match_owners_and_permissions"]


def test_f10_registry_missing_component_detected():
    r, c, s = snapshots()
    c = copy.deepcopy(c)
    c["components"] = [x for x in c["components"] if x["implementation"] != "smart_terminal_engine.py"]
    result = fault(r=r, c=c, s=s)
    assert result["status"] == "FAIL"
    assert not result["checks"]["registry_component_identity"]
