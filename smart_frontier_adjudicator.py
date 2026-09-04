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

import numpy as np
import pandas as pd

from smart_frontier_signal_lab import CANDIDATES, FREEZE_SCHEMA, brier, sha256_file, sha256_json
from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import load_registry, write_registry

LEDGER_SCHEMA = "SMART_FRONTIER_LEDGER_1"


def _verify_embedded_hash(document: dict[str, Any], label: str) -> None:
    observed = document.get("sha256")
    canonical = dict(document)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed != sha256_json(canonical):
        raise ValueError(f"{label} embedded hash mismatch")


def _strict_top6(values: Any, label: str) -> list[int]:
    if not isinstance(values, list) or len(values) != 6:
        raise ValueError(f"{label} must contain six numbers")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError(f"{label} must contain integers")
    result = [int(value) for value in values]
    if len(set(result)) != 6 or min(result) < 1 or max(result) > 60:
        raise ValueError(f"{label} must contain six unique numbers in [1,60]")
    return result


def _load_result(path: Path, target: int) -> list[int]:
    frame = pd.read_excel(path)
    row = frame[frame["Concurso"].astype(int) == int(target)]
    if len(row) != 1:
        raise ValueError("target result must occur exactly once")
    numbers = [int(row.iloc[0][f"Bola{i}"]) for i in range(1, 7)]
    return sorted(_strict_top6(numbers, "official result"))


def _load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": LEDGER_SCHEMA, "events": []}
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != LEDGER_SCHEMA or not isinstance(document.get("events"), list):
        raise ValueError("frontier ledger is invalid")
    return document


def _atomic_json(path: Path, document: dict[str, Any]) -> None:
    path = Path(path)
    handle, temporary = tempfile.mkstemp(prefix=path.stem + ".", suffix=".tmp.json", dir=path.parent)
    os.close(handle)
    temporary_path = Path(temporary)
    try:
        temporary_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def adjudicate_frontier(
    freeze_path: Path,
    main_freeze_path: Path,
    result_data: Path,
    target: int,
    registry_path: Path,
    ledger_path: Path,
) -> dict[str, Any]:
    freeze_path = Path(freeze_path)
    main_freeze_path = Path(main_freeze_path)
    result_data = Path(result_data)
    registry_path = Path(registry_path)
    ledger_path = Path(ledger_path)

    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("schema") != FREEZE_SCHEMA:
        raise ValueError("frontier freeze schema mismatch")
    _verify_embedded_hash(freeze, "frontier freeze")
    if int(freeze.get("target_contest", -1)) != int(target) or int(freeze.get("cutoff_contest", -1)) != int(target) - 1:
        raise ValueError("frontier freeze target/cutoff mismatch")
    if freeze.get("production_authority") is not False or freeze.get("material_weight") != 0.0 or freeze.get("result_used") is not False:
        raise ValueError("frontier freeze is not shadow-only")
    predictions = freeze.get("candidate_predictions")
    if not isinstance(predictions, dict) or set(predictions) != set(CANDIDATES):
        raise ValueError("frontier freeze candidate set mismatch")

    main_freeze = json.loads(main_freeze_path.read_text(encoding="utf-8"))
    if int(main_freeze.get("target_contest", -1)) != int(target) or int(main_freeze.get("cutoff_contest", -1)) != int(target) - 1:
        raise ValueError("main freeze target/cutoff mismatch")
    champion = _strict_top6(main_freeze.get("champion", {}).get("top6"), "main Champion")

    ledger = _load_ledger(ledger_path)
    if any(event.get("event_type") == "FRONTIER_ADJUDICATION" and int(event.get("target_contest", -1)) == int(target)
           for event in ledger["events"]):
        raise ValueError("frontier contest already adjudicated")

    actual = _load_result(result_data, target)
    actual_set = set(actual)
    champion_set = set(champion)
    champion_hits = len(champion_set & actual_set)
    governance = load_registry(registry_path, tuple(SIGNAL_NAMES))
    registry_before = sha256_file(registry_path)
    evaluations: dict[str, Any] = {}

    for name, family in CANDIDATES.items():
        if name not in governance.candidates:
            raise ValueError(f"frontier candidate is not registered: {name}")
        state = governance.candidates[name]
        if state.family != family or state.registered_cutoff != int(target) - 1:
            raise ValueError(f"frontier candidate registration mismatch: {name}")
        prediction = predictions[name]
        top6 = _strict_top6(prediction.get("top6"), f"frontier top6 {name}")
        probabilities = prediction.get("probabilities")
        if not isinstance(probabilities, dict) or set(probabilities) != {str(i) for i in range(1, 61)}:
            raise ValueError(f"frontier probabilities invalid: {name}")
        probability_array = np.asarray([float(probabilities[str(i)]) for i in range(1, 61)], dtype=float)
        if not np.all(np.isfinite(probability_array)) or np.any(probability_array < 0.0) or np.any(probability_array > 1.0):
            raise ValueError(f"frontier probabilities outside [0,1]: {name}")
        if not math.isclose(float(probability_array.sum()), 6.0, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(f"frontier probabilities do not sum to six: {name}")
        candidate_set = set(top6)
        hits = len(candidate_set & actual_set)
        novelty = 1.0 - len(candidate_set & champion_set) / 6.0
        delta = hits - champion_hits
        update = governance.observe_oos(name, int(target), float(delta), float(novelty))
        evaluations[name] = {
            "family": family,
            "top6": top6,
            "hits": int(hits),
            "champion_hits": int(champion_hits),
            "delta_hits": int(delta),
            "novelty": float(novelty),
            "brier": brier(probability_array, np.asarray(actual, dtype=int)),
            "registry_update": update,
            "production_authority": False,
        }

    registry_after = write_registry(registry_path, governance)
    event = {
        "event_type": "FRONTIER_ADJUDICATION",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": int(target),
        "actual_numbers": actual,
        "champion_top6": champion,
        "champion_hits": int(champion_hits),
        "freeze_file": freeze_path.name,
        "freeze_sha256": sha256_file(freeze_path),
        "main_freeze_file": main_freeze_path.name,
        "main_freeze_sha256": sha256_file(main_freeze_path),
        "result_data_file": result_data.name,
        "result_data_sha256": sha256_file(result_data),
        "registry_sha256_before": registry_before,
        "registry_sha256_after": registry_after,
        "evaluations": evaluations,
        "all_candidates_evaluated": True,
        "retroactive_reselection": False,
        "production_switch_performed": False,
    }
    event["sha256"] = sha256_json(event)
    ledger["events"].append(event)
    _atomic_json(ledger_path, ledger)
    return {
        "status": "FRONTIER_ADJUDICATED",
        "target_contest": int(target),
        "actual_numbers": actual,
        "champion_hits": int(champion_hits),
        "candidate_hits": {name: row["hits"] for name, row in evaluations.items()},
        "registry_sha256": registry_after,
        "ledger_sha256": sha256_file(ledger_path),
        "event_sha256": event["sha256"],
        "production_switch_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--main-freeze", required=True)
    parser.add_argument("--result-data", required=True)
    parser.add_argument("--target", required=True, type=int)
    parser.add_argument("--registry", default="SMART_SIGNAL_EXPANSION_REGISTRY.json")
    parser.add_argument("--ledger", default="SMART_FRONTIER_LEDGER.json")
    args = parser.parse_args()
    print(json.dumps(adjudicate_frontier(
        Path(args.freeze),
        Path(args.main_freeze),
        Path(args.result_data),
        args.target,
        Path(args.registry),
        Path(args.ledger),
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
