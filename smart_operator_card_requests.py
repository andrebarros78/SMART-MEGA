"""Issue one distinct six-number card only for each explicit operator request.

This consumes an already-frozen champion; it does NOT refreeze, adjudicate,
promote models, or authorize automatic generation. No per-contest quota.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from smart_primary_card_selector import select_primary_card

SCHEMA = "SMART_OPERATOR_CARD_REQUEST_1"
REQUEST_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("card evidence file path missing")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or candidate.is_symlink():
        raise ValueError("card evidence path outside project")
    return candidate


def _six(values):
    if (not isinstance(values, list) or len(values) != 6
            or any(type(n) is not int or n < 1 or n > 60 for n in values)
            or len(set(values)) != 6):
        raise ValueError("each operator-requested card requires six unique integers 1..60")
    return sorted(values)


def _verified_receipt(path, contest, freeze_sha):
    if path.is_symlink() or not path.is_file():
        raise ValueError("operator card receipt missing or linked")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    checksum = value.pop("sha256", None)
    if (value.get("schema") != SCHEMA or value.get("target_contest") != contest
            or value.get("freeze_sha256") != freeze_sha
            or not isinstance(checksum, str) or _hash(value) != checksum):
        raise ValueError("operator card receipt integrity mismatch")
    value["sha256"] = checksum
    _six(value.get("numbers"))
    return value


def issue_from_frozen_epoch(root, *, target, request_id, active, operator_requested=False):
    """Return one immutable receipt per request; distinct requests choose distinct cards.

    Authority must be checked by the outer operator command (lifecycle FROZEN
    and a verified pre-draw window). An explicit request is required even in
    an engineering-only call. No result is ever used.
    """
    if operator_requested is not True:
        raise PermissionError("only an explicit operator request may issue a card")
    if type(target) is not int or target < 1:
        raise ValueError("target contest must be positive integer")
    if not isinstance(request_id, str) or not REQUEST_RE.fullmatch(request_id):
        raise ValueError("operator request id invalid")
    root = Path(root).resolve()
    if (not isinstance(active, dict) or active.get("status") != "FROZEN"
            or active.get("target_contest") != target
            or active.get("cutoff_contest") != target - 1
            or active.get("operator_selected_target") is not True):
        raise PermissionError("no operator-authorized frozen epoch for this target")

    authority = active.get("freeze_authority")
    if not isinstance(authority, dict):
        raise ValueError("frozen model authority missing")
    expected_freeze_sha = authority.get("sha256")
    freeze_file = _path(root, authority.get("file"))
    if not freeze_file.is_file() or _file_sha(freeze_file) != expected_freeze_sha:
        raise ValueError("frozen model evidence hash mismatch")
    freeze = json.loads(freeze_file.read_text(encoding="utf-8-sig"))
    if (freeze.get("target_contest") != target
            or freeze.get("cutoff_contest") != target - 1
            or freeze.get("frozen_before_result") is not True
            or freeze.get("champion_remains_active") is not True):
        raise ValueError("model has no valid pre-result champion authority")

    state = active.get("state_paths")
    if not isinstance(state, dict):
        raise ValueError("frozen epoch state paths missing")
    ledger_file = _path(root, state.get("ledger"))
    ledger = json.loads(ledger_file.read_text(encoding="utf-8-sig"))
    events = [e for e in ledger.get("events", []) if e.get("target_contest") == target]
    if (len([e for e in events if e.get("event_type") == "FREEZE"
             and e.get("freeze_sha256") == expected_freeze_sha]) != 1
            or any(e.get("event_type") in ("ADJUDICATION", "LEARNING_UPDATE", "SEQUENTIAL_PROOF")
                   for e in events)):
        raise ValueError("invalid pre-result freeze ledger or result already available")

    primary_file = ledger_file.parent / f"SMART_{target}_PRIMARY_CARD.json"
    if primary_file.is_symlink() or not primary_file.is_file():
        raise ValueError("frozen primary card source unavailable")
    primary = json.loads(primary_file.read_text(encoding="utf-8-sig"))
    primary_hash = primary.get("sha256")
    if (not isinstance(primary_hash, str)
            or _hash({k: v for k, v in primary.items() if k != "sha256"}) != primary_hash
            or primary.get("target_contest") != target
            or primary.get("freeze_sha256") != expected_freeze_sha
            or primary.get("product_role") != "FINAL_SINGLE_CARD_PRODUCT"
            or primary.get("source_head") != "champion"
            or primary.get("status") != "FROZEN" or primary.get("result_used") is not False
            or primary.get("selector", {}).get("result_used") is not False):
        raise ValueError("frozen champion six-number card source integrity failure")
    first_card = _six(primary.get("numbers"))

    output_dir = root / "runtime" / "operator_card_requests" / str(target)
    if output_dir.is_symlink() or (output_dir.exists() and not output_dir.is_dir()):
        raise ValueError("operator request receipt directory invalid")
    existing = []
    for file in sorted(output_dir.glob("CARD-*.json")) if output_dir.is_dir() else ():
        record = _verified_receipt(file, target, expected_freeze_sha)
        if file.name != f"CARD-{record.get('request_ordinal'):04d}-{record.get('operator_request_id')}.json":
            raise ValueError("operator card receipt filename mismatch")
        existing.append(record)
    ordinals = [x.get("request_ordinal") for x in existing]
    if ordinals != list(range(1, len(existing) + 1)):
        raise ValueError("operator card receipt sequence broken")
    if len({x.get("operator_request_id") for x in existing}) != len(existing):
        raise ValueError("duplicate operator request identities")
    if len({tuple(_six(x["numbers"])) for x in existing}) != len(existing):
        raise ValueError("operator card receipt repeated combinations")
    for row in existing:
        if row["operator_request_id"] == request_id:
            return {**row, "idempotent_replay": True}

    if not existing:
        numbers = first_card
        selection = {"rule": "FROZEN_CHAMPION_PRIMARY_SIX", "source_primary_card_sha256": primary_hash}
    else:
        scores = freeze.get("champion", {}).get("aggregate_scores")
        if not isinstance(scores, dict):
            raise ValueError("frozen champion scores unavailable")
        selection_audit = select_primary_card(scores, excluded_cards=[row["numbers"] for row in existing])
        numbers = _six(selection_audit["selected_numbers"])
        selection = {
            "rule": "NEXT_HIGHEST_QUALIFIED_CHAMPION_CARD_EXCLUDING_ISSUED",
            "selector_sha256": selection_audit["sha256"],
            "excluded_prior_request_count": len(existing),
        }
    if any(numbers == _six(row["numbers"]) for row in existing):
        raise ValueError("model yielded a previously issued card")
    index = len(existing) + 1
    receipt = {
        "schema": SCHEMA,
        "status": "ISSUED_FOR_EXPLICIT_OPERATOR_REQUEST",
        "target_contest": target,
        "cutoff_contest": target - 1,
        "operator_request_id": request_id,
        "request_ordinal": index,
        "cards_issued_for_this_request": 1,
        "no_fixed_per_contest_card_limit": True,
        "numbers": numbers,
        "frozen_primary_reference": str(primary_file.relative_to(root)).replace("\\", "/"),
        "frozen_primary_sha256": _file_sha(primary_file),
        "freeze_sha256": expected_freeze_sha,
        "source_head": "champion",
        "selection": selection,
        "result_used": False,
        "model_weights_changed": False,
        "explicit_operator_request": True,
        "issued_utc": datetime.now(timezone.utc).isoformat(),
    }
    receipt["sha256"] = _hash(receipt)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"CARD-{index:04d}-{request_id}.json"
    # The outer operator lock serializes concurrent requests. Atomic replace
    # protects against partial files; never overwrite an issued receipt.
    fd, tmp = tempfile.mkstemp(prefix="card-request-", suffix=".tmp", dir=output_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        if destination.exists():
            raise FileExistsError("operator card request already issued")
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return receipt
