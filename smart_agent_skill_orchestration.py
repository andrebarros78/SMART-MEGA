from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_AGENT_SKILL_ORCHESTRATION_V1"

LANES: dict[str, dict[str, Any]] = {
    "data_quality_and_contracts": {
        "capabilities": [
            "openai-analyze-data-quality",
            "openai-validate-data",
            "pandera-data-contracts",
            "data-analysis",
        ],
        "native_targets": [
            "smart_data_quality_gate.py",
            "smart_validation_gate.py",
            "SMART_DATA_CONTRACT.md",
        ],
        "role": "validate source integrity, cutoff discipline, schemas and evidence bundles",
        "authority": "GATE_ONLY",
    },
    "experiment_design_and_falsification": {
        "capabilities": [
            "experiment-design",
            "simulation",
            "statistical-analysis",
            "multiple-testing-fdr-statsmodels",
            "bayesian-workflow",
            "machine-learning-model-validation",
            "mlflow",
        ],
        "native_targets": [
            "smart_experiment_lab.py",
            "smart_falsification_lab.py",
            "smart_falsification_power_audit.py",
            "smart_probability_audit.py",
        ],
        "role": "preregistration, null simulation, multiplicity, calibration and out-of-sample evidence",
        "authority": "RESEARCH_AND_GATE_ONLY",
    },
    "time_series_regime_and_structure": {
        "capabilities": [
            "aeon",
            "regime-detection",
            "time-series-forecasting",
            "networkx",
            "statsmodels",
            "ruptures",
        ],
        "native_targets": [
            "smart_randomness_cartography.py",
            "smart_cartography_extended.py",
        ],
        "role": "diagnostic temporal, network, regime and nonlinear structure measurement",
        "authority": "DIAGNOSTIC_ONLY",
    },
    "combinatorial_and_formal": {
        "capabilities": [
            "combinatorialist",
            "operations-research-algorithm-developer",
            "google-or-tools",
            "z3-formal-verification",
            "nisan-et-al-2007-algorithmic-game-theory",
        ],
        "native_targets": [
            "smart_portfolio_optimizer.py",
            "smart_portfolio_pipeline.py",
            "smart_validation_gate.py",
        ],
        "role": "constrained optimization, invariant reasoning and structural verification",
        "authority": "ENGINEERING_ONLY",
    },
    "testing_and_robustness": {
        "capabilities": [
            "property-based-testing-hypothesis",
            "test-gap-analysis",
            "mutmut-mutation",
        ],
        "native_targets": [
            "test_smart_architecture_alignment.py",
            "test_smart_global_integrity.py",
            "test_smart_continuous_red_team.py",
        ],
        "role": "test generation principles, gap discovery and mutation-resistance methodology",
        "authority": "TEST_ONLY",
    },
    "learning_calibration_and_drift": {
        "capabilities": [
            "evo-memory",
            "model-drift-management",
            "hyperparameter-tuning-optuna",
            "conformal-risk-control-mapie",
            "live-evo-online-evolution-agentic",
            "benchmarking-uncertainty-calibration-long-form",
            "superforecasting",
            "extremizing-forecasts",
        ],
        "native_targets": [
            "smart_bounded_online_learning.py",
            "smart_contextual_meta_weights.py",
            "smart_rank_score_calibration.py",
            "smart_meta_governor.py",
            "SMART_EXPERIMENT_REGISTRY",
        ],
        "role": "bounded adaptation, calibration, drift awareness and experiment memory",
        "authority": "SHADOW_UNTIL_EVIDENCE",
    },
    "multi_expert_research": {
        "capabilities": [
            "dianoia",
            "thinktank-me-multi-expert-framework-middle",
            "ml-engineer",
            "pymc",
        ],
        "native_targets": [
            "SMART_HYPOTHESIS_REGISTRY.json",
            "SMART_EXPERIMENT_LEDGER.json",
        ],
        "role": "hypothesis generation and methodology review; never direct scoring authority",
        "authority": "RESEARCH_ONLY",
    },
    "retained_quarantine_no_current_lane": {
        "capabilities": [
            "bridging-online-offline-rl",
            "growth-experimenter",
            "kaggle-learner",
            "visiontrim-unified-vision-token",
        ],
        "native_targets": [],
        "role": "retained as source references; no current SMART-MEGA capability gap justifies activation",
        "authority": "QUARANTINED_INACTIVE",
    },
}


AGENTS: dict[str, dict[str, Any]] = {
    "data_guardian": {
        "lane": "data_quality_and_contracts",
        "consumes": ["raw draw data", "dataset contracts", "cutoff declaration"],
        "produces": ["quality gate", "dataset hash binding", "leakage/cutoff verdict"],
        "handoff_to": ["null_model_cartographer", "falsification_auditor"],
    },
    "null_model_cartographer": {
        "lane": "time_series_regime_and_structure",
        "consumes": ["quality-approved dataset", "null-universe policy"],
        "produces": ["U0-U6 diagnostics", "randomness atlas", "regime/network/temporal measurements"],
        "handoff_to": ["falsification_auditor"],
    },
    "falsification_auditor": {
        "lane": "experiment_design_and_falsification",
        "consumes": ["preregistered hypotheses", "diagnostics", "null universes"],
        "produces": ["multiplicity-corrected evidence", "power-resolution verdict", "promotion denial/eligibility evidence"],
        "handoff_to": ["learning_calibration_governor", "mission_governor"],
    },
    "learning_calibration_governor": {
        "lane": "learning_calibration_and_drift",
        "consumes": ["prediction-result comparisons", "falsification evidence", "drift telemetry"],
        "produces": ["bounded weight decisions", "negative learning", "non-regression decisions"],
        "handoff_to": ["mission_governor"],
    },
    "robustness_red_team": {
        "lane": "testing_and_robustness",
        "consumes": ["native code", "contracts", "known failure modes"],
        "produces": ["regression tests", "invariant checks", "failure evidence"],
        "handoff_to": ["mission_governor"],
    },
    "combinatorial_solver": {
        "lane": "combinatorial_and_formal",
        "consumes": ["frozen scores", "explicit constraints"],
        "produces": ["solver-backed engineering solutions", "optimality/invariant evidence"],
        "handoff_to": ["mission_governor"],
    },
    "research_scout": {
        "lane": "multi_expert_research",
        "consumes": ["open hypotheses", "negative results", "capability gaps"],
        "produces": ["shadow hypotheses", "methodology proposals", "no-direct-weight research artifacts"],
        "handoff_to": ["falsification_auditor"],
    },
    "quarantine_curator": {
        "lane": "retained_quarantine_no_current_lane",
        "consumes": ["third-party source references"],
        "produces": ["inventory and security classification only"],
        "handoff_to": ["research_scout"],
    },
    "mission_governor": {
        "lane": None,
        "consumes": ["all native evidence gates", "prospective freeze", "official adjudication"],
        "produces": ["MISSION_ACTIVE or MISSION_PROVEN according to SMART_MISSION_STATUS terminal rule"],
        "handoff_to": [],
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _flatten_lane_capabilities() -> list[str]:
    out: list[str] = []
    for lane in LANES.values():
        out.extend(lane["capabilities"])
    return out


def _validate_native_targets(root: Path) -> dict[str, bool]:
    targets = sorted({target for lane in LANES.values() for target in lane["native_targets"]})
    return {target: (root / target).exists() for target in targets}


def _resolve_project_file(root: Path, relative: str, *, label: str) -> Path:
    value = str(relative).strip()
    if not value:
        raise ValueError(f"{label} path is empty")
    candidate = (root / value).resolve()
    resolved_root = root.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes project root: {value}") from exc
    return candidate


def _resolve_active_context(root: Path) -> dict[str, Any]:
    from smart_champion_challenger import active_freeze, load_ledger

    ledger_path = root / "SMART_SIGNAL_LEDGER.json"
    ledger = load_ledger(ledger_path)
    freeze_targets = sorted({
        int(ev.get("target_contest", -1))
        for ev in ledger.get("events", [])
        if isinstance(ev, dict) and ev.get("event_type") == "FREEZE" and int(ev.get("target_contest", -1)) >= 0
    }, reverse=True)
    adjudicated = {
        int(ev.get("target_contest", -1))
        for ev in ledger.get("events", [])
        if isinstance(ev, dict) and ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) >= 0
    }
    pending = [target for target in freeze_targets if target not in adjudicated]
    if len(pending) > 1:
        raise ValueError(f"SMART signal ledger has ambiguous pending freezes: {pending}")
    candidates = pending or freeze_targets
    if not candidates:
        raise ValueError("SMART signal ledger has no freeze to resolve")
    target = int(candidates[0])
    freeze_event = active_freeze(ledger, target)
    if freeze_event is None:
        raise ValueError(f"SMART signal ledger has no active freeze for contest {target}")
    freeze_file = str(freeze_event.get("freeze_file", ""))
    if not freeze_file:
        raise ValueError("active freeze event does not declare freeze_file")
    freeze_path = _resolve_project_file(root, freeze_file, label="active freeze")
    if not freeze_path.is_file():
        raise ValueError(f"active freeze artifact missing: {freeze_file}")
    freeze_sha = _sha256(freeze_path)
    declared_freeze_sha = str(freeze_event.get("freeze_sha256", "")).lower()
    if len(declared_freeze_sha) != 64 or freeze_sha.lower() != declared_freeze_sha:
        raise ValueError("active freeze artifact hash mismatch")
    frozen = _read_json(freeze_path)
    cutoff = int(frozen.get("cutoff_contest", freeze_event.get("cutoff_contest", -1)))
    if cutoff != target - 1:
        raise ValueError(f"active freeze cutoff mismatch: target={target} cutoff={cutoff}")
    data_file = str(frozen.get("data_file", ""))
    data_path = _resolve_project_file(root, data_file, label="active data")
    if not data_path.is_file():
        raise ValueError(f"active freeze data artifact missing: {data_file}")
    data_sha = _sha256(data_path)
    declared_data_sha = str(frozen.get("data_sha256", freeze_event.get("data_sha256", ""))).lower()
    if len(declared_data_sha) != 64 or data_sha.lower() != declared_data_sha:
        raise ValueError("active freeze data hash mismatch")
    event_data_sha = str(freeze_event.get("data_sha256", declared_data_sha)).lower()
    if event_data_sha and event_data_sha != data_sha.lower():
        raise ValueError("active freeze ledger/data hash mismatch")
    raw_state_file = frozen.get("signal_state_file")
    state_file = str(raw_state_file) if raw_state_file not in (None, "") else None
    state_path = _resolve_project_file(root, state_file, label="active state") if state_file is not None else None
    if state_path is not None and not state_path.is_file():
        raise ValueError(f"active freeze state artifact missing: {state_file}")
    state_sha = _sha256(state_path) if state_path else None
    declared_state_sha = frozen.get("signal_state_sha256")
    if state_path is not None and declared_state_sha is not None and str(declared_state_sha).lower() != str(state_sha).lower():
        raise ValueError("active freeze state hash mismatch")
    return {
        "target_contest": target,
        "cutoff_contest": cutoff,
        "freeze_file": freeze_file,
        "freeze_sha256": freeze_sha,
        "data_file": data_file,
        "data_sha256": data_sha,
        "signal_state_file": state_file,
        "signal_state_sha256": state_sha,
        "ledger_file": ledger_path.name,
        "ledger_sha256": _sha256(ledger_path),
        "pending_target": target in pending,
    }


def build_orchestration(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    source_manifest_path = root / ".external_skills_acquired" / "ACQUISITION_MANIFEST.json"
    v2_path = root / "SMART_CAPABILITY_ACQUISITION_PROOF_V2.json"
    v3_path = root / "SMART_CAPABILITY_ACQUISITION_PROOF_V3.json"
    v4_path = root / "SMART_CAPABILITY_ACQUISITION_PROOF_V4.json"
    mission_path = root / "SMART_MISSION_STATUS.json"
    active_context = _resolve_active_context(root)

    source_manifest = _read_json(source_manifest_path)
    v2 = _read_json(v2_path)
    v3 = _read_json(v3_path)
    v4 = _read_json(v4_path)
    mission = _read_json(mission_path)

    source_skills = [item["name"] for item in source_manifest["items"]]
    v2_items = list(v2["items"])
    v3_items = list(v3["items"])
    v4_items = [item["name"] for item in v4["acquired"]]
    acquired = sorted(set(source_skills + v2_items + v3_items + v4_items))
    lane_capabilities = _flatten_lane_capabilities()
    duplicates = sorted({name for name in lane_capabilities if lane_capabilities.count(name) > 1})
    missing_from_lanes = sorted(set(acquired) - set(lane_capabilities))
    unknown_in_lanes = sorted(set(lane_capabilities) - set(acquired))
    target_checks = _validate_native_targets(root)

    checks = {
        "source_skills_manifest_complete": len(source_skills) == int(source_manifest["acquired_items"]) == 21,
        "v2_capabilities_complete": len(v2_items) == int(v2["acquired_items"]) == 9,
        "v3_capabilities_complete": len(v3_items) == int(v3["acquired_items"]) == 8,
        "v4_native_libraries_complete": len(v4_items) == len(v4["acquired"]) == 3,
        "all_acquired_capabilities_accounted_for": not missing_from_lanes,
        "no_unknown_lane_capabilities": not unknown_in_lanes,
        "no_duplicate_lane_assignment": not duplicates,
        "all_native_targets_exist": all(target_checks.values()),
        "external_source_auto_execution_disabled": source_manifest.get("policy", "").startswith("Third-party skill sources are quarantined"),
        "global_mission_status_consistent": mission.get("status") in {"MISSION_ACTIVE", "MISSION_PROVEN"}
        and ((mission.get("status") == "MISSION_PROVEN") == bool(mission.get("terminal_6of6_proven"))),
        "active_freeze_present": (root / active_context["freeze_file"]).is_file(),
        "active_freeze_cutoff_is_target_minus_one": int(active_context["cutoff_contest"]) == int(active_context["target_contest"]) - 1,
        "active_data_present": (root / active_context["data_file"]).is_file(),
    }

    lane_documents: dict[str, Any] = {}
    for lane_name, lane in LANES.items():
        lane_documents[lane_name] = {
            **lane,
            "predictive_weight_authorized": False,
            "freeze_mutation_authorized": False,
            "terminal_mission_authority": False,
            "external_code_auto_execute": False,
        }

    document = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": "SMART-MEGA",
        "integration_status": "PASS" if all(checks.values()) else "FAIL",
        "integration_scope": "STRUCTURAL_ORCHESTRATION_ONLY",
        "functional_runtime_proof_required_for_full_integration": True,
        "global_mission_state": mission.get("status"),
        "terminal_6of6_proven": bool(mission.get("terminal_6of6_proven")),
        "policy": {
            "external_skill_sources": "SOURCE_ONLY_QUARANTINE",
            "external_code_auto_execute": False,
            "principles_may_be_distilled_into_native_code": True,
            "predictive_weight_requires_native_evidence_gate": True,
            "freeze_mutation_by_agent_or_skill": False,
            "terminal_mission_authority_by_agent_or_skill": False,
            "best_supported_native_implementation_wins_after_non_regression": True,
        },
        "inventory": {
            "source_only_skills": source_skills,
            "v2_capabilities": v2_items,
            "v3_capabilities": v3_items,
            "native_scientific_libraries": v4_items,
            "unique_capabilities_total": len(acquired),
        },
        "lanes": lane_documents,
        "agents": {
            name: {
                **agent,
                "predictive_weight_authorized": False,
                "freeze_mutation_authorized": False,
                "external_code_auto_execute": False,
                "terminal_authority": False,
                "terminal_resolver": name == "mission_governor",
                "terminal_resolution_condition": "read-only enforcement of SMART_MISSION_STATUS terminal rule" if name == "mission_governor" else None,
            }
            for name, agent in AGENTS.items()
        },
        "checks": checks,
        "active_context": active_context,
        "diagnostics": {
            "missing_from_lanes": missing_from_lanes,
            "unknown_in_lanes": unknown_in_lanes,
            "duplicate_lane_assignment": duplicates,
            "native_target_checks": target_checks,
        },
        "evidence_hashes": {
            "source_manifest_sha256": _sha256(source_manifest_path),
            "capability_v2_sha256": _sha256(v2_path),
            "capability_v3_sha256": _sha256(v3_path),
            "capability_v4_sha256": _sha256(v4_path),
            "mission_status_sha256": _sha256(mission_path),
            "active_freeze_sha256": active_context["freeze_sha256"],
            "active_data_sha256": active_context["data_sha256"],
            "active_signal_state_sha256": active_context["signal_state_sha256"],
            "signal_ledger_sha256": active_context["ledger_sha256"],
        },
    }
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    document["orchestration_sha256"] = hashlib.sha256(canonical).hexdigest()
    return document


def write_orchestration(root: str | Path, output: str = "SMART_AGENT_SKILL_ORCHESTRATION.json") -> dict[str, Any]:
    root = Path(root)
    document = build_orchestration(root)
    if document["integration_status"] != "PASS":
        raise RuntimeError(f"agent/skill integration failed: {document['diagnostics']}")
    (root / output).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


def main(argv: list[str] | None = None) -> None:
    import sys

    args = sys.argv[1:] if argv is None else list(argv)
    project_root = Path(args[0]) if args else Path(__file__).resolve().parent
    result = write_orchestration(project_root)
    print(json.dumps({
        "integration_status": result["integration_status"],
        "unique_capabilities_total": result["inventory"]["unique_capabilities_total"],
        "global_mission_state": result["global_mission_state"],
        "terminal_6of6_proven": result["terminal_6of6_proven"],
        "active_target_contest": result["active_context"]["target_contest"],
        "active_cutoff_contest": result["active_context"]["cutoff_contest"],
        "active_freeze_sha256": result["evidence_hashes"]["active_freeze_sha256"],
    }, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover
    main()
