"""Idempotent independent lottery card when the preceding epoch is unresolved.

The output is an explicit uniform-random contingency, never a champion/model
prediction, a frozen prospective attempt, or an adjudication authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_INDEPENDENT_CONTINGENCY_CARD_1"
RELATIVE_DIR = Path("runtime") / "contingency_cards"


def _digest(document: dict[str, Any]) -> str:
    body = {k: v for k, v in document.items() if k != "sha256"}
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verify(document: dict[str, Any], target: int, prior_target: int,
            lifecycle_sha256: str) -> None:
    if (document.get("schema") != SCHEMA or document.get("status") != "CONTINGENCY_NOT_CERTIFIED"
            or document.get("target_contest") != target
            or document.get("preceding_contest") != prior_target
            or document.get("lifecycle_sha256_at_generation") != lifecycle_sha256):
        raise ValueError("contingency card authority mismatch")
    numbers = document.get("numbers")
    if not (isinstance(numbers, list) and len(numbers) == 6
            and all(type(number) is int and 1 <= number <= 60 for number in numbers)
            and numbers == sorted(set(numbers))):
        raise ValueError("contingency card numbers invalid")
    if any(document.get(k) is not False for k in
           ("model_certified", "predictive_advantage_proven", "scientific_proof", "changes_productive_epoch")):
        raise ValueError("contingency card falsely claims certification")
    if document.get("method") != "UNIFORM_CSPRNG_6_OF_60":
        raise ValueError("contingency card generation method invalid")
    if document.get("sha256") != _digest(document):
        raise ValueError("contingency card integrity failure")


def generate_contingency_card(root: str | Path, target: int, *,
                              preceding_target: int, lifecycle_sha256: str,
                              chooser: Any = None, now: datetime | None = None) -> dict[str, Any]:
    """Create or replay one nonproductive card, independent of adjudication.

    Only the immediately next contest is eligible. Never rewrites the active
    lifecycle, training data, signal weights, frozen predictions, or ledger.
    """
    if (type(target) is not int or type(preceding_target) is not int
            or preceding_target <= 1 or target != preceding_target + 1):
        raise ValueError("contingency generation requires immediately next contest")
    if (not isinstance(lifecycle_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", lifecycle_sha256) is None):
        raise ValueError("prior operational lifecycle SHA-256 invalid")
    project = Path(root).resolve()
    if not project.is_dir():
        raise FileNotFoundError("canonical project directory unavailable")
    folder = project / RELATIVE_DIR
    filepath = folder / f"SMART_CONTINGENCY_CARD_{target}.json"
    if filepath.is_file():
        document = json.loads(filepath.read_text(encoding="utf-8"))
        _verify(document, target, preceding_target, lifecycle_sha256)
        return {**document, "idempotent_replay": True, "receipt_file": filepath.relative_to(project).as_posix()}
    if filepath.exists():
        raise ValueError("existing contingency card is not a regular file")

    rng = chooser if chooser is not None else secrets.SystemRandom()
    picked = sorted(rng.sample(range(1, 61), 6))
    if len(set(picked)) != 6 or any(type(v) is not int or v < 1 or v > 60 for v in picked):
        raise ValueError("random generator produced an invalid card")
    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("generation timestamp must be timezone-aware")
    document = {
        "schema": SCHEMA,
        "status": "CONTINGENCY_NOT_CERTIFIED",
        "target_contest": target,
        "preceding_contest": preceding_target,
        "lifecycle_sha256_at_generation": lifecycle_sha256,
        "numbers": picked,
        "method": "UNIFORM_CSPRNG_6_OF_60",
        "created_utc": clock.astimezone(timezone.utc).isoformat(),
        "model_certified": False,
        "predictive_advantage_proven": False,
        "scientific_proof": False,
        "changes_productive_epoch": False,
        "adjudication_required": False,
        "next_cycle_freeze_authority": False,
        "result_3071_used_in_selection": False,
    }
    document["sha256"] = _digest(document)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with filepath.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError:
        replay = json.loads(filepath.read_text(encoding="utf-8"))
        _verify(replay, target, preceding_target, lifecycle_sha256)
        return {**replay, "idempotent_replay": True, "receipt_file": filepath.relative_to(project).as_posix()}
    _verify(document, target, preceding_target, lifecycle_sha256)
    return {**document, "idempotent_replay": False, "receipt_file": filepath.relative_to(project).as_posix()}
