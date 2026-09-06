from pathlib import Path

from smart_agent_runtime import SmartAgentRuntime
from smart_agent_skill_orchestration import build_orchestration

ROOT = Path(__file__).resolve().parent


def test_pre_freeze_orchestration_requires_no_prior_freeze_or_learned_state():
    doc = build_orchestration(ROOT, phase="PRE_FREEZE")
    ctx = doc["active_context"]
    assert doc["integration_status"] == "PASS"
    assert doc["phase"] == "PRE_FREEZE"
    assert ctx["freeze_file"] is None
    assert ctx["freeze_sha256"] is None
    assert ctx["signal_state_file"] is None
    assert ctx["signal_state_sha256"] is None
    assert ctx["target_contest"] == ctx["cutoff_contest"] + 1
    assert doc["checks"]["pre_freeze_has_no_freeze_authority"] is True
    assert doc["checks"]["pre_freeze_has_no_learned_state_authority"] is True


def test_all_agents_can_run_before_any_new_freeze():
    runtime = SmartAgentRuntime(ROOT, phase="PRE_FREEZE").run()
    assert runtime["status"] == "PASS"
    assert runtime["phase"] == "PRE_FREEZE"
    assert runtime["agent_count"] == 9
    assert runtime["capability_count"] == 41
    assert all(runtime["checks"].values())
