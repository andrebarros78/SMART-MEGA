"""SMART-MEGA visual learning V2: auditable observation memory, not lottery prediction.

Read-only ingestion of previous contest checkpoints. No network, media persistence,
lottery-result access, model promotion, or predictive-weight updates.
Run: python -m research.visual_learning_v2 --checkpoint-dir PATH --store PATH --next-contest N
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from smart_video_observation import (
    EXTRACTOR_VERSION,
    PREDICTIVE_EVIDENCE,
    VALID_STATUSES,
    ObservationConfig,
    _observation_fingerprint,
    _is_youtube_source,
)

SCHEMA = "SMART_VISUAL_LEARNING_V2"
FORBIDDEN_KEYS = frozenset({
    "winning_numbers", "drawn_numbers", "result_numbers",
    "dezenas_sorteadas", "hit_count", "official_result",
    "sorteadas", "numero_sorteado", "actual_winners",
})
MAX_CHECKPOINT_BYTES = 1024 * 1024
MAX_CHECKPOINTS = 512


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _forbidden_recursive(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            str(k).lower() in FORBIDDEN_KEYS or _forbidden_recursive(v)
            for k, v in value.items()
        )
    if isinstance(value, list):
        return any(_forbidden_recursive(v) for v in value)
    return False


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".visual-v2-", delete=False) as f:
            temp = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _read_row(path: Path, target: int, hypothesis_id: str | None) -> tuple[dict | None, str | None]:
    match = re.fullmatch(r"contest_([0-9]+)\.json", path.name)
    if not match:
        return None, "INVALID_FILENAME"
    contest = int(match.group(1))
    if contest >= target:
        return None, "FUTURE_OR_SAME_CONTEST"
    if path.is_symlink() or not path.is_file():
        return None, "NOT_REGULAR_FILE"
    if path.stat().st_size > MAX_CHECKPOINT_BYTES:
        return None, "OVERSIZED"
    raw = path.read_bytes()
    try:
        row = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, "MALFORMED"
    if not isinstance(row, dict):
        return None, "MALFORMED"
    if _forbidden_recursive(row):
        return None, "RESULT_LABEL_LEAKAGE"
    if str(row.get("contest_id")) != str(contest):
        return None, "CONTEST_ID_MISMATCH"
    if row.get("extractor_version") != EXTRACTOR_VERSION:
        return None, "LEGACY_VERSION_UNVERIFIED"
    if row.get("hypothesis_id") != hypothesis_id:
        return None, "HYPOTHESIS_MISMATCH"
    if row.get("predictive_evidence") != PREDICTIVE_EVIDENCE:
        return None, "PREDICTIVE_CLAIM_DISALLOWED"
    if row.get("status") not in VALID_STATUSES:
        return None, "INVALID_STATUS"
    source = row.get("source")
    params = row.get("main_params")
    if not isinstance(source, str) or not isinstance(params, dict):
        return None, "MISSING_PROVENANCE"
    url = urlparse(source)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        return None, "INVALID_SOURCE"
    try:
        cfg = ObservationConfig(**params).validated()
    except (TypeError, ValueError):
        return None, "INVALID_PARAMS"
    if row.get("checkpoint_fingerprint") != _observation_fingerprint(
        str(contest), source, cfg, hypothesis_id
    ):
        return None, "FINGERPRINT_MISMATCH"
    status = str(row["status"])
    if status == "CANDIDATE":
        scope = row.get("analysis_scope") or {}
        if not isinstance(scope, dict) or not isinstance(row.get("spatial_consensus"), dict):
            return None, "CANDIDATE_UNVERIFIED"
        try:
            lo, hi = float(scope["start_s"]), float(scope["end_s"])
            times = [float(t) for t in row["event_timestamps_s"]]
        except (ValueError, TypeError, KeyError):
            return None, "CANDIDATE_MISSING_EVENTS"
        if (
            not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo
            or len(times) < cfg.min_candidate_events
            or not all(math.isfinite(t) and lo <= t <= hi for t in times)
            or row.get("spatial_consensus", {}).get("recurrent") is not True
            or (_is_youtube_source(source) and scope.get("segment_guard_passed") is not True)
        ):
            return None, "CANDIDATE_UNVERIFIED"
    coverage = row.get("analysis_scope_coverage_ratio", row.get("coverage_ratio"))
    if coverage is not None:
        try:
            coverage = float(coverage)
        except (TypeError, ValueError):
            return None, "INVALID_COVERAGE"
        if not math.isfinite(coverage) or not 0 <= coverage <= 1:
            return None, "INVALID_COVERAGE"
    limitations = row.get("limitations")
    notes = [str(x).lower() for x in limitations if isinstance(x, str)] if isinstance(limitations, list) else []
    failure_modes: list[str] = []
    if status in {"STREAM_FAILED", "TIMEOUT", "UNOBSERVABLE"}:
        failure_modes.append("UNAVAILABLE_VISUAL_INPUT")
    if any("global motion/camera change" in x for x in notes):
        failure_modes.append("GLOBAL_CAMERA_MOTION")
    if any("stable across spatial grid resolutions" in x for x in notes):
        failure_modes.append("SPATIAL_GRID_DISAGREEMENT")
    if any("too few recurrent events" in x for x in notes):
        failure_modes.append("LOW_EVENT_COUNT")
    if any("segment locator" in x or "segment guard" in x for x in notes):
        failure_modes.append("SEGMENT_GUARD_UNPROVEN")
    return {
        "contest": contest,
        "failure_modes": sorted(set(failure_modes)),
        "sha256": _digest(raw),
        "source_sha256": _digest(source.encode("utf-8")),
        "source_host": "youtube.com" if _is_youtube_source(source) else url.hostname.lower(),
        "status": status,
        "coverage_ratio": coverage,
        "observer_version": EXTRACTOR_VERSION,
    }, None


def analyze(checkpoint_dir: Path, next_contest: int, hypothesis_id: str | None = None) -> dict:
    """Summarize prior-video evidence; abstain from every predictive claim."""
    if next_contest < 1:
        raise ValueError("next_contest must be positive")
    rows: list[dict] = []
    rejected: list[dict] = []
    seen_sources: set[str] = set()
    paths = sorted(checkpoint_dir.glob("contest_*.json")) if checkpoint_dir.is_dir() else []
    for path in paths[:MAX_CHECKPOINTS]:
        try:
            row, reason = _read_row(path, next_contest, hypothesis_id)
        except OSError:
            row, reason = None, "IO_ERROR"
        if row is None:
            rejected.append({"filename": path.name, "reason": reason})
            continue
        if row["source_sha256"] in seen_sources:
            rejected.append({"filename": path.name, "reason": "DUPLICATE_SOURCE"})
            continue
        seen_sources.add(row["source_sha256"])
        rows.append(row)
    if len(paths) > MAX_CHECKPOINTS:
        rejected.append({"filename": "(remaining)", "reason": "INPUT_LIMIT_REACHED"})
    rows.sort(key=lambda r: r["contest"])
    counts = Counter(r["status"] for r in rows)
    available = sum(r["status"] not in {"TIMEOUT", "STREAM_FAILED", "UNOBSERVABLE"} for r in rows)
    observed_coverage = [r["coverage_ratio"] for r in rows if r["coverage_ratio"] is not None]
    n = len(rows)
    # Technical sample availability (NOT precision, learning efficacy or lottery weight).
    availability = round((available + 1) / (n + 2), 6) if n >= 10 else None
    holdout = rows[-max(5, n // 4):] if n >= 20 else []
    training = rows[:-len(holdout)] if holdout else rows
    report = {
        "schema": SCHEMA,
        "observer_version": EXTRACTOR_VERSION,
        "next_contest": next_contest,
        "hypothesis_id": hypothesis_id,
        "mode": "SHADOW_SCIENTIFIC_OBSERVATION",
        "learning_status": (
            "NO_VERIFIED_INPUT" if not rows else
            "OBSERVATION_BASELINE_ONLY" if n < 20 else
            "OBSERVATION_HOLDOUT_AVAILABLE"
        ),
        "predictive_evidence": "NOT_ESTABLISHED",
        "predictive_weight_authorized": False,
        "card_generation_authorized": False,
        "models_retrained": False,
        "eligible_observations": n,
        "candidate_observations": counts["CANDIDATE"],
        "status_counts": dict(sorted(counts.items())),
        "failure_modes_counts": dict(sorted(Counter(
            mode for r in rows for mode in r["failure_modes"]
        ).items())),
        "rejected_counts": dict(sorted(Counter(r["reason"] for r in rejected).items())),
        "rejected": rejected,
        "technical_availability_posterior_mean": availability,
        "mean_observed_coverage": (
            round(sum(observed_coverage) / len(observed_coverage), 6)
            if observed_coverage else None
        ),
        "training_contests": [r["contest"] for r in training],
        "holdout_contests": [r["contest"] for r in holdout],
        "inputs": rows,
        "gpt6_review_contract": {
            "role": "review anomalies and propose falsifiable tests; no autonomous API call",
            "may_write_predictive_weights": False,
            "may_edit_checkpoint": False,
            "may_claim_ball_ejection_from_motion_alone": False,
        },
        "next_action": (
            "RECONCILE_VERIFIED_B2_CHECKPOINTS" if not rows else
            "EXPAND_OFFICIAL_VIDEO_COVERAGE_AND_NEGATIVE_CONTROLS"
            if n < 20 else "TEST_HOLDOUT_STABILITY_NO_PREDICTIVE_PROMOTION"
        ),
    }
    report["dataset_sha256"] = _digest(_json_bytes({
        "target": next_contest,
        "hypothesis_id": hypothesis_id,
        "inputs": rows,
        "rejected": rejected,
    }))
    return report


def publish(checkpoint_dir: Path, store: Path, next_contest: int, hypothesis_id: str | None = None) -> dict:
    """Persist immutable snapshot + verified latest pointer; identical inputs are idempotent."""
    report = analyze(checkpoint_dir, next_contest, hypothesis_id)
    store.mkdir(parents=True, exist_ok=True)
    raw = _json_bytes(report)
    sha = _digest(raw)
    snapshot = store / "snapshots" / (sha + ".json")
    if snapshot.exists():
        if _digest(snapshot.read_bytes()) != sha:
            raise ValueError("persisted snapshot content changed")
    else:
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        # Atomic exclusive hard link: no replacement of an immutable snapshot.
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(dir=snapshot.parent, prefix=".visual-v2-", delete=False) as f:
                tmp = Path(f.name)
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            try:
                os.link(tmp, snapshot)
            except FileExistsError:
                if _digest(snapshot.read_bytes()) != sha:
                    raise ValueError("conflicting snapshot")
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
    pointer = {
        "schema": "SMART_VISUAL_LEARNING_V2_LATEST",
        "snapshot_sha256": sha,
        "dataset_sha256": report["dataset_sha256"],
        "snapshot_file": "snapshots/" + sha + ".json",
        "next_contest": next_contest,
        "eligible_observations": report["eligible_observations"],
        "mode": "SHADOW_SCIENTIFIC_OBSERVATION",
        "predictive_weight_authorized": False,
    }
    _atomic(store / "LATEST.json", _json_bytes(pointer))
    return pointer


def main() -> int:
    parser = argparse.ArgumentParser(description="SMART visual memory V2 (shadow-only)")
    parser.add_argument("--checkpoint-dir", default="runtime/video_observation")
    parser.add_argument("--store", default="runtime/video_learning_v2")
    parser.add_argument("--next-contest", required=True, type=int)
    parser.add_argument("--hypothesis-id")
    args = parser.parse_args()
    print(json.dumps(publish(
        Path(args.checkpoint_dir), Path(args.store), args.next_contest, args.hypothesis_id
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
