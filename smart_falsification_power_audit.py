from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TARGET_HYPOTHESES = {
    "H_MARGINAL_001",
    "H_MEMORY_001",
    "H_GRAPH_001",
    "H_REGIME_001",
}


def sha(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def build_power_audit(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    report_path = root / "SMART_FALSIFICATION_REPORT_V2.json"
    report = read_json(report_path)
    family_size = int(report["multiplicity"]["family_size"])
    replications = int(report["replications"])
    alpha = float(report["multiplicity"]["alpha"])
    minimum_raw = 1.0 / (replications + 1)
    best_case_holm = min(1.0, family_size * minimum_raw)
    required = math.ceil(family_size / alpha - 1)

    powered_path = root / "SMART_FALSIFICATION_REPORT_POWERED.json"
    powered_supersedes_registry = False
    powered_sha256 = None
    if powered_path.exists():
        powered = read_json(powered_path)
        powered_supersedes_registry = bool(
            powered.get("multiplicity", {}).get("resolution_sufficient")
            and int(powered.get("replications", 0)) >= int(
                powered.get("multiplicity", {}).get("minimum_replications_for_resolution", 10**9)
            )
        )
        powered_sha256 = sha(powered_path)

    return {
        "schema": "SMART_FALSIFICATION_POWER_AUDIT_V2",
        "created_brasilia": datetime.now(timezone(timedelta(hours=-3))).isoformat(),
        "source_file": report_path.name,
        "source_sha256": sha(report_path),
        "replications": replications,
        "holm_family_size": family_size,
        "alpha": alpha,
        "minimum_raw_empirical_p": minimum_raw,
        "best_case_smallest_holm_adjusted_p": best_case_holm,
        "minimum_replications_to_make_any_holm_rejection_numerically_possible": required,
        "resolution_sufficient_for_alpha": bool(best_case_holm <= alpha),
        "classification": (
            "INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE"
            if best_case_holm > alpha
            else "RESOLUTION_ADEQUATE"
        ),
        "predictive_weight_authorized": False,
        "rule": "failure to reject under insufficient Monte Carlo resolution cannot be interpreted as evidence for the null",
        "registry_mutation": (
            "SKIPPED_SUPERSEDED_BY_POWERED_REPORT"
            if powered_supersedes_registry
            else "LEGACY_POWER_LIMIT_STATUS_APPLICABLE"
        ),
        "powered_report_sha256": powered_sha256,
    }


def write_power_audit(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    obj = build_power_audit(root)
    audit_path = root / "SMART_FALSIFICATION_POWER_AUDIT.json"
    audit_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if obj["registry_mutation"] != "SKIPPED_SUPERSEDED_BY_POWERED_REPORT":
        registry_path = root / "SMART_HYPOTHESIS_REGISTRY.json"
        registry = read_json(registry_path)
        for hypothesis in registry["hypotheses"]:
            if hypothesis["id"] in TARGET_HYPOTHESES:
                hypothesis["status"] = "INCONCLUSIVE_POWER_LIMITED_RETROSPECTIVE"
                hypothesis["power_audit"] = audit_path.name
                hypothesis["promotion_authority"] = False
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ledger_path = root / "SMART_EXPERIMENT_LEDGER.json"
    ledger = read_json(ledger_path)
    for record in ledger.get("records", []):
        if record.get("experiment_id") == "SMART_P4_P5_FALSIFICATION_3053_V1":
            record["decision"] = "INCONCLUSIVE"
            record["lesson"] = (
                "100-replication Monte Carlo cannot resolve alpha=0.05 after Holm over 10 comparisons; "
                "no predictive promotion and no evidence-for-null claim."
            )
            record["power_audit"] = audit_path.name
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return obj


if __name__ == "__main__":
    import sys

    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    print(json.dumps(write_power_audit(project_root), ensure_ascii=False))
