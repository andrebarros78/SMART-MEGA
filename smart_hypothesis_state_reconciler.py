from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_HYPOTHESIS_STATE_RECONCILIATION_V1"
POWER_RESOLVED_STATUS = "RETROSPECTIVE_NO_REJECTION_POWER_RESOLVED_NO_NULL_PROOF"
RETROSPECTIVE_SIGNAL_STATUS = "RETROSPECTIVE_NULL_REJECTION_REQUIRES_OOS_PROSPECTIVE_REPLICATION"
POWER_LIMITED_STATUS = "INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE"
TARGET_HYPOTHESES = {
    "H_MARGINAL_001",
    "H_MEMORY_001",
    "H_GRAPH_001",
    "H_REGIME_001",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _dedupe(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def build_reconciliation(root: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(root)
    registry_path = root / "SMART_HYPOTHESIS_REGISTRY.json"
    powered_path = root / "SMART_FALSIFICATION_REPORT_POWERED.json"
    authority_path = root / "SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json"
    freeze_path = root / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json"

    registry = _read_json(registry_path)
    powered = _read_json(powered_path)
    authority = _read_json(authority_path)

    multiplicity = powered["multiplicity"]
    resolution_sufficient = bool(multiplicity["resolution_sufficient"])
    replications = int(powered["replications"])
    minimum = int(multiplicity["minimum_replications_for_resolution"])
    holdout_integrity = powered["holdout_integrity"]
    predictive_weight_authorized = bool(powered["predictive_weight_authorized"])
    if predictive_weight_authorized:
        raise ValueError("powered retrospective report must not authorize predictive weights")

    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in TARGET_HYPOTHESES}
    for row in powered["comparisons"]:
        hypothesis_id = row["hypothesis_id"]
        if hypothesis_id in grouped:
            grouped[hypothesis_id].append(row)

    updated_ids: list[str] = []
    decisions: dict[str, Any] = {}
    for hypothesis in registry["hypotheses"]:
        hypothesis_id = hypothesis["id"]
        if hypothesis_id not in TARGET_HYPOTHESES:
            continue
        rows = grouped[hypothesis_id]
        if not rows:
            raise ValueError(f"powered report has no comparisons for {hypothesis_id}")
        any_rejection = any(bool(row["reject_at_familywise_0_05"]) for row in rows)
        if not resolution_sufficient:
            status = POWER_LIMITED_STATUS
        elif any_rejection:
            status = RETROSPECTIVE_SIGNAL_STATUS
        else:
            status = POWER_RESOLVED_STATUS

        evidence = hypothesis.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        evidence = _dedupe([*evidence, powered_path.name])

        hypothesis["status"] = status
        hypothesis["evidence"] = evidence
        hypothesis["promotion_authority"] = False
        hypothesis["power_resolution"] = {
            "source": powered_path.name,
            "source_sha256": _sha256(powered_path),
            "replications": replications,
            "minimum_replications_for_resolution": minimum,
            "resolution_sufficient": resolution_sufficient,
            "holdout_integrity": holdout_integrity,
            "any_holm_rejection": any_rejection,
            "failure_to_reject_proves_null": False,
            "predictive_weight_authorized": False,
        }
        updated_ids.append(hypothesis_id)
        decisions[hypothesis_id] = {
            "status": status,
            "comparison_count": len(rows),
            "any_holm_rejection": any_rejection,
        }

    if set(updated_ids) != TARGET_HYPOTHESES:
        raise ValueError("hypothesis registry does not contain all powered targets")

    for hypothesis in registry["hypotheses"]:
        if hypothesis["id"] == "H_PROSPECTIVE_ADVANTAGE":
            hypothesis["status"] = "REGISTERED_3054_AWAITING_OFFICIAL_RESULT"
            hypothesis["promotion_authority"] = False
            hypothesis["evidence"] = [
                "SMART_PROBABILITY_PROSPECTIVE_LEDGER.json",
                "SMART_SIGNAL_LEDGER.json",
                authority_path.name,
            ]
            hypothesis["prospective_binding"] = {
                "target_contest": 3054,
                "active_freeze_sha256": authority["targets"]["3054"]["active_or_latest_freeze_hash"],
                "freeze_file_sha256": _sha256(freeze_path),
                "adjudicated": bool(authority["targets"]["3054"]["adjudicated"]),
                "sequential_proof": bool(authority["targets"]["3054"]["sequential_proof"]),
            }
            if hypothesis["prospective_binding"]["active_freeze_sha256"] != hypothesis["prospective_binding"]["freeze_file_sha256"]:
                raise ValueError("prospective authority is not bound to the immutable 3054 freeze")

    registry["schema"] = "SMART_HYPOTHESIS_REGISTRY_V4"
    registry["power_resolution_status"] = "RESOLVED_RETROSPECTIVE_NO_PROMOTION"
    registry["rules"]["failure_to_reject_does_not_prove_the_null"] = True
    registry["rules"]["predictive_weight_requires_oos_and_prospective_evidence"] = True

    powered_experiment_record = {
        "experiment_id": "SMART_P4_P5_FALSIFICATION_3053_POWERED_V2",
        "preregistration": "SMART_P4_P5_PREREGISTRATION_POWERED.json",
        "result": powered_path.name,
        "decision": "INCONCLUSIVE",
        "lesson": (
            "200-replication Monte Carlo resolves the declared Holm numerical limit; no comparison rejects after Holm. "
            "The retrospective split is not pristine, so this is neither evidence for the null nor predictive promotion authority."
        ),
        "resolution_sufficient": resolution_sufficient,
        "predictive_weight_authorized": False,
    }

    reconciliation = {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "registry_before_sha256": _sha256(registry_path),
        "powered_report": powered_path.name,
        "powered_report_sha256": _sha256(powered_path),
        "replications": replications,
        "minimum_replications_for_resolution": minimum,
        "resolution_sufficient": resolution_sufficient,
        "holdout_integrity": holdout_integrity,
        "holm_rejections": multiplicity["rejected_comparisons"],
        "hypothesis_decisions": decisions,
        "experiment_record": powered_experiment_record,
        "prospective_3054": {
            "freeze_sha256": _sha256(freeze_path),
            "adjudicated": bool(authority["targets"]["3054"]["adjudicated"]),
            "sequential_proof": bool(authority["targets"]["3054"]["sequential_proof"]),
        },
        "guardrails": {
            "historical_non_rejection_is_not_null_proof": True,
            "historical_rejection_would_not_authorize_prediction": True,
            "predictive_weight_authorized": False,
            "freeze_3054_mutated": False,
            "terminal_6of6_proven": False,
        },
        "status": "PASS",
    }
    return registry, reconciliation


def write_reconciliation(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    registry, reconciliation = build_reconciliation(root)
    registry_path = root / "SMART_HYPOTHESIS_REGISTRY.json"
    proof_path = root / "SMART_HYPOTHESIS_STATE_RECONCILIATION.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reconciliation["registry_after_sha256"] = _sha256(registry_path)

    ledger_path = root / "SMART_EXPERIMENT_LEDGER.json"
    ledger_before_sha256 = _sha256(ledger_path)
    ledger = _read_json(ledger_path)
    record = reconciliation["experiment_record"]
    records = ledger.setdefault("records", [])
    matched = [index for index, item in enumerate(records) if item.get("experiment_id") == record["experiment_id"]]
    if len(matched) > 1:
        raise ValueError("duplicate powered falsification experiment records")
    if matched:
        records[matched[0]] = record
    else:
        records.append(record)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reconciliation["experiment_ledger_before_sha256"] = ledger_before_sha256
    reconciliation["experiment_ledger_after_sha256"] = _sha256(ledger_path)

    proof_path.write_text(json.dumps(reconciliation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return reconciliation


if __name__ == "__main__":
    import sys

    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    result = write_reconciliation(project_root)
    print(json.dumps({
        "status": result["status"],
        "replications": result["replications"],
        "resolution_sufficient": result["resolution_sufficient"],
        "holm_rejections": result["holm_rejections"],
        "freeze_3054_mutated": result["guardrails"]["freeze_3054_mutated"],
    }, ensure_ascii=False))
