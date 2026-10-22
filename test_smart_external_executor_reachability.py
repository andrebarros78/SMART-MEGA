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
    from smart_component_reachability import EXTERNAL_EXECUTION_ENTRYPOINTS
    r = build_registry(ROOT)
    assert r["gate"]["status"] == "PASS", r["gate"]
    assert r["entrypoint_authority"] == POLICY_ID
    expected = {name: ["EXTERNAL_EXECUTOR:" + POLICY_ID]
                for name in EXTERNAL_EXECUTION_ENTRYPOINTS}
    assert r["workflow_entrypoints"] == expected
    assert r["summary"]["workflow_entrypoints"] == len(expected)
    assert r["classification_policy"]["runtime_execution_claimed"] is False
    assert r["classification_policy"]["python_source_sha256_normalization"] == "CRLF_TO_LF_BEFORE_HASHING"
    assert r["gate"]["required_production_unreachable"] == []
    for name in ("smart_github_operator.py", "smart_fast_result_ingest.py"):
        row = next(x for x in r["components"] if x["source_file"] == name)
        assert row["production_reachable"] is True


def test_f10_enforces_external_root_contract():
    r = build_registry(ROOT)
    result = audit_disconnections(ROOT, reachability=r, canonical=canonical(ROOT), skills=skills(ROOT))
    assert result["status"] == "PASS", result["errors"]
    assert result["checks"]["external_governed_entrypoint_bound"] is True
    assert result["external_entrypoint_provenance"]["policy_id"] == POLICY_ID
    broken = copy.deepcopy(r)
    broken["workflow_entrypoints"] = {}
    audit = audit_disconnections(ROOT, reachability=broken, canonical=canonical(ROOT), skills=skills(ROOT))
    assert audit["status"] == "FAIL"
    assert audit["checks"]["external_governed_entrypoint_bound"] is False


def test_false_dynamic_execution_claim_rejected():
    r = build_registry(ROOT)
    r["classification_policy"]["runtime_execution_claimed"] = True
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
        assert registry["gate"]["required_production_missing"]
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
        try:
            build_registry(root)
        except ValueError as exc:
            assert "GitHub Actions is forbidden" in str(exc)
        else:
            raise AssertionError("Runnable GitHub Actions must be rejected")


def test_f01_python_source_hashes_are_identical_for_lf_and_crlf_worktrees():
    with tempfile.TemporaryDirectory() as scratch:
        lf = Path(scratch, "lf")
        crlf = Path(scratch, "crlf")
        for root, newline in ((lf, b"\n"), (crlf, b"\r\n")):
            root.mkdir()
            (root / "smart_github_operator.py").write_bytes(
                newline.join((b'STATIC_EXECUTION_DEPENDENCIES = ("smart_operator.py",)',
                              b'if __name__ == "__main__":',
                              b'    pass', b''))
            )
            (root / "smart_operator.py").write_bytes(newline.join(
                (b'def run():', b'    return "ok"', b'')
            ))
        canonical = build_registry(lf)
        checkout = build_registry(crlf)
        assert canonical["inventory_sha256"] == checkout["inventory_sha256"]
        left = {x["source_file"]: x["sha256"] for x in canonical["components"]}
        right = {x["source_file"]: x["sha256"] for x in checkout["components"]}
        assert left == right
