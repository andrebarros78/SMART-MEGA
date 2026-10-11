"""Read-only, non-predictive bridge for visual learning metadata.

This adapter only records observational provenance in the prospective proof.
It never supplies a feature, weight or rank to card selection.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _hash_json(doc: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def inspect_visual_learning_shadow(
    root: str | Path, target_contest: int, cutoff_contest: int
) -> dict[str, Any]:
    """Inspect one optional bounded state file; never promote it."""
    result = {
        "schema": "SMART_VISUAL_LEARNING_SHADOW_LINK_V1",
        "status": "UNAVAILABLE",
        "target_contest": int(target_contest),
        "cutoff_contest": int(cutoff_contest),
        "source": "runtime/video_observation/SMART_VISUAL_LEARNING_STATE.json",
        "production_influence": False,
        "probability_weights_changed": False,
        "candidate_ranking_changed": False,
        "predictive_evidence": "NOT_ESTABLISHED",
        "training_observations": 0,
        "training_contests": [],
        "source_file_sha256": None,
    }
    path = Path(root) / result["source"]
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 262144:
            return result
        raw = path.read_bytes()
        doc = json.loads(raw)
        if not isinstance(doc, dict) or doc.get("schema") != "SMART_VISUAL_LEARNING_STATE_V1":
            return {**result, "status": "REJECTED_SCHEMA"}
        digest = doc.get("sha256")
        body = dict(doc)
        body.pop("sha256", None)
        if not isinstance(digest, str) or digest != _hash_json(body):
            return {**result, "status": "REJECTED_INTEGRITY"}
        prior = doc.get("observation_prior")
        ids = doc.get("training_contests")
        hashes = doc.get("training_sha256")
        if not isinstance(prior, dict) or not isinstance(ids, list) or not isinstance(hashes, dict):
            return {**result, "status": "REJECTED_EVIDENCE"}
        if (doc.get("next_contest") != str(target_contest)
            or doc.get("promotion_authorized") is not False
            or doc.get("same_contest_predictive_weight_authorized") is not False
            or doc.get("predictive_evidence") != "NOT_ESTABLISHED"
            or prior.get("predictive_evidence") != "NOT_ESTABLISHED"
            or not all(isinstance(n, int) and 0 < n <= cutoff_contest for n in ids)
            or len(ids) != len(set(ids))
            or set(hashes) != {str(n) for n in ids}
            or not all(isinstance(v, str) and len(v) == 64 and
                       all(c in "0123456789abcdef" for c in v) for v in hashes.values())
            or doc.get("training_observations") != len(ids)):
            return {**result, "status": "REJECTED_CAUSALITY"}
        return {
            **result,
            "status": "SHADOW_AVAILABLE" if prior.get("active") is True else "SHADOW_INACTIVE",
            "training_observations": len(ids),
            "training_contests": ids,
            "source_file_sha256": hashlib.sha256(raw).hexdigest(),
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {**result, "status": "UNREADABLE"}
