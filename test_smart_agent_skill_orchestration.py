from pathlib import Path

import smart_agent_skill_orchestration as aso

ROOT=Path(__file__).resolve().parent
def test_agent_skill_orchestration_accounts_for_all_acquired_capabilities():
    doc=aso.build_orchestration(ROOT)
    assert doc["integration_status"] == "PASS"
    assert doc["integration_scope"] == "STRUCTURAL_ORCHESTRATION_ONLY"
    assert doc["functional_runtime_proof_required_for_full_integration"] is True
    assert doc["inventory"]["unique_capabilities_total"] >= 30
    assert doc["diagnostics"]["missing_from_lanes"] == []
    assert doc["diagnostics"]["unknown_in_lanes"] == []
    assert doc["diagnostics"]["duplicate_lane_assignment"] == []
    assert all(doc["diagnostics"]["native_target_checks"].values())


def test_agents_and_skills_have_no_predictive_freeze_or_terminal_authority():
    doc=aso.build_orchestration(ROOT)
    assert doc["policy"]["external_code_auto_execute"] is False
    assert doc["policy"]["freeze_mutation_by_agent_or_skill"] is False
    assert doc["policy"]["terminal_mission_authority_by_agent_or_skill"] is False
    assert doc["global_mission_state"] == "MISSION_ACTIVE"
    assert doc["terminal_6of6_proven"] is False
    for lane in doc["lanes"].values():
        assert lane["predictive_weight_authorized"] is False
        assert lane["freeze_mutation_authorized"] is False
        assert lane["terminal_mission_authority"] is False
        assert lane["external_code_auto_execute"] is False


def test_orchestration_respects_active_epoch_lifecycle():
    doc=aso.build_orchestration(ROOT)
    assert doc["active_context"]["target_contest"] == doc["active_context"]["cutoff_contest"] + 1
    assert doc["active_context"]["cutoff_contest"] >= 3054
    if doc["phase"] == "PRE_FREEZE":
        assert doc["evidence_hashes"]["active_freeze_sha256"] is None
        assert doc["active_context"]["freeze_file"] is None
        assert doc["checks"]["pre_freeze_has_no_freeze_authority"] is True
    elif doc["phase"] == "POST_RESULT_HOLD":
        assert doc["evidence_hashes"]["active_freeze_sha256"] is None
        assert doc["active_context"]["freeze_file"] is None
        assert doc["active_context"]["prepare_allowed"] is False
        assert doc["active_context"]["generation_allowed"] is False
        assert doc["checks"]["post_result_hold_is_non_operational"] is True
        assert doc["checks"]["post_result_hold_has_no_generation_authority"] is True
    else:
        assert len(doc["evidence_hashes"]["active_freeze_sha256"]) == 64
        assert doc["checks"]["active_freeze_present"] is True


def test_quarantine_policy_remains_source_only():
    doc=aso.build_orchestration(ROOT)
    assert doc["checks"]["external_source_auto_execution_disabled"] is True
    assert doc["policy"]["external_skill_sources"] == "SOURCE_ONLY_QUARANTINE"

def test_all_agents_are_bounded_and_mission_governor_is_resolver_not_authority():
    doc=aso.build_orchestration(ROOT)
    assert set(doc["agents"]) == set(aso.AGENTS)
    for name,agent in doc["agents"].items():
        assert agent["predictive_weight_authorized"] is False
        assert agent["freeze_mutation_authorized"] is False
        assert agent["external_code_auto_execute"] is False
        assert agent["terminal_authority"] is False
        assert agent["terminal_resolver"] is (name == "mission_governor")
