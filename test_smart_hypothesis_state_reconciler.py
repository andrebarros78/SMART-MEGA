from pathlib import Path

import smart_hypothesis_state_reconciler as reconciler

ROOT = Path(__file__).resolve().parent
FREEZE_SHA = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_powered_report_resolves_replication_limit_without_promoting():
    registry, proof = reconciler.build_reconciliation(ROOT)
    rows = {item["id"]: item for item in registry["hypotheses"]}
    assert proof["resolution_sufficient"] is True
    assert proof["replications"] >= proof["minimum_replications_for_resolution"]
    assert proof["holm_rejections"] == []
    for hypothesis_id in reconciler.TARGET_HYPOTHESES:
        row = rows[hypothesis_id]
        assert row["status"] == reconciler.POWER_RESOLVED_STATUS
        assert row["promotion_authority"] is False
        assert row["power_resolution"]["resolution_sufficient"] is True
        assert row["power_resolution"]["failure_to_reject_proves_null"] is False
        assert row["power_resolution"]["predictive_weight_authorized"] is False
        assert "SMART_FALSIFICATION_REPORT_POWERED.json" in row["evidence"]


def test_prospective_hypothesis_is_bound_to_canonical_3054_freeze_and_unadjudicated():
    registry, proof = reconciler.build_reconciliation(ROOT)
    row = next(item for item in registry["hypotheses"] if item["id"] == "H_PROSPECTIVE_ADVANTAGE")
    binding = row["prospective_binding"]
    assert binding["target_contest"] == 3054
    assert binding["active_freeze_sha256"] == FREEZE_SHA
    assert binding["freeze_file_sha256"] == FREEZE_SHA
    assert binding["adjudicated"] is False
    assert binding["sequential_proof"] is False
    assert row["promotion_authority"] is False
    assert "SMART_SIGNAL_LEDGER.json" in row["evidence"]
    assert "SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json" in row["evidence"]
    assert proof["guardrails"]["freeze_3054_mutated"] is False


def test_reconciliation_never_converts_retrospective_evidence_into_terminal_proof():
    registry, proof = reconciler.build_reconciliation(ROOT)
    assert registry["rules"]["failure_to_reject_does_not_prove_the_null"] is True
    assert registry["rules"]["predictive_weight_requires_oos_and_prospective_evidence"] is True
    assert proof["guardrails"]["historical_non_rejection_is_not_null_proof"] is True
    assert proof["guardrails"]["historical_rejection_would_not_authorize_prediction"] is True
    assert proof["guardrails"]["predictive_weight_authorized"] is False
    assert proof["guardrails"]["terminal_6of6_proven"] is False


def test_powered_falsification_has_distinct_immutable_experiment_record():
    registry, proof = reconciler.build_reconciliation(ROOT)
    record = proof["experiment_record"]
    assert record["experiment_id"] == "SMART_P4_P5_FALSIFICATION_3053_POWERED_V2"
    assert record["decision"] == "INCONCLUSIVE"
    assert record["resolution_sufficient"] is True
    assert record["predictive_weight_authorized"] is False
    assert record["result"] == "SMART_FALSIFICATION_REPORT_POWERED.json"

    import json
    ledger = json.loads((ROOT / "SMART_EXPERIMENT_LEDGER.json").read_text(encoding="utf-8-sig"))
    matches = [item for item in ledger["records"] if item.get("experiment_id") == record["experiment_id"]]
    assert len(matches) == 1
    assert matches[0] == record
