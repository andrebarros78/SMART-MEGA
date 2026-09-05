from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JUNIT = "SMART_AUDIT_JUNIT_CURRENT.xml"
OUTPUT = Path(os.environ.get("SMART_CHECKPOINT_OUTPUT", str(ROOT / "SMART_EXECUTION_CHECKPOINT_20260904.json")))


def load_json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


def sha(name: str) -> str:
    h = hashlib.sha256()
    with (ROOT / name).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def junit_totals(name: str):
    root = ET.parse(ROOT / name).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag == "testsuites" and root.attrib.get("tests") is not None:
        tests = int(root.attrib.get("tests", 0))
        failures = int(root.attrib.get("failures", 0))
        errors = int(root.attrib.get("errors", 0))
        skipped = int(root.attrib.get("skipped", 0))
        if tests == 0:
            tests = sum(int(item.attrib.get("tests", 0)) for item in suites)
            failures = sum(int(item.attrib.get("failures", 0)) for item in suites)
            errors = sum(int(item.attrib.get("errors", 0)) for item in suites)
            skipped = sum(int(item.attrib.get("skipped", 0)) for item in suites)
    else:
        tests = sum(int(item.attrib.get("tests", 0)) for item in suites)
        failures = sum(int(item.attrib.get("failures", 0)) for item in suites)
        errors = sum(int(item.attrib.get("errors", 0)) for item in suites)
        skipped = sum(int(item.attrib.get("skipped", 0)) for item in suites)
    return {"tests": tests, "failures": failures, "errors": errors, "skipped": skipped}


freeze = load_json("SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json")
monte = load_json("SMART_MONTE_CARLO_CONVERGENCE_1000.json")
falsification = load_json("SMART_FALSIFICATION_REPORT_POWERED.json")
hypothesis = load_json("SMART_HYPOTHESIS_STATE_RECONCILIATION.json")
result_store = load_json("SMART_CANONICAL_RESULT_STORE_RECONCILIATION_3053.json")
preflight = load_json("SMART_3054_ADJUDICATION_PREFLIGHT.json")
full_cycle = load_json("SMART_3054_FULL_CYCLE_SANDBOX_PROOF.json")
terminal_sandbox = load_json("SMART_3054_TERMINAL_EXECUTOR_SANDBOX_PROOF.json")
independent = load_json("SMART_P14_INDEPENDENT_AUDIT_CURRENT.json")
authority = load_json("SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json")
mission = load_json("SMART_MISSION_STATUS.json")
junit = junit_totals(JUNIT)
resolution = bool(falsification.get("multiplicity", {}).get("resolution_sufficient"))

blockers = [
    "official contest 3054 result is not yet ingested/adjudicated",
    "no prospectively proven advantage over declared baselines",
    "terminal exact 6/6 has not occurred/proven",
    "independent terminal audit cannot occur before official 3054 adjudication",
]
if not resolution:
    blockers.append("falsification Monte Carlo resolution is insufficient for the declared multiplicity family")

obj = {
    "schema": "SMART_EXECUTION_CHECKPOINT_20260904_V3",
    "created_brasilia": datetime.now(timezone(timedelta(hours=-3))).isoformat(),
    "cutoff_contest": int(freeze["cutoff_contest"]),
    "target_contest": int(freeze["target_contest"]),
    "mission_state": mission["status"],
    "terminal_6of6_proven": bool(mission["terminal_6of6_proven"]),
    "completed": [
        "terminal authority repaired; historical engineering MISSION_PROVEN artifacts demoted",
        f"P1/P2 Monte Carlo cartography promoted to {int(monte['final_replications'])} final replications with convergence diagnostics",
        "agent/skill integration reconciled with no direct terminal/freeze/predictive authority",
        "prospective evidence authority reconciled to SMART_SIGNAL_LEDGER",
        "five frontier families rejected for predictive promotion on causal historical holdout",
        "3054 full probability vectors registered prospectively with zero production authority",
        f"falsification multiplicity power guard resolved with {int(falsification['replications'])} replications",
        "powered hypothesis state reconciled without interpreting non-rejection as proof of the null",
        f"canonical result store reconciled through contest {int(result_store['canonical_max_after'])}",
        f"3054 adjudication preflight status {preflight['readiness_status']}",
        f"3054 full post-result sandbox cycle status {full_cycle['status']}",
        f"independent audit current PASS over {int(independent['prospective_ledger']['pair_count'])} real adjudications",
        f"3054 terminal executor end-to-end sandbox status {terminal_sandbox['status']} with idempotent repeat",
        "official evidence policy separates operational CAIXA API authority from terminal corroboration",
        f"canonical regression {junit['tests']} tests, {junit['failures']} failures, {junit['errors']} errors",
    ],
    "regression": junit,
    "falsification_resolution": {
        "replications": int(falsification["replications"]),
        "minimum_replications_for_resolution": int(falsification["multiplicity"]["minimum_replications_for_resolution"]),
        "resolution_sufficient": resolution,
        "holdout_integrity": falsification.get("holdout_integrity"),
        "predictive_weight_authorized": bool(falsification.get("predictive_weight_authorized")),
    },
    "hypothesis_reconciliation": {
        "status": hypothesis["status"],
        "powered_experiment_id": hypothesis["experiment_record"]["experiment_id"],
        "holm_rejections": hypothesis["holm_rejections"],
        "predictive_weight_authorized": hypothesis["guardrails"]["predictive_weight_authorized"],
        "terminal_6of6_proven": hypothesis["guardrails"]["terminal_6of6_proven"],
    },
    "monte_carlo": {
        "final_replications": int(monte["final_replications"]),
        "predictive_weight_authorized": bool(monte.get("predictive_weight_authorized")),
    },
    "canonical_result_store": {
        "contest_max": int(result_store["canonical_max_after"]),
        "append_count": int(result_store["append_count"]),
        "ready_for_next_contest": bool(result_store["result_store_ready_for_next_contest"]),
        "freeze_unchanged": bool(result_store["freeze_3054_unchanged"]),
    },
    "prospective_3054": {
        "preflight_status": preflight["readiness_status"],
        "candidate_count": int(preflight["probability_ledger"]["candidate_count"]),
        "all_60_probabilities_retained": bool(preflight["probability_ledger"]["all_candidates_have_60_probabilities"]),
        "adjudicated": bool(preflight["sequence_before_result"]["adjudicated"]),
        "sandbox_duplicate_adjudication_rejected": bool(preflight["sandbox_rehearsal"]["duplicate_adjudication_rejected"]),
        "full_cycle_sandbox_status": full_cycle["status"],
        "full_cycle_sequence_valid": bool(full_cycle["sequence"]["valid"]),
        "full_cycle_learning_last_contest": int(full_cycle["learning"]["last_contest"]),
        "official_result_ingested": False,
        "terminal_6of6_proven": False,
        "terminal_executor_sandbox_status": terminal_sandbox["status"],
        "terminal_executor_repeat_idempotent": bool(terminal_sandbox["repeated_execution_idempotent"]),
        "terminal_executor_non_6of6_guards_pass": bool(terminal_sandbox["all_non_6of6_terminal_guards_pass"]),
        "independent_audit_pair_count": int(independent["prospective_ledger"]["pair_count"]),
        "prospective_authority_pair_count": int(authority["independent_audit"]["pair_count"]),
    },
    "critical_hashes": {
        "freeze_3054": sha("SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json"),
        "p1p2_proof": sha("SMART_P1_P2_CARTOGRAPHY_PROOF.json"),
        "mission_status": sha("SMART_MISSION_STATUS.json"),
        "probability_audit": sha("SMART_PROBABILITY_AUDIT.json"),
        "prospective_probability_ledger": sha("SMART_PROBABILITY_PROSPECTIVE_LEDGER.json"),
        "monte_carlo_1000": sha("SMART_MONTE_CARLO_CONVERGENCE_1000.json"),
        "falsification_powered": sha("SMART_FALSIFICATION_REPORT_POWERED.json"),
        "hypothesis_reconciliation": sha("SMART_HYPOTHESIS_STATE_RECONCILIATION.json"),
        "canonical_result_store_reconciliation": sha("SMART_CANONICAL_RESULT_STORE_RECONCILIATION_3053.json"),
        "adjudication_preflight_3054": sha("SMART_3054_ADJUDICATION_PREFLIGHT.json"),
        "full_cycle_sandbox_3054": sha("SMART_3054_FULL_CYCLE_SANDBOX_PROOF.json"),
        "terminal_executor_sandbox_3054": sha("SMART_3054_TERMINAL_EXECUTOR_SANDBOX_PROOF.json"),
        "terminal_executor_source": sha("smart_3054_terminal_executor.py"),
        "independent_audit_current": sha("SMART_P14_INDEPENDENT_AUDIT_CURRENT.json"),
        "prospective_evidence_authority": sha("SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json"),
        "current_junit": sha(JUNIT),
    },
    "freeze_3054_top6": sorted(int(value) for value in freeze["champion"]["top6"]),
    "current_blockers": blockers,
    "acquisition_decision": "NO_ADDITIONAL_SOFTWARE_ACQUISITION_REQUIRED_NOW",
    "next_gate": (
        "official 3054 CAIXA result -> validated operational evidence -> immutable adjudication -> causal replay learning -> "
        "sequential proof -> source corroboration/independent audit -> terminal-rule evaluation; no retroactive changes"
    ),
}

OUTPUT.write_text(
    json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps({
    "checkpoint": True,
    "schema": obj["schema"],
    "freeze": obj["critical_hashes"]["freeze_3054"],
    "blockers": len(blockers),
    "regression": junit,
    "falsification_resolution_sufficient": resolution,
    "preflight_3054": obj["prospective_3054"]["preflight_status"],
    "full_cycle_sandbox_3054": obj["prospective_3054"]["full_cycle_sandbox_status"],
}, ensure_ascii=False))
