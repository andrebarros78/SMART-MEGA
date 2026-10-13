"""Read-only result reconciliation for cards explicitly requested by the operator.

Never reconstruct a missing historical card, refit weights, or promote models.
A receipt's timestamps and hashes alone do not qualify prospective evidence:
an independently timestamped pre-draw Git publication is separately required.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import json

from smart_operator_card_requests import _path, _six, _verified_receipt

SCHEMA = "SMART_OPERATOR_REQUESTED_CARD_OUTCOMES_1"


def _utc(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must have an aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} timestamp malformed") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{label} timestamp lacks timezone")
    return parsed


def reconcile_operator_card_outcomes(root, target, freeze_sha, official_numbers,
                                     adjudicated_utc):
    """Score every persisted request against the official result, without writes.

    None means no operator-issued card receipts exist (legacy single freeze
    remains authoritative). Never invent card requests or infer missing ones.
    """
    if type(target) is not int or target <= 0:
        raise ValueError("invalid target contest")
    if (not isinstance(freeze_sha, str) or len(freeze_sha) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in freeze_sha)):
        raise ValueError("invalid immutable freeze SHA-256")
    actual = set(_six(official_numbers))
    root = Path(root).resolve()
    directory = _path(root, f"runtime/operator_card_requests/{target}")
    if not directory.exists():
        return None
    adjudicated_time = _utc(adjudicated_utc, "adjudication")
    if not directory.is_dir():
        raise ValueError("operator request archive is not a directory")
    files = sorted(directory.glob("CARD-*.json"))
    if not files:
        raise ValueError("operator request archive exists but no card receipts were found")
    rows = []
    requests = set()
    cards = set()
    for ordinal, file in enumerate(files, 1):
        receipt = _verified_receipt(file, target, freeze_sha)
        requested = receipt.get("operator_request_id")
        if (type(receipt.get("request_ordinal")) is not int
                or receipt["request_ordinal"] != ordinal
                or file.name != f"CARD-{ordinal:04d}-{requested}.json"
                or not isinstance(requested, str) or requested in requests):
            raise ValueError("operator request identity or sequence invalid")
        requests.add(requested)
        if (receipt.get("status") != "ISSUED_FOR_EXPLICIT_OPERATOR_REQUEST"
                or receipt.get("explicit_operator_request") is not True
                or receipt.get("cards_issued_for_this_request") != 1
                or receipt.get("result_used") is not False
                or receipt.get("model_weights_changed") is not False
                or receipt.get("source_head") != "champion"):
            raise ValueError("operator request authority or anti-leakage invalid")
        if _utc(receipt.get("issued_utc"), "card issue") >= adjudicated_time:
            raise ValueError("operator card receipt was not issued before adjudication")
        card = tuple(_six(receipt["numbers"]))
        if card in cards:
            raise ValueError("operator request duplicate combination")
        cards.add(card)
        source = _path(root, receipt.get("frozen_primary_reference"))
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != receipt.get("frozen_primary_sha256"):
            raise ValueError("operator request lost original primary-card binding")
        original = json.loads(source.read_text(encoding="utf-8-sig"))
        if (original.get("freeze_sha256") != freeze_sha or original.get("target_contest") != target
                or original.get("product_role") != "FINAL_SINGLE_CARD_PRODUCT"):
            raise ValueError("operator-requested card bound to wrong frozen prediction")
        if ordinal == 1 and card != tuple(_six(original.get("numbers"))):
            raise ValueError("first requested card does not match frozen original")
        matched = sorted(set(card) & actual)
        rows.append({
            "operator_request_id": requested,
            "request_ordinal": ordinal,
            "numbers": list(card),
            "receipt_sha256": receipt["sha256"],
            "hits": len(matched),
            "matched_numbers": matched,
            "false_positive_numbers": sorted(set(card) - actual),
            "false_negative_numbers": sorted(actual - set(card)),
        })
    return {
        "schema": SCHEMA,
        "status": "POST_RESULT_DIAGNOSTIC_RECONCILED",
        "target_contest": target,
        "freeze_sha256": freeze_sha,
        "operator_requested_card_count": len(rows),
        "all_cards_have_six_distinct_numbers": True,
        "results": rows,
        "mean_hits_per_requested_card": sum(x["hits"] for x in rows) / len(rows),
        "uniform_expected_hits_per_six_number_card": 0.6,
        "feedback_available_for_future_oos_evaluation": True,
        "model_weight_change_authorized": False,
        "retrospective_card_reconstruction_performed": False,
        "prospective_publication_independently_verified": False,
        "prospective_superiority_proven": False,
    }
