"""Cutoff-bound, read-only retrieval evidence for a prospective SMART-MEGA freeze.

Never grants predictive weights or mutates freeze, state, or signal ledgers.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_rag_excel import build_preparation_proof

FILE_NAME = "SMART_RAG_EXCEL_PREPARATION_PROOF.json"
DENIED_AUTHORITIES = (
    "predictive_weight_authority",
    "freeze_mutation_authority",
    "signal_state_mutation_authority",
    "ledger_mutation_authority",
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare_rag_freeze_evidence(
    root: str | Path,
    data_file: str | Path,
    cutoff_contest: int,
    epoch_dir: str | Path,
    target_contest: int,
) -> dict[str, Any]:
    """Save only the verified retrieval receipt in the fresh epoch."""
    root, epoch_dir = Path(root).resolve(), Path(epoch_dir).resolve()
    target, cutoff = int(target_contest), int(cutoff_contest)
    if target != cutoff + 1:
        raise ValueError("RAG cutoff must be target contest minus one")
    if not epoch_dir.is_dir() or not epoch_dir.is_relative_to(root):
        raise ValueError("RAG epoch directory must already exist inside project")
    destination = epoch_dir / FILE_NAME
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("RAG preparation receipt is create-only")
    proof = build_preparation_proof(root, excel=data_file, as_of_contest=cutoff)
    manifest, checks = proof.get("manifest"), proof.get("checks")
    if not isinstance(manifest, dict) or not isinstance(checks, dict):
        raise ValueError("invalid RAG preparation evidence")
    if proof.get("status") != "PASS":
        raise ValueError("RAG preparation did not pass")
    if manifest.get("as_of_contest") != cutoff or manifest.get("temporal_cutoff_enforced") is not True:
        raise ValueError("RAG evidence violated historical cutoff")
    if any(manifest.get(key) is not False for key in DENIED_AUTHORITIES):
        raise ValueError("RAG evidence attempted predictive or mutation authority")
    if not all(checks.get(key) is True for key in (
        "critical_canonical_state_unchanged",
        "no_predictive_or_freeze_authority",
        "latest_allowed_contest_retrievable",
    )):
        raise ValueError("RAG preparation integrity failed")
    canonical = dict(proof)
    observed = canonical.pop("sha256", None)
    serialized = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if observed != _digest(serialized):
        raise ValueError("RAG preparation self-hash invalid")
    payload = (json.dumps(proof, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    destination.write_bytes(payload)
    return {
        "status": "PASS",
        "file": str(destination.relative_to(root)).replace("\\", "/"),
        "file_sha256": _digest(payload),
        "self_sha256": observed,
        "cutoff_contest": cutoff,
        "target_contest": target,
        "predictive_weight_authority": False,
        "freeze_mutation_authority": False,
        "result_used": False,
    }
