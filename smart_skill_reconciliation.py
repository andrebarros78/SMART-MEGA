"""Bounded, truthful reconciliation of the 14 SMART-MEGA capability gaps.

A capability name alone never proves execution of the external skill that
inspired it.  Only the exact hash-verified native receipts count as consumed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from smart_agent_skill_orchestration import LANES
from smart_skill_runtime import FROZEN_STRUCTURAL_CAPABILITIES, LIVE_POST_RESULT_BINDINGS, sha256_json

SCHEMA = "SMART_REMAINING_CAPABILITIES_RECONCILIATION_1"
ORIGINAL_GAPS = frozenset({
    "aeon", "combinatorialist", "conformal-risk-control-mapie", "dianoia",
    "hyperparameter-tuning-optuna", "ml-engineer", "mlflow",
    "mutmut-mutation", "nisan-et-al-2007-algorithmic-game-theory",
    "property-based-testing-hypothesis", "pymc", "test-gap-analysis",
    "time-series-forecasting", "z3-formal-verification",
})
DEPENDENCIES = {
    "aeon": "aeon", "conformal-risk-control-mapie": "mapie",
    "hyperparameter-tuning-optuna": "optuna", "mlflow": "mlflow",
    "mutmut-mutation": "mutmut", "property-based-testing-hypothesis": "hypothesis",
    "pymc": "pymc", "z3-formal-verification": "z3",
}
RESEARCH_ALIASES = {
    "dianoia": "research source only; no autonomous research agent invoked",
    "nisan-et-al-2007-algorithmic-game-theory": "algorithmic game theory reference; no independent algorithm implemented",
    "ml-engineer": "engineering role label; no distinct model-training consumer proven",
    "test-gap-analysis": "test source and coverage tooling exists; no dedicated runtime gap-audit consumer proven",
}


def reconcile_remaining(structural_diagnostic: dict[str, Any], root: str | Path) -> dict[str, Any]:
    base = Path(root).resolve()
    all_caps = {n for lane in LANES.values() for n in lane["capabilities"]}
    quarantined = set(LANES["retained_quarantine_no_current_lane"]["capabilities"])
    consumed = set(LIVE_POST_RESULT_BINDINGS) | set(FROZEN_STRUCTURAL_CAPABILITIES)
    remaining = all_caps - consumed - quarantined
    expected = ORIGINAL_GAPS - set(FROZEN_STRUCTURAL_CAPABILITIES)
    if (len(all_caps) != 41 or len(quarantined) != 4
            or remaining != expected
            or (all_caps - set(LIVE_POST_RESULT_BINDINGS) - quarantined -
                (set(FROZEN_STRUCTURAL_CAPABILITIES) - ORIGINAL_GAPS)) != ORIGINAL_GAPS):
        raise ValueError("capability reconciliation does not match the registered initial 14-gap baseline")
    rows: dict[str, dict[str, Any]] = {}
    receipts = structural_diagnostic.get("receipts", {}) if isinstance(structural_diagnostic, dict) else {}
    for name in sorted(ORIGINAL_GAPS):
        if name in set(FROZEN_STRUCTURAL_CAPABILITIES):
            receipt = receipts.get(name)
            if structural_diagnostic.get("status") != "PASS" or not isinstance(receipt, dict):
                row = {"status": "INTEGRATION_IMPLEMENTED_NOT_EXECUTED_FOR_THIS_FREEZE",
                       "reason": "no validated hash-bound structural receipt for this historical source"}
            else:
                observed = receipt.get("execution_sha256")
                unsigned = dict(receipt)
                unsigned.pop("execution_sha256", None)
                if (observed != sha256_json(unsigned)
                        or receipt.get("capability") != name
                        or receipt.get("consumer") != "smart_post_result_report._structural_capability_diagnostic"
                        or receipt.get("predictive_weight_authorized") is not False):
                    raise ValueError("capability reconciliation received a forged execution receipt")
                row = {"status": "NATIVE_EXECUTION_CONSUMED_VERIFIED",
                       "native_function": receipt["native_function_executed"],
                       "execution_sha256": observed,
                       "external_skill_code_executed": False,
                       "predictive_weight_authorized": False}
        elif name in DEPENDENCIES:
            module = DEPENDENCIES[name]
            try:
                present = importlib.util.find_spec(module) is not None
            except (ValueError, ModuleNotFoundError):
                present = False
            row = {"status": "INSTALLED_NOT_CONSUMED" if present else "MISSING_DEPENDENCY",
                   "required_module": module,
                   "installed": bool(present), "native_execution_receipt": False,
                   "external_skill_code_executed": False}
            if name == "mlflow" and (base / "smart_experiment_lab.py").is_file():
                row["existing_native_entrypoint"] = "smart_experiment_lab.ExperimentRegistry.track_signed_post_result"
                row["native_consumer"] = "smart_operator.post_result_report_operation / mlflow-sync"
                row["integration_gap"] = (
                    "post-result secondary tracking executes after signed report creation; "
                    "only an MLflow SQLite run with verified SHA/readback proves consumption"
                )
                row["execution_receipt_must_be_checked_separately"] = True
        elif name in RESEARCH_ALIASES:
            row = {"status": "ROLE_OR_SOURCE_NOT_EXECUTED",
                   "reason": RESEARCH_ALIASES[name],
                   "native_execution_receipt": False,
                   "external_skill_code_executed": False}
        else:
            raise ValueError("unclassified capability remaining")
        rows[name] = row
    executed = sum(v["status"] == "NATIVE_EXECUTION_CONSUMED_VERIFIED" for v in rows.values())
    result = {"schema": SCHEMA, "status": "PASS",
              "original_gaps": len(ORIGINAL_GAPS),
              "registered_pertinent_capabilities": len(all_caps - quarantined),
              "registered_quarantined_capabilities": len(quarantined),
              "native_consumption_capabilities_total": len(consumed),
              "original_gaps_consumed_this_freeze": executed,
              "remaining_without_implemented_consumer": len(remaining),
              "remaining_not_proven_consumed": len(ORIGINAL_GAPS) - executed,
              "capabilities": rows,
              "external_skill_executions_claimed": 0,
              "predictive_weight_authorized": False,
              "prospective_superiority_proven": False}
    result["sha256"] = sha256_json(result)
    return result
