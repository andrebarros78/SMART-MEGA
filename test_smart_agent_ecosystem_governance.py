from __future__ import annotations

import ast
import json
from pathlib import Path

import smart_agent_ecosystem_governance as g
from smart_agent_skill_orchestration import build_orchestration

ROOT = Path(__file__).resolve().parent


def test_acquisition_manifest_is_source_only_hashed_and_runtime_free():
    doc = g.build_acquisition_manifest(ROOT)
    assert doc["status"] == "PASS"
    assert doc["runtime_dependency_added"] is False
    assert doc["external_code_auto_execute"] is False
    assert len(doc["items"]) >= 3
    for row in doc["items"]:
        assert row["status"] == "SOURCE_REFERENCE_ACQUIRED"
        assert row["execution_policy"] == "SOURCE_REFERENCE_ONLY"
        assert row["runtime_dependency"] is False
        assert len(row["local_sha256"]) == 64


def test_supervisory_agents_are_gate_only_without_predictive_authority():
    assert set(g.SUPERVISORY_AGENTS) == {"architecture_gap_hunter", "capability_acquisition_guardian"}
    allowed = {"OBSERVE_AND_GATE_ONLY", "ACQUISITION_GATE_ONLY"}
    assert all(agent["authority"] in allowed for agent in g.SUPERVISORY_AGENTS.values())


def test_external_agent_runtime_packages_and_imports_are_absent():
    forbidden_deps = {
        "langgraph", "crewai", "autogen", "pyautogen", "llama-index", "llama_index",
        "llamaindex", "dify", "dify-client", "dify_client", "agent-framework",
        "microsoft-agent-framework", "microsoft_agent_framework", "langchain", "langchain-core",
    }
    assert not (g._dependency_names(ROOT) & forbidden_deps)
    forbidden_roots = {"langgraph", "crewai", "autogen", "llama_index", "llamaindex", "dify", "dify_client", "agent_framework", "microsoft_agent_framework", "langchain"}
    hits = []
    for path in sorted(ROOT.glob("smart_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = {node.module.split(".")[0]}
            else:
                continue
            if roots & forbidden_roots:
                hits.append(f"{path.name}:{node.lineno}:{sorted(roots & forbidden_roots)}")
    assert hits == []


def test_build_context_is_non_operational_and_targets_next_contest():
    doc = build_orchestration(ROOT, phase="BUILD")
    ctx = doc["active_context"]
    assert ctx["context_role"] == "NON_OPERATIONAL_CONSTRUCTION_PROBE"
    assert ctx["target_contest"] == ctx["cutoff_contest"] + 1
    assert ctx["freeze_file"] is None
    assert ctx["operator_target_selected"] is False


def test_stale_product_certification_fails_closed(monkeypatch):
    monkeypatch.setattr(g, "_current_product_certification", lambda root: (False, "stale-test"))
    monkeypatch.setattr(g, "_latest_code_mtime", lambda root: 0.0)
    doc = g.evaluate(ROOT)
    assert doc["status"] == "FAIL"
    rendered = json.dumps(doc, sort_keys=True)
    assert "proof_freshness_audit" in rendered
    assert "stale-test" in rendered
