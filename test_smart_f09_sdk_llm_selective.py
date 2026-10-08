from __future__ import annotations

from copy import deepcopy

import pytest

from smart_agent_handoff_runtime import (
    SDK_CONTRACT,
    _sha256_json,
    build_operational_handoff_ledger,
    consume_handoff,
    create_handoff,
    validate_sdk_handoff,
)
from smart_agent_runtime import SmartAgentRuntime
from smart_total_integration_gate import evaluate


def _sample_handoff():
    return create_handoff(
        producer="quarantine_curator",
        consumer="research_scout",
        producer_sequence=1,
        probe_id="synthetic_native_probe",
        probe_result={"pass": True},
        evidence_artifacts=[{"path": "SMART_DATA_CONTRACT.md", "sha256": "a" * 64}],
        payload_sha256="b" * 64,
    )


def test_f09_existing_sdk_validates_live_agent_handoffs():
    handoff = _sample_handoff()
    validate_sdk_handoff(handoff)
    consumed = consume_handoff(handoff, consumer="research_scout", consumer_sequence=2)
    assert consumed["consumption_result"]["sdk_contract"] == SDK_CONTRACT
    assert consumed["artifact"] == handoff["artifact"]
    assert consumed["artifact_sha256"] == handoff["artifact_sha256"]


def test_f09_sdk_rejects_bad_evidence_structure_even_with_rehashed_payload():
    for change in (
        {"evidence_artifacts": [{"path": "x"}]},
        {"evidence_artifacts": [{"path": "x", "sha256": "not-a-hash"}]},
        {"evidence_artifacts": [{"path": "x", "sha256": "a" * 64, "unexpected": "injection"}]},
        {"predictive_weight_authorized": True},
        {"freeze_mutation_authorized": True},
        {"decision_effect": "DIRECT_PREDICTION"},
    ):
        handoff = deepcopy(_sample_handoff())
        handoff["artifact"].update(change)
        handoff["artifact_sha256"] = _sha256_json(handoff["artifact"])
        handoff["handoff_id"] = f'{handoff["producer"]}->{handoff["consumer"]}:{handoff["artifact_sha256"][:16]}'
        with pytest.raises(ValueError):
            consume_handoff(handoff, consumer="research_scout", consumer_sequence=2)


def test_f09_sdk_rejects_forged_handoff_id_and_invalid_sequence():
    handoff = _sample_handoff()
    handoff["handoff_id"] = "unbound-id"
    with pytest.raises(ValueError, match="handoff id"):
        consume_handoff(handoff, consumer="research_scout", consumer_sequence=2)

    handoff = _sample_handoff()
    handoff["created_sequence"] = True
    with pytest.raises(ValueError, match="typed SDK"):
        consume_handoff(handoff, consumer="research_scout", consumer_sequence=2)


def test_f09_live_consumption_proves_sdk_and_no_llm_authority(tmp_path):
    from pathlib import Path
    root = Path(__file__).resolve().parent
    runtime = SmartAgentRuntime(root, phase="BUILD").run()
    sdk = runtime["operational_handoff_ledger"]
    assert sdk["status"] == "PASS"
    assert sdk["sdk_contract"] == SDK_CONTRACT
    assert sdk["sdk_external_network_calls"] == 0
    assert sdk["llm_provider"] is None
    assert sdk["checks"]["sdk_contract_consumed"] is True
    assert sdk["consumed_count"] > 0
    total = evaluate(root, phase="BUILD")
    assert total["status"] == "PASS"
    assert all(total["gates"]["G11_SDK_LLM_SELECTIVE"].values())
    assert total["sdk_llm_selection"]["predictive_weight_authorized"] is False
    assert total["sdk_llm_selection"]["freeze_mutation_authorized"] is False
