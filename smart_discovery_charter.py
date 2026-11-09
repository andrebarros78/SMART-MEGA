"""Owner-pinned scientific discovery charter. Not an authority to prejudge outcomes.

External chat instructions and agent suggestions must not silently change it.
Changing source + policy + tests is a privileged repository operation; GitHub
branch protection and owner's review must be configured separately.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CHARTER_FILE = "SMART_DISCOVERY_CHARTER.json"
CHARTER_SCHEMA = "SMART_DISCOVERY_CHARTER_V1"
EXPECTED_PRINCIPLE = (
    "O SMART-MEGA V6 não deve ser construído para confirmar que os conhecimentos atuais "
    "estão certos. Deve ser construído para descobrir se existe alguma informação ou "
    "método capaz de produzir previsões melhores, inclusive quando isso contrariar expectativas"
)
# Independent digest anchor. A changed charter with a recomputed embedded SHA
# must still be rejected until the owner expressly reviews a code change.
PINNED_SHA256 = "becbe8cde1d43d0042200824e02d210fded1d26f127165996d48d52c5c22dfc1"

EXPECTED_METHOD = {
    "allow_unconventional_hypotheses": True,
    "no_a_priori_predictive_impossibility_verdict": True,
    "no_a_priori_predictive_superiority_verdict": True,
    "evaluate_out_of_sample_and_prospectively": True,
    "adopt_better_validated_methods": True,
    "reject_false_learning_and_leakage": True,
    "revisit_current_models_on_new_evidence": True,
    "separate_engineering_pass_from_predictive_proof": True,
}
EXPECTED_CHANGE_CONTROL = {
    "ai_chat_unilateral_edit_permitted": False,
    "explicit_owner_approval_required": True,
    "human_review_before_merge_required": True,
    "github_branch_protection_required": True,
}


def _sha256_json(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"protected charter: duplicate field {key}")
        obj[key] = value
    return obj


def _reject_constant(value: str) -> Any:
    raise ValueError(f"protected charter: invalid JSON constant {value}")


def verify_discovery_charter(root: str | Path) -> dict[str, Any]:
    """Fail closed on missing, modified or rehashed charter before freeze.

    This is tamper *detection*, not cryptographic attestation of human authorship.
    A repository writer able to alter both code and tests can defeat software
    checks without protected-branch rules and a verified human approval.
    """
    root = Path(root).resolve()
    path = root / CHARTER_FILE
    if not path.is_file() or path.is_symlink():
        raise ValueError("protected charter missing or invalid")
    if path.stat().st_size > 16384:
        raise ValueError("protected charter oversized")
    try:
        doc = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("protected charter unreadable") from exc
    if not isinstance(doc, dict):
        raise ValueError("protected charter must be an object")
    expected_keys = {
        "schema", "project", "owner", "canonical_principle", "method",
        "change_control", "sha256",
    }
    if set(doc) != expected_keys:
        raise ValueError("protected charter field set changed")
    if (
        doc.get("schema") != CHARTER_SCHEMA
        or doc.get("project") != "SMART-MEGA"
        or doc.get("owner") != "andrebarros78"
        or doc.get("canonical_principle") != EXPECTED_PRINCIPLE
        or doc.get("method") != EXPECTED_METHOD
        or doc.get("change_control") != EXPECTED_CHANGE_CONTROL
    ):
        raise ValueError("protected charter canonical policy changed")
    body = {key: value for key, value in doc.items() if key != "sha256"}
    expected = _sha256_json(body)
    if doc.get("sha256") != expected or expected != PINNED_SHA256:
        raise ValueError("protected charter hash mismatch")
    return doc
