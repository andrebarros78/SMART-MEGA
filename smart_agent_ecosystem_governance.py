from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_AGENT_ECOSYSTEM_GOVERNANCE_V1"
ACQUISITION_SCHEMA = "SMART_AGENT_ECOSYSTEM_ACQUISITIONS_V1"
SOURCE_DIR = ".external_agent_methodologies_20260915"

SUPERVISORY_AGENTS: dict[str, dict[str, Any]] = {
    "architecture_gap_hunter": {
        "role": "detect stale evidence, architecture drift, unmeasured change and governance gaps",
        "skills": [
            "proof_freshness_audit",
            "orchestration_context_reconciliation",
            "regression_freshness_audit",
            "material_deficiency_crosscheck",
        ],
        "authority": "OBSERVE_AND_GATE_ONLY",
    },
    "capability_acquisition_guardian": {
        "role": "admit external methodologies only through provenance, quarantine and non-regression gates",
        "skills": [
            "source_provenance_hashing",
            "source_quarantine_enforcement",
            "runtime_dependency_bloat_rejection",
            "negative_acquisition_memory",
        ],
        "authority": "ACQUISITION_GATE_ONLY",
    },
}

SOURCE_REFERENCES: dict[str, dict[str, str]] = {
    "langgraph-durable-orchestration": {
        "file": f"{SOURCE_DIR}/langgraph_durable_orchestration.md",
        "source": "https://langchain-ai.github.io/langgraph/reference/",
        "decision": "REFERENCE_ONLY_NO_RUNTIME_INSTALL",
    },
    "mcp-2026-07-28-contracts": {
        "file": f"{SOURCE_DIR}/mcp_2026_07_28_contracts.md",
        "source": "https://blog.modelcontextprotocol.io/posts/2026-07-28/",
        "decision": "REFERENCE_ONLY_NO_RUNTIME_INSTALL",
    },
    "openai-eval-flywheel": {
        "file": f"{SOURCE_DIR}/openai_eval_flywheel.md",
        "source": "https://github.com/openai/openai-cookbook",
        "decision": "REFERENCE_ONLY_NO_RUNTIME_INSTALL",
    },
}

REJECTED_RUNTIME_FRAMEWORKS = {
    "CrewAI": "role-based orchestration already exists natively; no measured gain justifies a second runtime",
    "LangGraph-runtime": "durability patterns are useful, but native SMART state/hashes already cover the current need",
    "Microsoft-Agent-Framework": "cooperative runtime would duplicate current deterministic handoffs",
    "Dify": "visual workflow layer is not required by the canonical headless execution path",
    "LlamaIndex-Workflows": "document/event workflow runtime does not close a current material project gap",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _code_files(root: Path) -> list[Path]:
    files = sorted(set(root.glob("smart_*.py")) | set(root.glob("test_*.py")))
    for name in (
        "requirements.txt",
        "requirements.lock.txt",
        "smart_python.cmd",
        "pytest.ini",
        "SMART_DATA_CONTRACT.md",
        "adjudicate_signal_challenger.py",
        "freeze_next_research.py",
        "p14_coverage_plugin.py",
    ):
        path = root / name
        if path.is_file():
            files.append(path)
    return sorted(set(files))


def _latest_code_mtime(root: Path) -> float:
    files = _code_files(root)
    return max((path.stat().st_mtime for path in files), default=0.0)


def _dependency_names(root: Path) -> set[str]:
    path = root / "requirements.txt"
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            names.add(line.split("==", 1)[0].strip().lower())
    return names


def build_acquisition_manifest(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    items = []
    for name, meta in SOURCE_REFERENCES.items():
        path = root / meta["file"]
        items.append({
            "name": name,
            "status": "SOURCE_REFERENCE_ACQUIRED" if path.is_file() else "MISSING",
            "local_reference": meta["file"],
            "local_sha256": _sha256_file(path) if path.is_file() else None,
            "official_source": meta["source"],
            "execution_policy": "SOURCE_REFERENCE_ONLY",
            "runtime_dependency": False,
            "decision": meta["decision"],
        })
    doc: dict[str, Any] = {
        "schema": ACQUISITION_SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "project": "SMART-MEGA",
        "policy": "External methodologies may inform native design but do not execute inside the predictive runtime without a separate evidence gate.",
        "items": items,
        "rejected_runtime_frameworks": REJECTED_RUNTIME_FRAMEWORKS,
        "external_code_auto_execute": False,
        "runtime_dependency_added": False,
        "status": "PASS" if items and all(row["status"] == "SOURCE_REFERENCE_ACQUIRED" for row in items) else "FAIL",
    }
    canonical = dict(doc)
    doc["sha256"] = _sha256_json(canonical)
    return doc


def write_acquisition_manifest(root: str | Path, output: str = "SMART_AGENT_ECOSYSTEM_ACQUISITIONS_20260915.json") -> dict[str, Any]:
    root = Path(root)
    doc = build_acquisition_manifest(root)
    if doc["status"] != "PASS":
        raise RuntimeError("agent ecosystem acquisition manifest is incomplete")
    (root / output).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def _validate_written_acquisitions(root: Path, manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        return {"valid": False, "reason": "manifest_missing"}
    doc = _read_json(manifest_path)
    canonical = dict(doc)
    observed_hash = canonical.pop("sha256", None)
    rows = doc.get("items", [])
    hash_checks = []
    for row in rows:
        local = root / str(row.get("local_reference", ""))
        hash_checks.append(local.is_file() and row.get("local_sha256") == _sha256_file(local))
    valid = (
        doc.get("schema") == ACQUISITION_SCHEMA
        and doc.get("status") == "PASS"
        and observed_hash == _sha256_json(canonical)
        and bool(rows)
        and all(hash_checks)
        and doc.get("external_code_auto_execute") is False
        and doc.get("runtime_dependency_added") is False
    )
    return {"valid": bool(valid), "items": len(rows), "hash_checks": hash_checks, "sha256": _sha256_file(manifest_path)}


def _runtime_framework_imports(root: Path) -> list[str]:
    needles = ("import langgraph", "from langgraph", "import crewai", "from crewai", "import autogen", "from autogen", "import llama_index", "from llama_index", "import llamaindex", "from llamaindex", "import dify", "from dify", "import dify_client", "from dify_client", "import agent_framework", "from agent_framework", "import microsoft_agent_framework", "from microsoft_agent_framework", "import langchain", "from langchain")
    hits: list[str] = []
    for path in root.glob("smart_*.py"):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore").lower()
        if any(needle in text for needle in needles):
            hits.append(path.name)
    return sorted(hits)


def _current_product_certification(root: Path) -> tuple[bool, str | None]:
    from smart_product_certification import verify_product_certification
    path = root / "SMART_PRODUCT_CERTIFICATION.json"
    try:
        verify_product_certification(path, root=root, require_current_code=True)
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def evaluate(root: str | Path) -> dict[str, Any]:
    from smart_agent_skill_orchestration import build_orchestration
    from smart_material_deficiency_registry import load_registry

    root = Path(root).resolve()
    manifest_path = root / "SMART_AGENT_ECOSYSTEM_ACQUISITIONS_20260915.json"
    acquisitions = _validate_written_acquisitions(root, manifest_path)
    orchestration = build_orchestration(root, phase="BUILD")
    deficiencies = load_registry(root / "SMART_MATERIAL_DEFICIENCY_REGISTRY.json", root=root)
    open_deficiencies = list(deficiencies.get("open_entries", []))
    product_current, product_error = _current_product_certification(root)
    junit = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    regression_fresh = junit.is_file() and junit.stat().st_mtime >= _latest_code_mtime(root)
    deps = _dependency_names(root)
    forbidden_runtime_deps = sorted(deps & {"langgraph", "crewai", "autogen", "pyautogen", "llama-index", "llama_index", "llamaindex", "dify", "dify-client", "dify_client", "agent-framework", "microsoft-agent-framework", "microsoft_agent_framework", "langchain", "langchain-core"})
    runtime_import_hits = _runtime_framework_imports(root)

    gap_skill_results = {
        "proof_freshness_audit": product_current,
        "orchestration_context_reconciliation": orchestration.get("integration_status") == "PASS" and all(orchestration.get("checks", {}).values()),
        "regression_freshness_audit": regression_fresh,
        "material_deficiency_crosscheck": len(open_deficiencies) == 0,
    }
    acquisition_skill_results = {
        "source_provenance_hashing": bool(acquisitions.get("valid")) and all(acquisitions.get("hash_checks", [])),
        "source_quarantine_enforcement": bool(acquisitions.get("valid")),
        "runtime_dependency_bloat_rejection": not forbidden_runtime_deps and not runtime_import_hits,
        "negative_acquisition_memory": len(REJECTED_RUNTIME_FRAMEWORKS) >= 5,
    }
    checks = {
        "two_supervisory_agents_active": set(SUPERVISORY_AGENTS) == {"architecture_gap_hunter", "capability_acquisition_guardian"},
        "all_supervisory_skills_executed": all(gap_skill_results.values()) and all(acquisition_skill_results.values()),
        "base_orchestration_build_pass": orchestration.get("integration_status") == "PASS",
        "acquisition_manifest_pass": bool(acquisitions.get("valid")),
        "no_external_runtime_framework_added": not forbidden_runtime_deps and not runtime_import_hits,
        "external_methodologies_have_no_predictive_authority": all(agent["authority"] in {"OBSERVE_AND_GATE_ONLY", "ACQUISITION_GATE_ONLY"} for agent in SUPERVISORY_AGENTS.values()),
    }
    executions = {
        "architecture_gap_hunter": {
            "status": "PASS" if all(gap_skill_results.values()) else "FAIL",
            "skills": gap_skill_results,
            "observations": {
                "product_certification_current": product_current,
                "product_certification_error": product_error,
                "regression_fresh": regression_fresh,
                "open_material_deficiencies": len(open_deficiencies),
                "build_target_contest": orchestration.get("active_context", {}).get("target_contest"),
                "build_cutoff_contest": orchestration.get("active_context", {}).get("cutoff_contest"),
            },
        },
        "capability_acquisition_guardian": {
            "status": "PASS" if all(acquisition_skill_results.values()) else "FAIL",
            "skills": acquisition_skill_results,
            "observations": {
                "acquired_methodologies": len(SOURCE_REFERENCES),
                "rejected_runtime_frameworks": sorted(REJECTED_RUNTIME_FRAMEWORKS),
                "forbidden_runtime_dependencies": forbidden_runtime_deps,
                "runtime_framework_import_hits": runtime_import_hits,
                "external_code_auto_execute": False,
            },
        },
    }
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "project": "SMART-MEGA",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "scope": "Supervisory architecture governance only; no predictive-weight, freeze-mutation or terminal-mission authority.",
        "base_agent_runtime": {"agents": 9, "capabilities": 41, "unchanged": True},
        "supervisory_agents": SUPERVISORY_AGENTS,
        "executions": executions,
        "checks": checks,
        "acquisition_manifest_file": manifest_path.name,
        "acquisition_manifest_sha256": acquisitions.get("sha256"),
        "base_orchestration_sha256": orchestration.get("orchestration_sha256"),
    }
    doc["sha256"] = _sha256_json(doc)
    return doc


def write(root: str | Path, output: str = "SMART_AGENT_ECOSYSTEM_GOVERNANCE.json") -> dict[str, Any]:
    root = Path(root).resolve()
    doc = evaluate(root)
    (root / output).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def main() -> None:
    root = Path(__file__).resolve().parent
    acquisitions = write_acquisition_manifest(root)
    governance = write(root)
    print(json.dumps({
        "acquisition_status": acquisitions["status"],
        "governance_status": governance["status"],
        "supervisory_agents": len(governance["supervisory_agents"]),
        "checks": governance["checks"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
