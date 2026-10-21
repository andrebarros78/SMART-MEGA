"""Canonical externally governed Python entrypoint must replace retired Actions roots."""
from __future__ import annotations
import copy
import tempfile
from pathlib import Path
from smart_component_reachability import build_registry
from smart_disconnection_gate import audit_disconnections
from smart_canonical_component_registry import build_registry as canonical
from smart_skill_adapter_registry import build_registry as skills
from smart_github_native_policy import POLICY_ID, ACTIVE_INSTRUCTIONS

ROOT = Path(__file__).resolve().parent


def test_external_authorized_entrypoint_reaches_operator():
    r = build_registry(ROOT)
    assert r["gate"]["status"] == "PASS", r["gate"]
    assert r["entrypoint_provenance"]["policy_id"] == POLICY_ID
    assert r["entrypoint_provenance"]["authority_kind"] == "GOVERNED_EXTERNAL_EXECUTION_STATIC_CONTRACT"
    assert r["entrypoint_provenance"]["runtime_executed"] is False
    assert r["workflow_entrypoints"] == {}
    assert r["external_entrypoints"] == {
        "smart_github_operator.py": ["GOVERNED_EXTERNAL:smart_github_operator.py"]
    }
    assert r["summary"]["workflow_entrypoints"] == 0
    assert r["summary"]["external_entrypoints"] == 1
    required = r["gate"]["required_production_unreachable"]
    assert required == []
    row = next(x for x in r["components"] if x["source_file"] == "smart_github_operator.py")
    assert row["production_reachable"] is True


def test_f10_enforces_external_root_contract():
    r = build_registry(ROOT)
    result = audit_disconnections(ROOT, reachability=r, canonical=canonical(ROOT), skills=skills(ROOT))
    assert result["status"] == "PASS", result["errors"]
    assert result["checks"]["external_governed_entrypoint_bound"] is True
    assert result["external_entrypoint_provenance"]["policy_id"] == POLICY_ID
    broken = copy.deepcopy(r)
    broken["external_entrypoints"] = {}
    audit = audit_disconnections(ROOT, reachability=broken, canonical=canonical(ROOT), skills=skills(ROOT))
    assert audit["status"] == "FAIL"
    assert audit["checks"]["external_governed_entrypoint_bound"] is False


def test_false_dynamic_execution_claim_rejected():
    r = build_registry(ROOT)
    r["entrypoint_provenance"]["runtime_executed"] = True
    audit = audit_disconnections(ROOT, reachability=r, canonical=canonical(ROOT), skills=skills(ROOT))
    assert audit["status"] == "FAIL"
    assert audit["checks"]["external_governed_entrypoint_bound"] is False


def test_synthetic_unverified_policy_denies_external_roots():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "smart_github_operator.py").write_text(
            'STATIC_EXECUTION_DEPENDENCIES = ("smart_operator.py",)\n'
            'if __name__ == "__main__":\n    pass\n'
        )
        (root / "smart_operator.py").write_text('x = 1\n')
        registry = build_registry(root)
        assert registry["external_entrypoints"] == {}
        assert registry["gate"]["status"] == "FAIL"


def test_fake_actions_files_do_not_restore_execution_authority():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for name in ACTIVE_INSTRUCTIONS:
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"{POLICY_ID}\nandrebarros78/SMART-MEGA\nmain\n")
        operator = root / "smart_github_operator.py"
        operator.write_text(
            'STATIC_EXECUTION_DEPENDENCIES = ("smart_operator.py",)\n'
            'if __name__ == "__main__":\n    pass\n'
        )
        (root / "smart_operator.py").write_text('x = 1\n')
        workflows = root / ".github/workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("python smart_github_operator.py\n")
        registry = build_registry(root)
        assert registry["external_entrypoints"] == {}
        assert registry["gate"]["status"] == "FAIL"
