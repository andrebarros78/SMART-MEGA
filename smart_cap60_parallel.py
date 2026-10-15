"""Research-only cap-60 parallel card, bound to the productive freeze.

This module never changes the champion engine, primary card, authoritative
ledger, weights consumed by production, or an existing frozen artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import smart_v2_engine as e
import freeze_next_research as champion_engine
import smart_cap60_experiment_engine as experimental_engine

SCHEMA = "SMART_CAP60_PARALLEL_CARD_1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(obj: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _numbers(top: Any) -> list[int]:
    if (not isinstance(top, list) or len(top) != 6
            or any(type(v) is not int or v < 1 or v > 60 for v in top)
            or len(set(top)) != 6):
        raise ValueError("invalid frozen six-number card")
    return sorted(top)


def _file(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError("artifact path must be root-relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("artifact path escapes canonical root")
    return path


def _verify_record(doc: dict[str, Any]) -> None:
    observed = doc.get("sha256")
    plain = dict(doc)
    plain.pop("sha256", None)
    if doc.get("schema") != SCHEMA or not isinstance(observed, str) or observed != _digest(plain):
        raise ValueError("shadow artifact self-hash mismatch")
    if (doc.get("production_authority") is not False
            or doc.get("material_weight") != 0.0
            or doc.get("result_used") is not False
            or doc.get("production_switch_performed") is not False):
        raise ValueError("shadow artifact authority violation")


def produce(root: str | Path, freeze_file: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    freeze_path = _file(root, str(freeze_file))
    frozen_bytes_sha = _sha(freeze_path)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8-sig"))
    target = freeze.get("target_contest")
    cutoff = freeze.get("cutoff_contest")
    if (type(target) is not int or type(cutoff) is not int
            or cutoff != target - 1 or target <= 0
            or freeze.get("frozen_before_result") is not True
            or freeze.get("champion_remains_active") is not True
            or freeze.get("production_switch_performed") is not False):
        raise ValueError("not a verified pre-result champion freeze")
    data_path = _file(root, str(freeze.get("data_file") or ""))
    data_sha = _sha(data_path)
    if data_sha != freeze.get("data_sha256"):
        raise ValueError("frozen dataset hash mismatch")
    draws, contests = e.load_draws(data_path)
    if int(contests[-1]) != cutoff or len(draws) <= int(freeze.get("start_index", 1000)):
        raise ValueError("frozen history does not end immediately before target")
    original_sha = _sha(root / "freeze_next_research.py")
    if original_sha != freeze.get("champion_engine_sha256"):
        raise ValueError("champion source differs from frozen champion source")
    start = int(freeze.get("start_index", 1000))
    champion = champion_engine.current_policy(draws, start=start)
    original_top6 = _numbers(freeze["champion"]["top6"])
    if _numbers(champion["top6"]) != original_top6:
        raise ValueError("champion replay differs from authoritative freeze")
    candidate = experimental_engine.current_policy(draws, start=start)
    top6 = _numbers(candidate["top6"])
    frequency = {}
    for family, weight in candidate["family_weights"].items():
        if not 0 < weight <= 1:
            raise ValueError("invalid family weight")
        shares = [v / weight for k, v in candidate["expert_weights"].items()
                  if e.family_of(k) == family]
        if not shares or max(shares) > 0.6000000001:
            raise ValueError("experimental family-expert cap exceeded")
        frequency[family] = max(shares)
    out = {
        "schema": SCHEMA,
        "status": "FROZEN_SHADOW_ONLY",
        "target_contest": target,
        "cutoff_contest": cutoff,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_file": str(freeze_path.relative_to(root)),
        "freeze_file_sha256": frozen_bytes_sha,
        "data_file": str(data_path.relative_to(root)),
        "data_sha256": data_sha,
        "champion_engine_sha256": original_sha,
        "experimental_engine_sha256": _sha(root / "smart_cap60_experiment_engine.py"),
        "start_index": start,
        "champion_card": original_top6,
        "experimental_card": top6,
        "same_card": original_top6 == top6,
        "family_max_expert_share": frequency,
        "candidate_family_weights": candidate["family_weights"],
        "candidate_expert_weights": candidate["expert_weights"],
        "candidate_aggregate_scores": candidate["aggregate_scores"],
        "candidate_ranking60": candidate["ranking60"],
        "production_authority": False,
        "material_weight": 0.0,
        "result_used": False,
        "production_switch_performed": False,
        "prospective_promotion_authority": False,
        "timestamp_proof": "requires separate GitHub pre-draw registration; generated_utc alone is not proof",
    }
    out["sha256"] = _digest(out)
    destination = freeze_path.with_name(f"SMART_{target}_CAP60_PARALLEL_CARD.json")
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8-sig"))
        _verify_record(existing)
        if (existing.get("freeze_file_sha256") != frozen_bytes_sha
                or existing.get("experimental_engine_sha256") != out["experimental_engine_sha256"]
                or existing.get("data_sha256") != data_sha):
            raise ValueError("existing shadow artifact bound to different source")
        return {"status": "ALREADY_FROZEN_SHADOW", "file": str(destination.relative_to(root)),
                "sha256": _sha(destination), "card": existing["experimental_card"],
                "production_authority": False}
    fd, temp = tempfile.mkstemp(prefix=".cap60_", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(out, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, destination)  # create-only, never overwrite signed evidence
    finally:
        Path(temp).unlink(missing_ok=True)
    return {"status": "FROZEN_SHADOW_ONLY", "file": str(destination.relative_to(root)),
            "sha256": _sha(destination), "card": top6,
            "production_authority": False}
