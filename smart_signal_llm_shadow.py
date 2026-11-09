"""Validate external LLM hypotheses for prospective shadow use only.

This module makes no provider call. Provider identity is a self-reported label;
only a separately verified external receipt could prove actual LLM inference.
No proposal has champion, predictive-weight or freeze authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_LLM_SHADOW_PROPOSAL_1"
CANDIDATE_ID = "llm_shadow_v1"
FAMILY = "external_llm_experimental"
MAX_BYTES = 65536
EXPECTED_KEYS = frozenset({
    "schema", "target_contest", "cutoff_contest", "history_sha256",
    "generated_utc", "provider_claim", "model_claim", "prompt_sha256",
    "scores", "result_used", "production_authority", "sha256",
})
NUMBERS = frozenset(str(i) for i in range(1, 61))
HEX = re.compile(r"[0-9a-f]{64}\Z")


def _canonical_sha256(document: Any) -> str:
    raw = json.dumps(
        document, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    doc: dict[str, Any] = {}
    for key, value in pairs:
        if key in doc:
            raise ValueError("duplicate JSON field in LLM proposal")
        doc[key] = value
    return doc


def _utc(value: Any, label: str) -> datetime:
    if type(value) is not str:
        raise ValueError(f"{label} must be a timezone-aware ISO datetime")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be a timezone-aware ISO datetime") from exc
    if result.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return result.astimezone(timezone.utc)


def load_proposal(
    path: str | Path, *, target: int, history_sha256: str,
    frozen_at_utc: str,
) -> dict[str, Any]:
    """Fail closed on stale, leaky, malformed or unbound external score proposals."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("LLM proposal must be a bounded regular file")
    raw = path.read_bytes()
    try:
        doc = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("LLM proposal must be strict JSON") from exc
    if not isinstance(doc, dict) or set(doc) != EXPECTED_KEYS:
        raise ValueError("LLM proposal contract fields mismatch")
    if doc["schema"] != SCHEMA:
        raise ValueError("LLM proposal schema mismatch")
    if type(target) is not int or type(doc["target_contest"]) is not int or doc["target_contest"] != target:
        raise ValueError("LLM proposal target mismatch")
    if type(doc["cutoff_contest"]) is not int or doc["cutoff_contest"] != target - 1:
        raise ValueError("LLM proposal cutoff mismatch")
    if not isinstance(history_sha256, str) or not HEX.fullmatch(history_sha256):
        raise ValueError("expected history hash invalid")
    if doc["history_sha256"] != history_sha256:
        raise ValueError("LLM proposal history hash mismatch")
    if doc["result_used"] is not False or doc["production_authority"] is not False:
        raise ValueError("LLM proposal must not use results or claim production authority")
    timestamp = _utc(doc["generated_utc"], "generated_utc")
    frozen = _utc(frozen_at_utc, "frozen_at_utc")
    if timestamp > frozen:
        raise ValueError("LLM proposal timestamp is after frozen time")
    if not all(
        type(doc[field]) is str and 0 < len(doc[field].strip()) <= 120
        and all(ord(ch) >= 32 for ch in doc[field])
        for field in ("provider_claim", "model_claim")
    ):
        raise ValueError("LLM proposal provider/model labels invalid")
    if not isinstance(doc["prompt_sha256"], str) or not HEX.fullmatch(doc["prompt_sha256"]):
        raise ValueError("LLM proposal prompt SHA invalid")
    scores = doc["scores"]
    if not isinstance(scores, dict) or set(scores) != NUMBERS:
        raise ValueError("LLM proposal must cover all 60 scores")
    if any(
        type(value) not in (int, float) or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
        for value in scores.values()
    ):
        raise ValueError("LLM scores must be finite numeric scores in [0, 1]")
    observed = doc["sha256"]
    if (not isinstance(observed, str) or not HEX.fullmatch(observed)
            or observed != _canonical_sha256({k: v for k, v in doc.items() if k != "sha256"})):
        raise ValueError("LLM proposal embedded hash mismatch")
    return {
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY,
        "scores": {str(i): float(scores[str(i)]) for i in range(1, 61)},
        "generated_utc": timestamp.isoformat(),
        "input_file": path.name,
        "input_file_sha256": hashlib.sha256(raw).hexdigest(),
        "input_embedded_sha256": observed,
        "prompt_sha256": doc["prompt_sha256"],
        "provider_claim": doc["provider_claim"],
        "model_claim": doc["model_claim"],
        "provider_verified": False,
        "external_model_call_proven": False,
        "predictive_benefit_proven": False,
        "result_used": False,
        "production_authority": False,
    }
