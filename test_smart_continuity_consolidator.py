from pathlib import Path
import copy
import smart_continuity_consolidator as cc

ROOT = Path(__file__).resolve().parent


def test_chat_continuity_consolidation_is_canonical_and_complete():
    doc = cc.build(ROOT)
    assert doc["consolidation_status"] == "PASS"
    assert all(doc["checks"].values())
    current = doc["current_epoch"]
    assert current["target_contest"] == current["cutoff_contest"] + 1
    assert doc["canonical_data"]["sha256"] == current["data_sha256"]
    assert doc["legacy_pre_activation"]["freeze_sha256"] == cc.LEGACY_FREEZE_EXPECTED_SHA256
    assert doc["legacy_pre_activation"]["authority"] == "PRE_FULL_ACTIVATION_HISTORICAL_ONLY"
    if current["status"] == "RESET_READY":
        assert doc["prospective_freeze"]["sha256"] is None
        assert doc["prospective_freeze"]["authority"] == "NONE_RESET_READY"
    else:
        assert len(doc["prospective_freeze"]["sha256"]) == 64
        if current.get("authority_mode") == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE":
            assert doc["prospective_freeze"]["authority"] == "CARRY_FORWARD_PROSPECTIVE_AUTHORITY"
            assert current["current_engineering_generation_authority"] is False
        else:
            assert doc["prospective_freeze"]["authority"] == "ACTIVE_EPOCH"
            assert current["current_engineering_generation_authority"] is True
    assert doc["powered_falsification"]["resolution_sufficient"] is True
    assert doc["checks"]["total_integration_gate_pass"] is True
    assert doc["total_integration"]["status"] == "PASS"
    assert doc["total_integration"]["health"] == "HEALTHY"
    assert doc["checks"]["wmcp_execution_proof_pass"] is True
    assert doc["wmcp_execution"]["command_state"] == "completed"
    assert doc["wmcp_execution"]["exit_code"] == 0
    assert doc["wmcp_execution"]["proof_schema"] == cc.WMCP_PROOF_SCHEMA
    assert doc["wmcp_execution"]["live_supervisor_state"] == "ready"
    assert doc["wmcp_execution"]["live_worker_mode"] in {"LIVE", "DEMAND_DRAINED"}
    assert doc["monte_carlo_convergence"]["predictive_weight_authorized"] is False
    assert doc["mission_state"] == "MISSION_ACTIVE"
    assert doc["terminal_6of6_proven"] is False


def test_wmcp_v2_freshness_gate_rejects_stale_signed_proof():
    doc = cc.read_json(ROOT / "SMART_WMCP_EXECUTION_PROOF_20260905.json")
    stale = copy.deepcopy(doc)
    stale["generated_at_utc"] = "2020-01-01T00:00:00+00:00"
    stale["live_runtime"]["observed_at_utc"] = "2020-01-01T00:00:00+00:00"
    stale.pop("sha256", None)
    stale["sha256"] = cc.sha256_json(stale)
    assert cc._wmcp_execution_valid(stale, require_fresh=False) is True
    assert cc._wmcp_execution_valid(stale, require_fresh=True) is False


def test_wmcp_v2_rejects_forged_noncanonical_roots_even_with_valid_self_hash():
    doc = cc.read_json(ROOT / "SMART_WMCP_EXECUTION_PROOF_20260905.json")
    forged = copy.deepcopy(doc)
    forged["live_runtime"]["wmcp_root"] = r"C:\Temp\FAKE_WMCP"
    forged["live_runtime"]["broker_root"] = r"C:\Temp\FAKE_BROKER"
    forged["checks"]["canonical_wmcp_root"] = True
    forged["checks"]["canonical_broker_root"] = True
    forged["generated_at_utc"] = cc.datetime.now(cc.timezone.utc).isoformat()
    forged["live_runtime"]["observed_at_utc"] = forged["generated_at_utc"]
    forged.pop("sha256", None)
    forged["sha256"] = cc.sha256_json(forged)
    assert cc._wmcp_execution_valid(forged, require_fresh=True) is False
