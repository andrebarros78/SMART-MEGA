"""Read and verify the *existing* frozen predictive card without adjudication.

No new prediction, random fallback, weights mutation or post-draw re-freeze.
Only stdlib is required. Supports inspection even after the draw date.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "SMART_FROZEN_MODEL_CARD_READ_1"


def file_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(data)
    return sha.hexdigest()


def sha256_json(document: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _self_hashed(obj: Any, label: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"{label} document invalid")
    observed = obj.get("sha256")
    if not isinstance(observed, str) or observed != sha256_json({k: v for k, v in obj.items() if k != "sha256"}):
        raise ValueError(f"{label} self-hash mismatch")
    return obj


def _safe_file(root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f"{label} path invalid")
    parts = Path(relative).parts
    if ".." in parts or "." in parts:
        raise ValueError(f"{label} path traverses parent")
    p = root
    for part in parts:
        p = p / part
        if p.is_symlink():
            raise ValueError(f"{label} symbolic link is forbidden")
    if not p.resolve().is_relative_to(root):
        raise ValueError(f"{label} path escapes canonical root")
    if not p.is_file():
        raise ValueError(f"{label} evidence file missing")
    return p


def _immutable_archive(root: Path, target: int) -> dict[str, Any]:
    """Resolve one independently hash-bound epoch; never reconstruct a past card."""
    base = root / "SMART_STATE_ARCHIVE" / "adjudicated-epochs" / str(target)
    candidates = sorted(base.glob("*/ARCHIVE_MANIFEST.json")) if base.is_dir() else []
    if len(candidates) != 1:
        raise ValueError("unique immutable archive not found for requested frozen contest")
    manifest_path = _safe_file(root, candidates[0].relative_to(root).as_posix(), "archive manifest")
    manifest = _self_hashed(_read(manifest_path), "archive manifest")
    if (manifest.get("schema") != "SMART_ADJUDICATED_EPOCH_ARCHIVE_1"
            or manifest.get("status") != "ARCHIVED_IMMUTABLE"
            or manifest.get("target_contest") != target
            or manifest.get("byte_for_byte_verified") is not True
            or manifest.get("immutability_policy") != "CONTENT_ADDRESSED_READ_ONLY_ARCHIVE"):
        raise ValueError("archive manifest authority invalid")
    files = manifest.get("source_files")
    if (not isinstance(files, dict) or not files
            or manifest.get("file_count") != len(files)):
        raise ValueError("archive manifest source inventory invalid")
    epoch_id = manifest.get("epoch_id")
    if (not isinstance(epoch_id, str) or not epoch_id
            or "/" in epoch_id or "\\" in epoch_id
            or epoch_id in {".", ".."} or manifest_path.parent.name != epoch_id):
        raise ValueError("archive manifest epoch identity invalid")
    pointer_relative = (manifest_path.parent.relative_to(root) / "SMART_ACTIVE_EPOCH.json").as_posix()
    pointer_path = _safe_file(root, pointer_relative, "archive active pointer")
    if file_sha256(pointer_path) != manifest.get("source_active_pointer_sha256"):
        raise ValueError("archive active pointer SHA-256 mismatch")
    active = _self_hashed(_read(pointer_path), "active")
    if active.get("target_contest") != target or active.get("epoch_id") != epoch_id:
        raise ValueError("archive pointer target/epoch mismatch")
    return {"manifest": manifest, "directory": manifest_path.parent, "active": active}


def _archived_file(root: Path, original: Any, label: str, archive: dict[str, Any]) -> Path:
    if not isinstance(original, str) or not original:
        raise ValueError(f"{label} archive source path invalid")
    declared = Path(original)
    if declared.is_absolute() or any(part in {".", ".."} for part in declared.parts):
        raise ValueError(f"{label} archive source traversal")
    prefix = Path("runtime") / "learning_epochs" / archive["manifest"]["epoch_id"]
    if not declared.is_relative_to(prefix):
        raise ValueError(f"{label} archive source epoch mismatch")
    name = declared.relative_to(prefix)
    if not name.parts:
        raise ValueError(f"{label} archive source basename missing")
    expected = archive["manifest"]["source_files"].get(name.as_posix())
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f"{label} archive evidence not declared")
    archived_relative = (archive["directory"].relative_to(root) / "epoch" / name).as_posix()
    physical = _safe_file(root, archived_relative, label)
    if file_sha256(physical) != expected:
        raise ValueError(f"{label} archive artifact SHA-256 mismatch")
    return physical


def _read(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError("frozen card evidence JSON is not an object")
    return obj


def _six(values: Any) -> bool:
    return (isinstance(values, list) and len(values) == 6
            and all(type(n) is int and 1 <= n <= 60 for n in values)
            and len(set(values)) == 6 and values == sorted(values))


def verify_result(doc: dict[str, Any]) -> bool:
    return (isinstance(doc, dict)
            and doc.get("schema") == SCHEMA
            and doc.get("status") == "FROZEN_MODEL_CARD_VERIFIED"
            and doc.get("readonly") is True
            and doc.get("result_used_in_generation") is False
            and doc.get("certified_predictive_advantage") is False
            and doc.get("past_draw_can_be_reused_as_future_prediction") is False
            and _six(doc.get("numbers"))
            and doc.get("sha256") == sha256_json({k: v for k, v in doc.items() if k != "sha256"}))


def read_frozen_card(root: str | Path, target: int) -> dict[str, Any]:
    """Return an already-frozen model card, tied to existing immutable evidence.

    Deliberately never builds a new target card from an older cutoff or calls
    the model; never requires completion of the old adjudication.
    """
    if type(target) is not int or target < 1:
        raise ValueError("target must be a positive integer")
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError("canonical project root missing")
    archive = None
    if (root / "SMART_ACTIVE_EPOCH.json").is_file():
        active = _self_hashed(_read(_safe_file(root, "SMART_ACTIVE_EPOCH.json", "active")), "active")
    else:
        archive = _immutable_archive(root, target)
        active = archive["active"]
    if active.get("status") != "FROZEN" or active.get("target_contest") != target:
        raise ValueError("requested contest is not frozen in active model epoch")
    cutoff = target - 1
    if active.get("cutoff_contest") != cutoff:
        raise ValueError("active cutoff mismatch")
    authority = active.get("freeze_authority")
    if not isinstance(authority, dict) or authority.get("target_contest") != target or authority.get("cutoff_contest") != cutoff:
        raise ValueError("freeze authority target mismatch")
    freeze_file = (_archived_file(root, authority.get("file"), "freeze", archive)
                   if archive is not None else _safe_file(root, authority.get("file"), "freeze"))
    freeze_sha = file_sha256(freeze_file)
    if freeze_sha != authority.get("sha256"):
        raise ValueError("freeze SHA-256 mismatch")
    freeze = _read(freeze_file)
    if not (freeze.get("target_contest") == target
            and freeze.get("cutoff_contest") == cutoff
            and freeze.get("frozen_before_result") is True
            and freeze.get("causal_cutoff") is True
            and freeze.get("data_sha256") == active.get("data_sha256")):
        raise ValueError("freeze causal evidence mismatch")
    original_freeze = Path(str(authority.get("file")))
    original_proof = (original_freeze.parent / "FULL_PROCESS_PROOF.json").as_posix()
    proof_file = (_archived_file(root, original_proof, "proof", archive)
                  if archive is not None else _safe_file(root, original_proof, "proof"))
    proof = _self_hashed(_read(proof_file), "proof")
    if (proof.get("status") != "PASS" or proof.get("target_contest") != target
            or proof.get("cutoff_contest") != cutoff
            or proof.get("result_used") is not False
            or proof.get("freeze_sha256") != freeze_sha
            or proof.get("freeze_file") != original_freeze.as_posix()
            or proof.get("data_sha256") != freeze["data_sha256"]):
        raise ValueError("proof target or frozen-source mismatch")
    card_file = (_archived_file(root, proof.get("primary_card_file"), "card", archive)
                 if archive is not None else _safe_file(root, proof.get("primary_card_file"), "card"))
    card_sha = file_sha256(card_file)
    if card_sha != proof.get("primary_card_sha256"):
        raise ValueError("card SHA-256 mismatch")
    card = _self_hashed(_read(card_file), "card")
    portfolio_file = (_archived_file(root, proof.get("portfolio_file"), "portfolio", archive)
                      if archive is not None else _safe_file(root, proof.get("portfolio_file"), "portfolio"))
    portfolio_sha = file_sha256(portfolio_file)
    if portfolio_sha != proof.get("portfolio_sha256") or portfolio_sha != card.get("portfolio_sha256"):
        raise ValueError("portfolio SHA-256 mismatch")
    portfolio = _read(portfolio_file)
    if (portfolio.get("status") != "PASS"
            or portfolio.get("target_contest") != target
            or portfolio.get("cutoff_contest") != cutoff
            or portfolio.get("freeze_sha256") != freeze_sha
            or portfolio.get("source_data_sha256") != freeze["data_sha256"]):
        raise ValueError("portfolio target/freeze mismatch")
    numbers = card.get("numbers")
    selector = card.get("selector")
    embedded = proof.get("primary_card")
    original = portfolio.get("primary_card")
    if (not _six(numbers)
            or card.get("schema") != "SMART_PRIMARY_SINGLE_CARD_2"
            or card.get("status") != "FROZEN"
            or card.get("product_role") != "FINAL_SINGLE_CARD_PRODUCT"
            or card.get("result_used") is not False
            or card.get("target_contest") != target
            or card.get("cutoff_contest") != cutoff
            or card.get("freeze_sha256") != freeze_sha
            or card.get("freeze_file") != proof.get("freeze_file")
            or card.get("portfolio_file") != proof.get("portfolio_file")
            or not isinstance(embedded, dict)
            or not isinstance(original, dict)
            or embedded.get("numbers") != numbers
            or original.get("numbers") != numbers
            or not isinstance(selector, dict)
            or selector.get("selected_numbers") != numbers
            or selector.get("result_used") is not False
            or selector.get("status") != "PASS"
            or selector != embedded.get("selector")
            or selector != original.get("selector")):
        raise ValueError("frozen model card selector/consumer mismatch")
    confidence = card.get("confidence")
    if not isinstance(confidence, dict) or confidence.get("status") != "UNPROVEN_PROSPECTIVE" or confidence.get("guaranteed") is not False:
        raise ValueError("card calibration provenance invalid")
    result = {
        "schema": SCHEMA,
        "status": "FROZEN_MODEL_CARD_VERIFIED",
        "target_contest": target,
        "cutoff_contest": cutoff,
        "numbers": numbers,
        "generated_utc": card.get("generated_utc"),
        "source_kind": "EXISTING_FROZEN_SMART_MEGA_MODEL",
        "freeze_sha256": freeze_sha,
        "primary_card_sha256": card_sha,
        "portfolio_sha256": portfolio_sha,
        "full_process_proof_sha256": file_sha256(proof_file),
        "historical_data_sha256": freeze.get("data_sha256"),
        "readonly": True,
        "result_used_in_generation": False,
        "certified_predictive_advantage": False,
        "past_draw_can_be_reused_as_future_prediction": False,
        "scientific_status": proof.get("scientific_claim_status"),
        "no_adjudication_required_to_read": True,
    }
    result["sha256"] = sha256_json(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Read an existing frozen SMART-MEGA model card without dependencies.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--target", required=True, type=int)
    args = parser.parse_args()
    print(json.dumps(read_frozen_card(Path(args.root), args.target), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
