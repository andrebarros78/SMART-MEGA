from pathlib import Path
import json

import pytest
from smart_skill_adapter_registry import build_registry, sha256_json
from smart_skill_runtime import SmartSkillRuntime
from smart_total_integration_gate import evaluate

ROOT = Path(__file__).resolve().parent


def test_f07_separates_native_aliases_reference_and_external_sources():
    reg = build_registry(ROOT)
    assert reg["gate"] == {"status": "PASS", "errors": []}
    assert reg["summary"] == {
        "capabilities": 41,
        "native_adapters": 37,
        "reference_only": 4,
        "external_quarantined_sources": 21,
        "active_native": 0,
        "external_executions": 0,
    }
    assert all(x["state"] == "QUARANTINED_SOURCE" and not x["runtime_source_code_executed"] for x in reg["external_sources"])
    assert all(x["state"] != "ACTIVE_NATIVE" for x in reg["adapters"])


def test_f07_registry_is_reproducible_from_current_sources():
    expected = build_registry(ROOT)
    actual = json.loads((ROOT / "SMART_SKILL_ADAPTER_REGISTRY.json").read_text(encoding="utf-8"))
    assert actual == expected
    assert expected["registry_sha256"] == sha256_json({k: v for k, v in expected.items() if k != "registry_sha256"})


def test_f07_skill_runtime_consumes_exact_certified_native_binding():
    rt = SmartSkillRuntime(ROOT, phase="BUILD")
    native = next(c for c in rt.registrations() if c["callable"])
    invocation = rt.invoke(native["capability"])
    binding = rt._adapter_by_name[native["capability"]]
    assert invocation["adapter_state"] == "NATIVE_ADAPTER"
    assert invocation["adapter_binding_sha256"] == binding["binding_sha256"]
    assert invocation["adapter_registry_sha256"] == rt.adapter_registry["registry_sha256"]
    assert invocation["decision_effect"] == "READ_ONLY_VALIDATION_EVIDENCE"
    assert invocation["external_source_executed"] is False
    assert invocation["predictive_weight_authorized"] is False
    assert invocation["freeze_mutation_authorized"] is False


def test_f07_unauthorized_state_and_binding_tampering_fail_closed():
    rt = SmartSkillRuntime(ROOT, phase="BUILD")
    capability = next(c["capability"] for c in rt.registrations() if c["callable"])
    row = rt._adapter_by_name[capability]
    original = dict(row)
    try:
        row["state"] = "ACTIVE_NATIVE"
        with pytest.raises(RuntimeError, match="binding mismatch"):
            rt.invoke(capability)
    finally:
        rt._adapter_by_name[capability] = original
    row = rt._adapter_by_name[capability]
    row["state"] = "ACTIVE_NATIVE"
    row["binding_sha256"] = sha256_json({k: v for k, v in row.items() if k != "binding_sha256"})
    with pytest.raises(RuntimeError, match="unproved skill adapter state"):
        rt.invoke(capability)


def test_f07_manifest_policy_tampering_rejected(tmp_path):
    import shutil
    target = tmp_path / "manifest"
    target.mkdir()
    source = json.loads((ROOT / "SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json").read_text(encoding="utf-8"))
    source["external_code_auto_execute"] = True
    (target / "SMART_EXTERNAL_SKILLS_QUARANTINE_MANIFEST.json").write_text(json.dumps(source), encoding="utf-8")
    from smart_skill_adapter_registry import build_registry
    bad = build_registry(target)
    assert bad["gate"]["status"] == "FAIL"
    assert "external source quarantine manifest policy violated" in bad["gate"]["errors"]


def test_f07_total_integration_gate_checks_adapter_consumption():
    proof = evaluate(ROOT, phase="BUILD")
    assert proof["status"] == "PASS"
    gate = proof["gates"]["G10_SKILL_ADAPTER_CONSUMPTION"]
    assert all(gate.values())
    assert len(proof["skill_adapter_registry_sha256"]) == 64


def test_f07_native_python_target_line_endings_normalized(tmp_path):
    import hashlib
    from smart_skill_adapter_registry import sha256_file
    py=tmp_path/"native.py"
    canonical=b"print(1)\nprint(2)\n"
    py.write_bytes(canonical.replace(b"\n",b"\r\n"))
    assert sha256_file(py)==hashlib.sha256(canonical).hexdigest()
    evidence=tmp_path/"immutable.json"
    bytes_evidence=b"{\r\n}\r\n"
    evidence.write_bytes(bytes_evidence)
    assert sha256_file(evidence)==hashlib.sha256(bytes_evidence).hexdigest()
