from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_SCHEMA = "SMART_PROSPECTIVE_LEDGER_V1"
ENTRY_SCHEMA = "SMART_PROSPECTIVE_REGISTRATION_V1"


def canonical_json(document: Any) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(document: Any) -> str:
    return hashlib.sha256(canonical_json(document)).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_embedded_hash(document: dict[str, Any], label: str) -> None:
    observed = document.get("sha256")
    canonical = dict(document)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed != sha256_json(canonical):
        raise ValueError(f"{label} embedded hash mismatch")


def strict_top6(values: Any, label: str) -> list[int]:
    if not isinstance(values, list) or len(values) != 6:
        raise ValueError(f"{label} must contain six numbers")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError(f"{label} must contain integers")
    result = [int(value) for value in values]
    if len(set(result)) != 6 or min(result) < 1 or max(result) > 60:
        raise ValueError(f"{label} must contain six unique numbers in [1,60]")
    return result


def validate_probability_map(values: Any, label: str) -> dict[str, float]:
    expected = {str(number) for number in range(1, 61)}
    if not isinstance(values, dict) or set(values) != expected:
        raise ValueError(f"{label} must contain keys 1..60")
    result = {str(number): float(values[str(number)]) for number in range(1, 61)}
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in result.values()):
        raise ValueError(f"{label} contains probability outside [0,1]")
    if not math.isclose(sum(result.values()), 6.0, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError(f"{label} probabilities must sum to six")
    return result


def build_registration(
    freeze: dict[str, Any],
    freeze_file: str,
    freeze_file_sha256: str,
    main_freeze: dict[str, Any],
    main_freeze_file: str,
    main_freeze_sha256: str,
    registered_at_utc: str | None = None,
) -> dict[str, Any]:
    verify_embedded_hash(freeze, "frontier freeze")
    target = int(freeze.get("target_contest", -1))
    cutoff = int(freeze.get("cutoff_contest", -1))
    if target < 1 or cutoff != target - 1:
        raise ValueError("frontier freeze target/cutoff mismatch")
    if freeze.get("status") != "FROZEN_SHADOW_ONLY":
        raise ValueError("frontier freeze is not shadow-frozen")
    if freeze.get("result_used") is not False:
        raise ValueError("frontier freeze used target result")
    if freeze.get("production_authority") is not False:
        raise ValueError("frontier freeze has production authority")
    if float(freeze.get("material_weight", -1.0)) != 0.0:
        raise ValueError("frontier freeze material weight must be zero")

    if int(main_freeze.get("target_contest", -1)) != target:
        raise ValueError("main freeze target mismatch")
    if int(main_freeze.get("cutoff_contest", -1)) != cutoff:
        raise ValueError("main freeze cutoff mismatch")
    champion = strict_top6(main_freeze.get("champion", {}).get("top6"), "champion top6")
    challenger = strict_top6(
        main_freeze.get("challenger", {}).get("top6"), "challenger top6"
    )

    candidates = freeze.get("candidate_predictions")
    if not isinstance(candidates, dict) or not candidates:
        raise ValueError("candidate predictions are missing")
    retained: dict[str, Any] = {}
    for name in sorted(candidates):
        prediction = candidates[name]
        top6 = strict_top6(prediction.get("top6"), f"{name} top6")
        probabilities = validate_probability_map(
            prediction.get("probabilities"), f"{name} probabilities"
        )
        retained[name] = {
            "family": str(prediction.get("family")),
            "top6": top6,
            "probabilities": probabilities,
            "probability_sum": float(sum(probabilities.values())),
            "production_authority": False,
            "result_used": False,
        }

    entry = {
        "schema": ENTRY_SCHEMA,
        "registered_at_utc": registered_at_utc or datetime.now(timezone.utc).isoformat(),
        "target_contest": target,
        "target_date": freeze.get("target_date"),
        "cutoff_contest": cutoff,
        "frontier_freeze_file": freeze_file,
        "frontier_freeze_file_sha256": freeze_file_sha256,
        "frontier_freeze_embedded_sha256": freeze["sha256"],
        "frontier_frozen_utc": freeze.get("frozen_utc"),
        "main_freeze_file": main_freeze_file,
        "main_freeze_file_sha256": main_freeze_sha256,
        "champion_top6": champion,
        "challenger_top6": challenger,
        "candidate_predictions": retained,
        "candidate_count": len(retained),
        "all_60_probabilities_retained": True,
        "source_cutoff_before_target": True,
        "result_used": False,
        "result_available_at_registration": False,
        "production_switch_performed": False,
        "predictive_weight_authorized": False,
        "terminal_6of6_proven": False,
        "status": "REGISTERED_PROSPECTIVE_AWAITING_RESULT",
    }
    entry["entry_sha256"] = sha256_json(entry)
    return entry


def _atomic_write(path: Path, document: dict[str, Any]) -> None:
    handle, temporary = tempfile.mkstemp(
        prefix=path.stem + ".", suffix=".tmp.json", dir=path.parent
    )
    os.close(handle)
    temporary_path = Path(temporary)
    try:
        temporary_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def register(
    frontier_freeze_path: str | Path,
    main_freeze_path: str | Path,
    ledger_path: str | Path,
) -> dict[str, Any]:
    frontier_freeze_path = Path(frontier_freeze_path)
    main_freeze_path = Path(main_freeze_path)
    ledger_path = Path(ledger_path)
    freeze = json.loads(frontier_freeze_path.read_text(encoding="utf-8-sig"))
    main_freeze = json.loads(main_freeze_path.read_text(encoding="utf-8-sig"))
    entry = build_registration(
        freeze,
        frontier_freeze_path.name,
        sha256_file(frontier_freeze_path),
        main_freeze,
        main_freeze_path.name,
        sha256_file(main_freeze_path),
    )

    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
        if ledger.get("schema") != LEDGER_SCHEMA or not isinstance(ledger.get("entries"), list):
            raise ValueError("prospective ledger is invalid")
    else:
        ledger = {
            "schema": LEDGER_SCHEMA,
            "contract": {
                "append_only": True,
                "one_registration_per_target": True,
                "retain_all_60_probabilities": True,
                "adjudicate_only_from_official_result": True,
                "no_retroactive_reselection": True,
            },
            "entries": [],
        }

    existing = [
        item for item in ledger["entries"]
        if int(item.get("target_contest", -1)) == entry["target_contest"]
    ]
    if existing:
        if len(existing) != 1:
            raise ValueError("duplicate target registrations in prospective ledger")
        if (
            existing[0].get("frontier_freeze_file_sha256")
            != entry["frontier_freeze_file_sha256"]
        ):
            raise ValueError("target already registered with a different freeze")
        return existing[0]

    ledger["entries"].append(entry)
    ledger["ledger_sha256"] = sha256_json(
        {key: value for key, value in ledger.items() if key != "ledger_sha256"}
    )
    _atomic_write(ledger_path, ledger)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontier-freeze", required=True)
    parser.add_argument("--main-freeze", required=True)
    parser.add_argument("--ledger", default="SMART_PROSPECTIVE_LEDGER.json")
    args = parser.parse_args()
    entry = register(args.frontier_freeze, args.main_freeze, args.ledger)
    print(
        json.dumps(
            {
                "status": entry["status"],
                "target_contest": entry["target_contest"],
                "candidate_count": entry["candidate_count"],
                "all_60_probabilities_retained": entry[
                    "all_60_probabilities_retained"
                ],
                "entry_sha256": entry["entry_sha256"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
