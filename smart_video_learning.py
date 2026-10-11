"""SMART-MEGA bounded, concurrent visual-learning service.

Checkpoint observation is inherited from smart_video_observation. This module
adds reproducible batch scheduling, shared memory consolidation and a read-only
consumer view with a strict contest/time cutoff. No lottery weights are promoted.
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from smart_video_observation import (
    EXTRACTOR_VERSION, PREDICTIVE_EVIDENCE, ObservationConfig, _atomic_json,
    _checkpoint_path, _is_youtube_source, _utc_now, analyze_contest,
    learned_motion_prior, persist_visual_learning_state, resolve_stream,
    observe_short_sample, locate_mega_segment,
)


def _cutoff(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("cutoff_utc requires a timezone-aware ISO-8601 timestamp")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid cutoff_utc timestamp") from exc
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("cutoff_utc requires timezone")
    return d.astimezone(timezone.utc).isoformat()


def get_visual_features(
    target_contest: str,
    cutoff_utc: str,
    checkpoint_dir: str | Path = "runtime/video_observation",
    hypothesis_id: str | None = None,
    *,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Consume only validated, *earlier* and pre-cutoff video observations."""
    contest = str(target_contest)
    if not (contest.isascii() and contest.isdecimal() and int(contest) > 0):
        raise ValueError("target_contest must be a positive numeric contest")
    cutoff = _cutoff(cutoff_utc)
    prior = learned_motion_prior(
        checkpoint_dir, contest, hypothesis_id, source_url=source_url,
        cutoff_utc=cutoff,
    )
    return {
        "schema": "SMART_VISUAL_FEATURES_V1",
        "target_contest": contest,
        "as_of_utc": cutoff,
        "status": prior["status"],
        "source_contests": prior["training_contests"],
        "source_sha256": prior["training_sha256"],
        "extractor_version": EXTRACTOR_VERSION,
        "hypothesis_id": hypothesis_id,
        "observational_features": {
            "normalized_event_center": prior["normalized_event_center"],
            "observed_spread": prior["observed_spread"],
            "eligible_observations": prior["eligible_observations"],
        },
        "quality": {
            "consensus_active": prior["active"],
            "eligible_source_count": prior["eligible_observations"],
        },
        "limitations": [
            "motion is observational evidence, not a confirmed ball event",
            "post-draw video does not establish predictive advantage",
            "results of the target or later contests are excluded",
        ],
        "predictive_weight_authorized": False,
        "predictive_weight": 0.0,
        "predictive_evidence": PREDICTIVE_EVIDENCE,
    }


def observe_batch(
    items: Iterable[dict[str, Any]],
    checkpoint_dir: str | Path = "runtime/video_observation",
    config: ObservationConfig | None = None,
    *,
    batch_workers: int = 2,
    next_contest: str | None = None,
    force: bool = False,
    hypothesis_id: str | None = None,
    resolver: Callable[[str, float], dict[str, Any]] = resolve_stream,
    sampler: Callable[[dict[str, Any], float], dict[str, Any]] = observe_short_sample,
    segment_locator: Callable[[str, str, float], dict[str, Any]] = locate_mega_segment,
) -> dict[str, Any]:
    """Concurrent independent checkpoints; one deterministic memory commit."""
    cfg = (config or ObservationConfig()).validated()
    if type(batch_workers) is not int or not 1 <= batch_workers <= 4:
        raise ValueError("batch_workers must be between 1 and 4")
    if batch_workers * cfg.workers > 8:
        raise ValueError("batch_workers * per-contest workers must not exceed 8")
    manifest = list(items)
    if not manifest or any(not isinstance(x, dict) for x in manifest):
        raise ValueError("batch requires a nonempty list of objects")
    normalized: list[tuple[str, str, bool]] = []
    seen_id: set[int] = set()
    seen_url: set[str] = set()
    for row in manifest:
        contest = str(row.get("contest_id") or row.get("contest") or "").strip()
        url = str(row.get("source_url") or row.get("url") or "").strip()
        if not (contest.isascii() and contest.isdecimal() and int(contest) > 0):
            raise ValueError("batch contest_id must be a positive integer")
        if not url.startswith("https://") or not urlparse(url).hostname:
            raise ValueError("batch source_url must be valid HTTPS")
        if int(contest) in seen_id or url in seen_url:
            raise ValueError("duplicate contest or video URL in manifest")
        if row.get("hypothesis_id", hypothesis_id) != hypothesis_id:
            raise ValueError("batch must use one hypothesis_id for shared learning")
        seen_id.add(int(contest))
        seen_url.add(url)
        normalized.append((contest, url, bool(row.get("force", force))))
    target = str(max(seen_id) + 1) if next_contest is None else str(next_contest)
    if not (target.isascii() and target.isdecimal() and int(target) > max(seen_id)):
        raise ValueError("next_contest must follow all contests in the batch")
    root = Path(checkpoint_dir)
    start = time.monotonic()
    # Freeze observation learning before workers begin, to avoid races where
    # one worker sees another worker's partially completed study history.
    snapshots = [
        learned_motion_prior(root, contest, hypothesis_id, source_url=url)
        for contest, url, refresh in normalized
    ]
    outcomes: list[dict[str, Any] | None] = [None] * len(normalized)

    def run_one(index: int) -> tuple[int, dict[str, Any]]:
        contest, url, refresh = normalized[index]
        try:
            result = analyze_contest(
                contest, url, root, cfg, force=refresh,
                hypothesis_id=hypothesis_id, resolver=resolver, sampler=sampler,
                segment_locator=segment_locator, persist_memory=False,
                frozen_learning_prior=snapshots[index],
            )
        except Exception as exc:
            result = {
                "schema": "smart.video_observation.v1",
                "contest_id": contest, "source": url,
                "extractor_version": EXTRACTOR_VERSION,
                "hypothesis_id": hypothesis_id, "status": "UNRESOLVED",
                "predictive_evidence": PREDICTIVE_EVIDENCE,
                "semantic_label": None, "confidence": 0.0,
                "event_timestamps_s": [], "created_at_utc": _utc_now(),
                "errors": [f"{type(exc).__name__}: {exc}"],
                "limitations": ["individual batch task failed"],
                "media_persisted_bytes": 0, "checkpoint_reused": False,
            }
            _atomic_json(_checkpoint_path(root, contest), result)
        return index, result

    with ThreadPoolExecutor(max_workers=batch_workers) as pool:
        futures = [pool.submit(run_one, i) for i in range(len(normalized))]
        for future in as_completed(futures):
            index, value = future.result()
            outcomes[index] = value
    results = [r for r in outcomes if r is not None]
    hosts = {
        "youtube.com" if _is_youtube_source(url) else (urlparse(url).hostname or "").lower()
        for _, url, _ in normalized
    }
    common_url = normalized[0][1] if len(hosts) == 1 else None
    # Publish shared state exactly once, strictly after independent workers.
    memory = persist_visual_learning_state(
        root, target, hypothesis_id, source_url=common_url,
    )
    features = get_visual_features(
        target, _utc_now(), root, hypothesis_id, source_url=common_url,
    )
    return {
        "schema": "SMART_VISUAL_BATCH_V1",
        "status": "COMPLETE" if all(r["status"] in {"CANDIDATE", "INSUFFICIENT_EVIDENCE"} for r in results) else "PARTIAL",
        "next_contest": target,
        "processed": len(results),
        "reused": sum(bool(r.get("checkpoint_reused")) for r in results),
        "contest_ids": [r["contest_id"] for r in results],
        "statuses": [r["status"] for r in results],
        "results": results,
        "learning_state_sha256": memory["sha256"],
        "learning_training_observations": memory["training_observations"],
        "consumer_features": features,
        "elapsed_s": round(time.monotonic() - start, 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SMART visual observation batch and consumer")
    parser.add_argument("--manifest", help="JSON list of contest_id and source_url")
    parser.add_argument("--next-contest")
    parser.add_argument("--target-contest", help="Read-only feature consumer target")
    parser.add_argument("--cutoff-utc", help="ISO-8601 observation cutoff for consumer")
    parser.add_argument("--checkpoint-dir", default="runtime/video_observation")
    parser.add_argument("--batch-workers", type=int, default=2)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--hypothesis-id")
    parser.add_argument("--force", action="store_true")
    opts = parser.parse_args()
    if bool(opts.manifest) == bool(opts.target_contest):
        parser.error("choose exactly one of --manifest or --target-contest")
    if opts.manifest:
        rows = json.loads(Path(opts.manifest).read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            parser.error("manifest must be a JSON list")
        value = observe_batch(
            rows, opts.checkpoint_dir, ObservationConfig(workers=opts.workers),
            batch_workers=opts.batch_workers, next_contest=opts.next_contest,
            hypothesis_id=opts.hypothesis_id, force=opts.force,
        )
    else:
        if not opts.cutoff_utc:
            parser.error("--target-contest requires --cutoff-utc")
        value = get_visual_features(
            opts.target_contest, opts.cutoff_utc, opts.checkpoint_dir,
            opts.hypothesis_id,
        )
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
