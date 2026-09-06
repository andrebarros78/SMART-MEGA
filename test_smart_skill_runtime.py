from pathlib import Path

import pytest

from smart_skill_runtime import (
    ALL_CAPABILITIES,
    PERTINENT_CAPABILITIES,
    QUARANTINED_CAPABILITIES,
    SmartSkillRuntime,
    write_gate,
)


def root() -> Path:
    return Path(__file__).resolve().parent


def test_every_pertinent_capability_is_individually_callable():
    runtime = SmartSkillRuntime(root())
    assert len(ALL_CAPABILITIES) == 41
    assert len(PERTINENT_CAPABILITIES) == 37
    for capability in PERTINENT_CAPABILITIES:
        result = runtime.invoke(capability, {"test": True})
        assert result["status"] == "PASS"
        assert result["capability"] == capability
        assert result["executed_functions"]
        assert result["external_source_executed"] is False
        assert result["direct_named_skill_execution"] is False
        assert result["semantic_binding_kind"] == "METHODOLOGY_ALIAS_TO_NATIVE_ROLE_PROBE"
        assert len(result["invocation_sha256"]) == 64


def test_nonpertinent_capabilities_are_explicitly_not_callable():
    runtime = SmartSkillRuntime(root())
    assert len(QUARANTINED_CAPABILITIES) == 4
    for capability in QUARANTINED_CAPABILITIES:
        registration = runtime.registration(capability)
        assert registration.pertinent is False
        assert registration.callable is False
        assert registration.execution_mode == "SOURCE_ONLY_QUARANTINE"
        with pytest.raises(PermissionError):
            runtime.invoke(capability)


def test_unknown_capability_and_bad_payload_fail_closed():
    runtime = SmartSkillRuntime(root())
    with pytest.raises(KeyError):
        runtime.invoke("does-not-exist")
    with pytest.raises(TypeError):
        runtime.invoke(PERTINENT_CAPABILITIES[0], "bad")  # type: ignore[arg-type]


def test_full_skill_runtime_gate_is_real_and_non_mutating(tmp_path):
    output = tmp_path / "proof.json"
    result = write_gate(root(), output)
    assert result["status"] == "PASS"
    assert all(result["checks"].values())
    assert result["counts"] == {"registered": 41, "pertinent_callable": 37, "nonpertinent_quarantined": 4}
    assert result["critical_hashes_before"] == result["critical_hashes_after"]
    assert output.is_file()
