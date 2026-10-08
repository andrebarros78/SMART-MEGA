from pathlib import Path

import pytest

from smart_agent_handoff_runtime import (
    HANDOFF_SCHEMA,
    build_operational_handoff_ledger,
    consume_handoff,
    create_handoff,
)
from smart_agent_runtime import SmartAgentRuntime
from smart_total_integration_gate import evaluate

ROOT = Path(__file__).resolve().parent


def test_f06_runtime_materializes_and_consumes_every_handoff():
    runtime = SmartAgentRuntime(ROOT, phase="BUILD").run()
    ledger = runtime["operational_handoff_ledger"]
    assert ledger["status"] == "PASS"
    assert ledger["produced_count"] > 0
    assert ledger["produced_count"] == ledger["consumed_count"]
    assert all(ledger["checks"].values())
    for row in ledger["records"]:
        assert row["schema"] == HANDOFF_SCHEMA
        assert row["consumed"] is True
        assert row["status"] == "CONSUMED"
        assert len(row["artifact_sha256"]) == 64
        assert row["consumption_result"]["status"] == "CONSUMED"
        assert row["decision_effect"] == "EVIDENCE_GATE_INPUT_ONLY"
        assert row["artifact"]["predictive_weight_authorized"] is False
        assert row["artifact"]["freeze_mutation_authorized"] is False


def test_f06_handoff_rejects_wrong_consumer_and_tampering():
    handoff = create_handoff(
        producer="a",
        consumer="b",
        producer_sequence=1,
        probe_id="probe",
        probe_result={"pass": True},
        evidence_artifacts=[{"path": "x", "sha256": "a" * 64}],
        payload_sha256="b" * 64,
    )
    with pytest.raises(ValueError, match="consumer route mismatch"):
        consume_handoff(handoff, consumer="c", consumer_sequence=2)

    tampered = {**handoff, "artifact": {**handoff["artifact"], "probe_id": "tampered"}}
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        consume_handoff(tampered, consumer="b", consumer_sequence=2)


def test_f06_total_integration_consumes_operational_handoff_ledger():
    total = evaluate(ROOT, phase="BUILD")
    ledger = total["operational_handoff_ledger"]
    assert total["status"] == "PASS"
    assert ledger["status"] == "PASS"
    assert total["gates"]["G5_INTEGRATION"]["operational_handoff_ledger_pass"] is True
    assert total["gates"]["G5_INTEGRATION"]["all_operational_handoffs_consumed_exactly_once"] is True


def test_f06_unconsumed_handoff_is_fail_closed():
    handoff = create_handoff(
        producer="a",
        consumer="b",
        producer_sequence=1,
        probe_id="probe",
        probe_result={"pass": True},
        evidence_artifacts=[{"path": "x", "sha256": "a" * 64}],
        payload_sha256="b" * 64,
    )
    ledger = build_operational_handoff_ledger({
        "a": {"produced_handoffs": [handoff], "consumed_handoffs": []},
        "b": {"produced_handoffs": [], "consumed_handoffs": []},
    })
    assert ledger["status"] == "FAIL"
    assert ledger["records"][0]["status"] == "UNCONSUMED"
