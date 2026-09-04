from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha(name: str) -> str:
    h = hashlib.sha256()
    with (ROOT / name).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def junit_totals(name: str):
    root = ET.parse(ROOT / name).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = sum(int(s.attrib.get("tests", 0)) for s in suites)
    failures = sum(int(s.attrib.get("failures", 0)) for s in suites)
    errors = sum(int(s.attrib.get("errors", 0)) for s in suites)
    skipped = sum(int(s.attrib.get("skipped", 0)) for s in suites)
    return {"tests": tests, "failures": failures, "errors": errors, "skipped": skipped}


freeze = load_json("SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json")
monte = load_json("SMART_MONTE_CARLO_CONVERGENCE_1000.json")
falsification = load_json("SMART_FALSIFICATION_REPORT_POWERED.json")
mission = load_json("SMART_MISSION_STATUS.json")
junit = junit_totals("SMART_AUDIT_JUNIT_CURRENT.xml")
resolution = bool(falsification.get("multiplicity", {}).get("resolution_sufficient"))

blockers = [
    "no prospectively proven advantage over declared baselines",
    "terminal exact 6/6 has not occurred/proven",
]
if not resolution:
    blockers.append("falsification Monte Carlo resolution is insufficient for the declared multiplicity family")

obj = {
    "schema": "SMART_EXECUTION_CHECKPOINT_20260904_V2",
    "created_brasilia": datetime.now(timezone(timedelta(hours=-3))).isoformat(),
    "cutoff_contest": int(freeze["cutoff_contest"]),
    "target_contest": int(freeze["target_contest"]),
    "mission_state": mission["status"],
    "terminal_6of6_proven": bool(mission["terminal_6of6_proven"]),
    "completed": [
        "terminal authority repaired; historical engineering MISSION_PROVEN artifacts demoted",
        f"P1/P2 Monte Carlo cartography promoted to {int(monte['final_replications'])} final replications with convergence diagnostics",
        "model registry rebound exactly to immutable 3054 freeze",
        "prospective evidence authority reconciled to SMART_SIGNAL_LEDGER",
        "five frontier families rejected for predictive promotion on causal historical holdout",
        "probability audit retains uniform baseline for all five frontier candidates",
        "3054 full probability vectors registered prospectively with zero production authority",
        f"falsification multiplicity power guard: {int(falsification['replications'])} replications; resolution_sufficient={str(resolution).lower()}",
        f"canonical deployment regression {junit['tests']} tests, {junit['failures']} failures, {junit['errors']} errors",
    ],
    "regression": junit,
    "falsification_resolution": {
        "replications": int(falsification["replications"]),
        "minimum_replications_for_resolution": int(falsification["multiplicity"]["minimum_replications_for_resolution"]),
        "resolution_sufficient": resolution,
        "holdout_integrity": falsification.get("holdout_integrity"),
        "predictive_weight_authorized": bool(falsification.get("predictive_weight_authorized")),
    },
    "monte_carlo": {
        "final_replications": int(monte["final_replications"]),
        "predictive_weight_authorized": bool(monte.get("predictive_weight_authorized")),
    },
    "critical_hashes": {
        "freeze_3054": sha("SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json"),
        "p1p2_proof": sha("SMART_P1_P2_CARTOGRAPHY_PROOF.json"),
        "mission_status": sha("SMART_MISSION_STATUS.json"),
        "probability_audit": sha("SMART_PROBABILITY_AUDIT.json"),
        "prospective_probability_ledger": sha("SMART_PROBABILITY_PROSPECTIVE_LEDGER.json"),
        "monte_carlo_1000": sha("SMART_MONTE_CARLO_CONVERGENCE_1000.json"),
        "falsification_powered": sha("SMART_FALSIFICATION_REPORT_POWERED.json"),
        "current_junit": sha("SMART_AUDIT_JUNIT_CURRENT.xml"),
    },
    "freeze_3054_top6": sorted(int(x) for x in freeze["champion"]["top6"]),
    "current_blockers": blockers,
    "acquisition_decision": "NO_ADDITIONAL_SOFTWARE_ACQUISITION_REQUIRED_NOW",
    "next_gate": "official 3054 result -> immutable adjudication -> scoring/calibration -> learning -> next freeze; no retroactive changes",
}

(ROOT / "SMART_EXECUTION_CHECKPOINT_20260904.json").write_text(
    json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({
    "checkpoint": True,
    "schema": obj["schema"],
    "freeze": obj["critical_hashes"]["freeze_3054"],
    "blockers": len(blockers),
    "regression": junit,
    "falsification_resolution_sufficient": resolution,
}))
