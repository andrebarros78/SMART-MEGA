from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from smart_ai_fine_tuning import (
    load_authority,
    run_fine_tuning,
    sha256_file,
    sha256_json,
    write_report_and_authority,
)

REPORT_NAME = "SMART_AI_FINE_TUNING_CURRENT.json"
AUTHORITY_NAME = "SMART_AI_HYPERPARAMETERS.json"


def _load_report(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("fine-tuning report must be a JSON object")
    canonical = dict(obj)
    observed = canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed != sha256_json(canonical):
        raise ValueError("fine-tuning report self-hash invalid")
    return obj


def _validate_pair(
    data_file: Path,
    target_contest: int,
    report_path: Path,
    authority_path: Path,
) -> dict[str, Any]:
    data_file = Path(data_file).resolve()
    report = _load_report(report_path)
    data_sha = sha256_file(data_file)
    target = int(target_contest)
    cutoff = target - 1
    if int(report.get("target_contest", -1)) != target:
        raise ValueError("fine-tuning report target mismatch")
    if int(report.get("cutoff_contest", -1)) != cutoff:
        raise ValueError("fine-tuning report cutoff mismatch")
    if report.get("data_sha256") != data_sha:
        raise ValueError("fine-tuning report data mismatch")
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    if guardrails.get("future_result_used") is not False:
        raise ValueError("fine-tuning report used future result")
    if guardrails.get("holdout_used_for_selection") is not False:
        raise ValueError("fine-tuning holdout was used for selection")
    if report.get("selection", {}).get("holdout_used_for_selection") is not False:
        raise ValueError("fine-tuning selection used holdout")

    authority = load_authority(authority_path, target_contest=target, data_sha256=data_sha)
    if authority is None:
        raise FileNotFoundError(authority_path)
    if authority.get("fine_tuning_report_sha256") != report.get("sha256"):
        raise ValueError("fine-tuning authority/report semantic hash mismatch")
    if authority.get("fine_tuning_report_file_sha256") != sha256_file(report_path):
        raise ValueError("fine-tuning authority/report file hash mismatch")
    if authority.get("causal_partitioning") is not True:
        raise ValueError("fine-tuning authority lacks causal partitioning")
    if authority.get("future_result_used") is not False or authority.get("holdout_used_for_selection") is not False:
        raise ValueError("fine-tuning authority violates causal guardrails")

    adjudication = report.get("adjudication") if isinstance(report.get("adjudication"), dict) else {}
    return {
        "status": str(authority.get("status")),
        "target_contest": target,
        "cutoff_contest": cutoff,
        "data_sha256": data_sha,
        "promotion_authorized": bool(authority.get("promotion_authorized")),
        "effective_candidate_id": str(adjudication.get("effective_candidate_id") or "baseline"),
        "report_file": str(report_path.resolve()),
        "report_file_sha256": sha256_file(report_path),
        "report_sha256": str(report.get("sha256")),
        "authority_file": str(authority_path.resolve()),
        "authority_file_sha256": sha256_file(authority_path),
        "authority_sha256": str(authority.get("sha256")),
        "holdout_used_for_selection": False,
        "future_result_used": False,
    }


def ensure_pre_freeze_authority(
    data_file: str | Path,
    target_contest: int,
    epoch_dir: str | Path,
    *,
    start: int = 1000,
    max_workers: int = 4,
) -> dict[str, Any]:
    data_file = Path(data_file).resolve()
    epoch_dir = Path(epoch_dir).resolve()
    if not data_file.is_file():
        raise FileNotFoundError(data_file)
    epoch_dir.mkdir(parents=True, exist_ok=True)
    report_path = epoch_dir / REPORT_NAME
    authority_path = epoch_dir / AUTHORITY_NAME
    if report_path.exists() != authority_path.exists():
        raise RuntimeError("partial fine-tuning authority artifacts are forbidden")
    if report_path.exists():
        result = _validate_pair(data_file, int(target_contest), report_path, authority_path)
        return {**result, "reused_existing_authority": True}

    progress_path = epoch_dir / "SMART_AI_FINE_TUNING_PROGRESS.json"

    def progress(state: dict[str, Any]) -> None:
        # Progress never grants authority; only a complete, hash-bound report does.
        payload = {
            **state, "target_contest": int(target_contest),
            "cutoff_contest": int(target_contest) - 1,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=epoch_dir,
            prefix=".fine-tuning-progress-", suffix=".tmp", delete=False,
        ) as handle:
            tmp = Path(handle.name)
            try:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        os.replace(tmp, progress_path)
        print(
            f"FINE_TUNING_PROGRESS target={target_contest} "
            f"status={state['status']} completed={state['completed']}/{state['total']}",
            file=sys.stderr, flush=True,
        )

    report = run_fine_tuning(
        data_file,
        int(target_contest),
        start=int(start),
        max_workers=int(max_workers),
        progress=progress,
    )
    try:
        write_report_and_authority(report, report_path=report_path, authority_path=authority_path)
        result = _validate_pair(data_file, int(target_contest), report_path, authority_path)
    except BaseException:
        progress({"status": "FAILED", "completed": 0, "total": 0,
                  "candidate_ids": [], "elapsed_seconds": 0.0})
        raise
    progress({"status": "COMPLETE", "completed": int(report["candidate_count"]),
              "total": int(report["candidate_count"]),
              "candidate_ids": [item["candidate"]["candidate_id"] for item in report["results"]],
              "elapsed_seconds": 0.0,
              "report_file_sha256": result["report_file_sha256"],
              "authority_file_sha256": result["authority_file_sha256"]})
    return {**result, "reused_existing_authority": False}
