"""Fail-closed video frame provenance audit; no model, predictions or web calls.

An Ed25519 witness binds a frame's byte digest to a claim about observation
time. A signed claim does NOT establish an independent timestamp, licensed
media access or a proven video-derived predictor. No production trust anchors
are distributed; trusted issuer keys must be supplied from independent,
operator-governed authority.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "SMART_VIDEO_PIT_FRAME_WITNESS_V1"
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
ID_RE = re.compile(r"[1-9][0-9]{0,11}\Z")
VIDEO_RE = re.compile(r"[A-Za-z0-9_-]{11}\Z")
SIGNER_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{3,63}\Z")
MAX_FRAME_BYTES = 50 * 1024 * 1024
ALLOWED_WITNESS_FIELDS = {
    "schema", "issuer_id", "target_contest", "source_contest",
    "observed_utc", "frame_sha256", "frame_basename", "frame_size_bytes",
    "media_sha256", "video_id", "source_authority", "synthetic",
    "checkpoint_sha256", "signature_b64",
}
FORBIDDEN_FIELDS = {
    "winning_numbers", "drawn_numbers", "draw_result", "official_result",
    "result_numbers", "dezenas_sorteadas", "prize_distribution",
    "numero_sorteado", "prediction_gain", "predictive_weight",
}


def _canonical(doc: Mapping[str, Any]) -> bytes:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _parse_utc(stamp: Any) -> datetime:
    if not isinstance(stamp, str) or len(stamp) > 45:
        raise ValueError("invalid timestamp")
    value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive timestamp")
    return value.astimezone(timezone.utc)


def audit_pit_frame_witness(
    frame_file: str | Path,
    witness: Mapping[str, Any],
    trusted_issuers: Mapping[str, Mapping[str, str]],
    *,
    target_contest: str,
    cutoff_utc: str,
    checkpoint_sha256: str,
) -> dict[str, Any]:
    """Verify content + claimed time separately; never grant predictive status.

    A caller-supplied issuer key is a trust *input* and not a validated
    authority chain. Even a matching signature cannot prove the witness's
    real-time clock, authentic video decoding, or authorized source use.
    """
    if not isinstance(target_contest, str) or not ID_RE.fullmatch(target_contest):
        raise ValueError("INVALID_TARGET_CONTEST")
    cutoff = _parse_utc(cutoff_utc)
    result: dict[str, Any] = {
        "schema": "SMART_VIDEO_PIT_FRAME_AUDIT_V1",
        "status": "FRAME_UNAVAILABLE",
        "target_contest": target_contest,
        "cutoff_utc": cutoff.isoformat(),
        "frame_hash_verified": False,
        "witness_signature_verified": False,
        "independent_historical_timestamp_verified": False,
        "media_source_authorized": False,
        "video_frames_independently_decoded": None,
        "pit_independently_attested": False,
        "contribution_to_predictions": None,
        "predictive_weight": 0.0,
    }
    path = Path(frame_file)
    if any(part.upper().startswith("SYNTHETIC_ONLY") for part in
           str(path).replace("\\", "/").split("/")):
        result["status"] = "SYNTHETIC_SOURCE_QUARANTINED"
        return result
    if path.is_symlink() or not path.is_file():
        return result
    if not isinstance(witness, Mapping) or not isinstance(trusted_issuers, Mapping):
        result["status"] = "WITNESS_NOT_TRUSTED"
        return result
    def contains_result_labels(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(str(k).lower() in FORBIDDEN_FIELDS
                       or contains_result_labels(v) for k, v in value.items())
        if isinstance(value, (tuple, list)):
            return any(contains_result_labels(v) for v in value)
        return False
    if contains_result_labels(witness):
        result["status"] = "RESULT_CONTAMINATION_REJECTED"
        return result
    if set(witness) != ALLOWED_WITNESS_FIELDS:
        result["status"] = "WITNESS_SCHEMA_REJECTED"
        return result
    if (not isinstance(checkpoint_sha256, str)
            or not SHA_RE.fullmatch(checkpoint_sha256)
            or witness.get("checkpoint_sha256") != checkpoint_sha256):
        result["status"] = "CHECKPOINT_BINDING_MISMATCH"
        return result
    if witness.get("schema") != SCHEMA or witness.get("source_authority") != "UNVERIFIED" or witness.get("synthetic") is not False:
        result["status"] = "SOURCE_AUTHORITY_UNPROVEN"
        return result
    source_id = witness.get("source_contest")
    if (not isinstance(source_id, str) or not ID_RE.fullmatch(source_id)
            or int(source_id) >= int(target_contest)
            or witness.get("target_contest") != target_contest):
        result["status"] = "FUTURE_OR_TARGET_CONTEST"
        return result
    if (not isinstance(witness.get("media_sha256"), str)
            or not SHA_RE.fullmatch(witness["media_sha256"])
            or not isinstance(witness.get("frame_sha256"), str)
            or not SHA_RE.fullmatch(witness["frame_sha256"])
            or not isinstance(witness.get("video_id"), str)
            or not VIDEO_RE.fullmatch(witness["video_id"])
            or witness.get("frame_basename") != path.name):
        result["status"] = "SOURCE_AUTHORITY_UNPROVEN"
        return result
    try:
        observed = _parse_utc(witness.get("observed_utc"))
    except (ValueError, TypeError, OverflowError):
        result["status"] = "UNTRUSTED_TIME_FORMAT"
        return result
    if observed > cutoff or observed > datetime.now(timezone.utc):
        result["status"] = "WITNESS_AFTER_CUTOFF"
        return result
    issuer = witness.get("issuer_id")
    anchor = trusted_issuers.get(issuer) if isinstance(issuer, str) and SIGNER_RE.fullmatch(issuer) else None
    if (not isinstance(anchor, Mapping)
            or anchor.get("role") != "INDEPENDENT_TIMESTAMP_WITNESS"
            or anchor.get("source") != "OPERATOR_PINNED_TRUST_ANCHOR"
            or anchor.get("revoked") is True):
        result["status"] = "WITNESS_NOT_TRUSTED"
        return result
    try:
        public_key = bytes.fromhex(anchor["ed25519_public_key_hex"])
        if len(public_key) != 32:
            raise ValueError("invalid key size")
        signature = base64.b64decode(witness["signature_b64"], validate=True)
        if len(signature) != 64:
            raise ValueError("invalid signature size")
        unsigned = {k: v for k, v in witness.items() if k != "signature_b64"}
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, _canonical(unsigned)
        )
    except (InvalidSignature, ValueError, TypeError, KeyError, binascii.Error,
            UnicodeEncodeError, OverflowError):
        result["status"] = "WITNESS_SIGNATURE_INVALID"
        return result
    result["witness_signature_verified"] = True
    try:
        size = path.stat().st_size
        if size < 1 or size > MAX_FRAME_BYTES or witness.get("frame_size_bytes") != size:
            result["status"] = "FRAME_CONTENT_MISMATCH"
            return result
        with path.open("rb") as fd:
            digest = hashlib.sha256(fd.read(MAX_FRAME_BYTES + 1)).hexdigest()
    except OSError:
        result["status"] = "FRAME_UNAVAILABLE"
        return result
    if digest != witness["frame_sha256"]:
        result["status"] = "FRAME_CONTENT_MISMATCH"
        return result
    result["frame_hash_verified"] = True
    result["frame_sha256"] = digest
    result["witness_issuer_id"] = issuer
    result["witness_observed_utc"] = observed.isoformat()
    result["status"] = "SIGNED_FRAME_WITNESS_ONLY"
    return result


def audit_pit_frame_batch(
    evidence_dir: str | Path,
    checkpoint_hashes: Mapping[str, str],
    eligible_contests: list[int],
    trusted_issuers: Mapping[str, Mapping[str, str]],
    *,
    target_contest: str,
    cutoff_utc: str,
) -> dict[str, Any]:
    """Audit a single fixed-name frame witness per earlier eligible contest.

    Individual signed frame byte commitments can be useful for provenance
    hygiene, but the whole batch is *never* an independent historical PIT
    certificate without external timestamp authority receipts. No source
    download, writes, model execution or weights.
    """
    root = Path(evidence_dir)
    summary: dict[str, Any] = {
        "schema": "SMART_VIDEO_PIT_FRAME_BATCH_AUDIT_V1",
        "status": "EVIDENCE_DIR_UNAVAILABLE",
        "eligible_episodes": len(eligible_contests),
        "signed_frame_bindings": 0,
        "invalid_frame_bindings": 0,
        "missing_frame_bindings": 0,
        "independently_timestamped": 0,
        "pit_independently_attested": False,
        "predictive_weight": 0.0,
        "results": [],
    }
    if root.is_symlink() or not root.is_dir():
        return summary
    for cid in eligible_contests:
        key = str(cid)
        result = {"source_contest": key, "status": "MISSING"}
        witness_path = root / f"contest_{cid}_pit_witness.json"
        frame_path = root / f"contest_{cid}_frame.png"
        if witness_path.is_symlink() or frame_path.is_symlink():
            result["status"] = "SYMLINK_REJECTED"
        elif (witness_path.is_file() and frame_path.is_file()
                and 2 <= witness_path.stat().st_size <= 16384):
            try:
                receipt = json.loads(witness_path.read_bytes())
                verified = audit_pit_frame_witness(
                    frame_path, receipt, trusted_issuers,
                    target_contest=target_contest, cutoff_utc=cutoff_utc,
                    checkpoint_sha256=checkpoint_hashes[key],
                )
                result["status"] = verified["status"]
            except (ValueError, TypeError, OSError, KeyError, json.JSONDecodeError):
                result["status"] = "WITNESS_INVALID"
        if result["status"] == "SIGNED_FRAME_WITNESS_ONLY":
            summary["signed_frame_bindings"] += 1
        elif result["status"] == "MISSING":
            summary["missing_frame_bindings"] += 1
        else:
            summary["invalid_frame_bindings"] += 1
        summary["results"].append(result)
    summary["status"] = "CONTENT_WITNESS_ONLY_PIT_NOT_PROVEN"
    return summary
