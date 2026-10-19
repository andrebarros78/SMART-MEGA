"""Immutable operator-entered Mega-Sena result authority; intentionally HTTP-free.

An operator report is authoritative for the *local operational input*, not
independent evidence that the draw occurred. Past frozen cards are immutable.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_official_result_validation import validate_official_payload

INPUT_SCHEMA = "SMART_OPERATOR_RESULT_INPUT_1"
RESULT_SCHEMA = "SMART_OPERATOR_RESULT_AUTHORITY_1"


def _sha(obj: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def _read_input(root: Path, source: str | Path, target: int) -> dict[str, Any]:
    path = Path(source)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError("operator input must be a regular project-local file")
    if path.stat().st_size > 64 * 1024:
        raise ValueError("operator result input too large")
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict) or obj.get("schema") != INPUT_SCHEMA:
        raise ValueError("operator result schema invalid")
    if type(obj.get("target_contest")) is not int or obj["target_contest"] != target:
        raise ValueError("operator result target mismatch")
    if not isinstance(obj.get("numbers"), list):
        raise ValueError("operator result numbers missing")
    if any(type(x) is not int for x in obj["numbers"]):
        raise ValueError("operator numbers must be integers")
    payload = {"numero": target, "listaDezenas": [str(x) for x in obj["numbers"]],
               "dataApuracao": obj.get("draw_date"), "acumulado": False}
    normalized = validate_official_payload(payload, target)
    return {"target_contest": target, "draw_date": normalized["draw_date_text"],
            "actual_numbers": normalized["numbers"], "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "input_file": str(path.relative_to(root)).replace("\\", "/")}


def _read_authority(root: Path, target: int) -> dict[str, Any]:
    path = root / f"SMART_OPERATOR_RESULT_{target}.json"
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError("operator result not yet registered")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema") != RESULT_SCHEMA:
        raise ValueError("operator result authority schema invalid")
    supplied = dict(obj)
    observed = supplied.pop("sha256", None)
    if observed != _sha(supplied):
        raise ValueError("operator result authority hash mismatch")
    if obj.get("target_contest") != target:
        raise ValueError("operator result authority target mismatch")
    validate_official_payload({"numero": target, "listaDezenas": obj.get("actual_numbers"),
                               "dataApuracao": obj.get("draw_date")}, target)
    return obj


def register(root: str | Path, target: int, source: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    target = int(target)
    validated = _read_input(root, source, target)
    path = root / f"SMART_OPERATOR_RESULT_{target}.json"
    if path.exists():
        existing = _read_authority(root, target)
        if (existing["actual_numbers"] != validated["actual_numbers"]
                or existing["draw_date"] != validated["draw_date"]):
            raise ValueError("operator result conflict: registered draw is immutable")
        return existing
    doc = {"schema": RESULT_SCHEMA, "status": "OPERATOR_RESULT_REGISTERED",
           "source": "OPERATOR", "source_independently_verified": False,
           "target_contest": target, "draw_date": validated["draw_date"],
           "actual_numbers": validated["actual_numbers"],
           "input_file": validated["input_file"], "input_sha256": validated["input_sha256"],
           "registered_at_utc": datetime.now(timezone.utc).isoformat(),
           "predictive_weight_authorized": False, "retroactive_rewrite": False}
    doc["sha256"] = _sha(doc)
    with path.open("x", encoding="utf-8") as out:
        json.dump(doc, out, ensure_ascii=False, indent=2)
        out.write("\n")
    return doc


def fetch(root: str | Path, target: int) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(root).resolve()
    obj = _read_authority(root, int(target))
    payload = {"numero": int(target), "listaDezenas": [f"{n:02d}" for n in obj["actual_numbers"]],
               "dataApuracao": obj["draw_date"], "acumulado": False, "source": "OPERATOR"}
    evidence = {
        "schema": "SMART_OFFICIAL_EVIDENCE_CONSENSUS_V1",
        "target_contest": int(target),
        "primary": {"channel": "OPERATOR", "endpoint": None,
                    "numbers": obj["actual_numbers"], "draw_date": obj["draw_date"],
                    "validated": True, "authority_sha256": obj["sha256"]},
        "secondary": None, "secondary_error": None,
        "status": "OPERATOR_ATTESTED_RESULT",
        "operational_adjudication_authorized": True, "dual_channel_corroborated": False,
        "terminal_source_corroboration_authorized": False,
        "independent_audit_still_required_for_terminal_6of6": True,
        "predictive_weight_authorized": False, "terminal_6of6_proven": False,
    }
    return payload, evidence
