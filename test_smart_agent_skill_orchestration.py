from pathlib import Path

import smart_agent_skill_orchestration as aso

ROOT=Path(__file__).resolve().parent
FREEZE_SHA="503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_agent_skill_orchestration_accounts_for_all_acquired_capabilities():
    doc=aso.build_orchestration(ROOT)
    assert doc["integration_status"] == "PASS"
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


def test_orchestration_is_bound_to_immutable_3054_freeze():
    doc=aso.build_orchestration(ROOT)
    assert doc["evidence_hashes"]["freeze_3054_sha256"] == FREEZE_SHA


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
