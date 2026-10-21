"""SMART-MEGA bounded, concurrent visual-learning service.

Checkpoint observation is inherited from smart_video_observation. This module
adds reproducible batch scheduling, shared memory consolidation and a read-only
consumer view with a strict contest/time cutoff. No lottery weights are promoted.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from smart_video_observation import (
    EXTRACTOR_VERSION, PREDICTIVE_EVIDENCE, VALID_STATUSES, ObservationConfig, _observation_fingerprint, _atomic_json,
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
    # Defensive PIT boundary on the official consumer output, independent of the
    # upstream checkpoint reader. Do not silently accept later contest evidence.
    sources = prior.get("training_contests")
    if not isinstance(sources, list):
        raise ValueError("PIT_SOURCE_CONTRACT_INVALID")
    for source_contest in sources:
        value = str(source_contest)
        if (not value.isascii() or not value.isdecimal()
                or int(value) >= int(contest)):
            raise ValueError("PIT_FUTURE_OR_TARGET_CONTEST")
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



def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _verify_study_snapshot(value: dict[str, Any]) -> None:
    if not isinstance(value, dict) or value.get("schema") != "SMART_VISUAL_STUDY_V1":
        raise ValueError("invalid visual study schema")
    document = dict(value)
    saved_sha = document.pop("sha256", None)
    if not isinstance(saved_sha, str) or saved_sha != _digest(document):
        raise ValueError("visual study checksum invalid")


def publish_visual_study(
    checkpoint_dir: str | Path,
    features: dict[str, Any],
) -> dict[str, Any]:
    """Materialize verifiable observation examples without result labels.

    Immutable per-content revisions preserve historical study. The latest
    pointer is monotonic across contest backfills and replays are idempotent.
    """
    root = Path(checkpoint_dir)
    if features.get("schema") != "SMART_VISUAL_FEATURES_V1":
        raise ValueError("study requires validated visual features")
    examples = []
    for n in features["source_contests"]:
        path = _checkpoint_path(root, str(n))
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != features["source_sha256"][str(n)]:
            raise ValueError("study source checkpoint hash mismatch")
        row = json.loads(raw)
        if row.get("contest_id") != str(n) or row.get("status") != "CANDIDATE":
            raise ValueError("study source checkpoint is incompatible")
        examples.append({
            "contest_id": str(n),
            "checkpoint_sha256": features["source_sha256"][str(n)],
            "recorded_at_utc": row.get("created_at_utc"),
            "source_host": (urlparse(row.get("source", "")).hostname or "").lower(),
            "events_s": row.get("event_timestamps_s") or [],
            "observed_coverage_ratio": row.get("coverage_ratio"),
            "spatial": row.get("spatial"),
            "cadence": row.get("cadence"),
            "semantic_label": "MOTION_EVENT_CANDIDATE",
        })
    body: dict[str, Any] = {
        "schema": "SMART_VISUAL_STUDY_V1",
        "target_contest": features["target_contest"],
        "as_of_utc": features["as_of_utc"],
        "features": features,
        "studied_contests": len(examples),
        "examples": examples,
        "predictive_weight_authorized": False,
        "predictive_weight": 0.0,
    }
    current = root / "SMART_VISUAL_STUDY_CURRENT.json"
    previous = None
    if current.exists() or current.is_symlink():
        if current.is_symlink():
            raise ValueError("visual study current pointer cannot be a symlink")
        previous = json.loads(current.read_text(encoding="utf-8"))
        _verify_study_snapshot(previous)
        if (previous["target_contest"] == body["target_contest"]
                and previous["features"]["source_sha256"] == features["source_sha256"]
                and previous["features"]["observational_features"] == features["observational_features"]):
            history_dir = root / "study_history"
            archived = history_dir / (previous["sha256"] + ".json")
            canonical_bytes = json.dumps(
                previous, ensure_ascii=False, sort_keys=True, indent=2,
            ).encode("utf-8")
            if (history_dir.is_symlink() or archived.is_symlink()
                    or not archived.is_file() or archived.read_bytes() != canonical_bytes):
                raise ValueError("visual study immutable history missing or corrupt")
            return previous
    body["previous_sha256"] = previous["sha256"] if previous else None
    body["sha256"] = _digest(body)
    _verify_study_snapshot(body)
    archive = root / "study_history"
    if archive.is_symlink():
        raise ValueError("visual study history directory cannot be a symlink")
    archive.mkdir(parents=True, exist_ok=True)
    destination = archive / (body["sha256"] + ".json")
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or destination.read_bytes() != encoded:
            raise ValueError("visual study history collision or corruption")
    else:
        temp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix="study.", suffix=".tmp",
                dir=archive, delete=False,
            ) as handle:
                temp = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp, destination)
            except FileExistsError:
                if destination.is_symlink() or destination.read_bytes() != encoded:
                    raise ValueError("visual study history collision or corruption")
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    if previous is None or int(body["target_contest"]) >= int(previous["target_contest"]):
        _atomic_json(current, body)
    return body


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
    if type(batch_workers) is not int or not 1 <= batch_workers <= 8:
        raise ValueError("batch_workers must be between 1 and 8")
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
    study = publish_visual_study(root, features)
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
        "study_sha256": study["sha256"],
        "study_examples": study["studied_contests"],
        "elapsed_s": round(time.monotonic() - start, 6),
    }



def audit_checkpoint_inventory(
    checkpoint_dir: str | Path = "runtime/video_observation",
    *,
    expected_count: int = 13,
    limit: int = 512,
) -> dict[str, Any]:
    """Inventory B2 checkpoints read-only; never downloads videos or writes memory.

    This is a technical integrity audit, not a predictive signal or an approval
    of the observed motion semantics. Results expose hashes, not raw video data.
    """
    if type(expected_count) is not int or expected_count < 1 or expected_count > 512:
        raise ValueError("expected_count must be 1..512")
    if type(limit) is not int or limit < expected_count or limit > 512:
        raise ValueError("limit must be between expected_count and 512")
    root = Path(checkpoint_dir)
    result: dict[str, Any] = {
        "schema": "SMART_VIDEO_CHECKPOINT_INVENTORY_V1",
        "checkpoint_dir": str(root),
        "expected_count": expected_count,
        "status": "INCOMPLETE",
        "files_discovered": 0,
        "valid_count": 0,
        "invalid_count": 0,
        "truncated": False,
        "contest_ids": [],
        "records": [],
        "predictive_evidence": PREDICTIVE_EVIDENCE,
        "predictive_weight_authorized": False,
        "predictive_weight": 0.0,
        "read_only": True,
    }
    if root.is_symlink() or not root.is_dir():
        result["status"] = "PATH_UNAVAILABLE"
        return result

    names: list[tuple[int, Path]] = []
    for item in root.glob("contest_*.json"):
        match = re.fullmatch(r"contest_([0-9]{1,12})\.json", item.name)
        if match and int(match.group(1)) > 0:
            names.append((int(match.group(1)), item))
    names.sort(key=lambda pair: (pair[0], pair[1].name), reverse=True)
    result["files_discovered"] = len(names)
    result["truncated"] = len(names) > limit
    outcome_keys = {
        "winning_numbers", "drawn_numbers", "result_numbers", "dezenas_sorteadas",
        "hit_count", "official_result", "sorteadas", "numero_sorteado",
        "actual_winners", "winner_information", "prize_distribution",
    }

    def has_result_labels(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                str(key).lower() in outcome_keys or has_result_labels(val)
                for key, val in value.items()
            )
        if isinstance(value, list):
            return any(has_result_labels(val) for val in value)
        return False

    for contest, path in names[:limit]:
        record: dict[str, Any] = {"contest_id": str(contest), "integrity": "REJECTED"}
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("SYMLINK_OR_NONFILE")
            size = path.stat().st_size
            if size < 2 or size > 1024 * 1024:
                raise ValueError("SIZE_OUT_OF_RANGE")
            raw = path.read_bytes()
            record["sha256"] = hashlib.sha256(raw).hexdigest()
            record["size_bytes"] = len(raw)
            obj = json.loads(raw)
            if not isinstance(obj, dict) or has_result_labels(obj):
                raise ValueError("INVALID_OBJECT_OR_RESULT_LEAKAGE")
            if str(obj.get("contest_id")) != str(contest):
                raise ValueError("CONTEST_ID_MISMATCH")
            if obj.get("extractor_version") != EXTRACTOR_VERSION:
                raise ValueError("EXTRACTOR_VERSION_MISMATCH")
            if obj.get("predictive_evidence") != PREDICTIVE_EVIDENCE:
                raise ValueError("PREDICTIVE_CLAIM_UNSAFE")
            status = str(obj.get("status") or "")
            if status not in VALID_STATUSES:
                raise ValueError("STATUS_UNRECOGNIZED")
            url = obj.get("source")
            if not isinstance(url, str):
                raise ValueError("SOURCE_MISSING")
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("SOURCE_UNVERIFIED")
            cfg = ObservationConfig(**obj["main_params"]).validated()
            if obj.get("checkpoint_fingerprint") != _observation_fingerprint(
                str(contest), url, cfg, obj.get("hypothesis_id")
            ):
                raise ValueError("FINGERPRINT_MISMATCH")
            timestamp = _cutoff(str(obj["created_at_utc"]))
            if status == "CANDIDATE":
                scope = obj.get("analysis_scope")
                events = obj.get("event_timestamps_s")
                if not isinstance(scope, dict) or not isinstance(events, list):
                    raise ValueError("CANDIDATE_SCOPE_MISSING")
                lo, hi = float(scope["start_s"]), float(scope["end_s"])
                if not (hi > lo and len(events) >= cfg.min_candidate_events and
                        all(lo <= float(t) <= hi for t in events)):
                    raise ValueError("CANDIDATE_EVENTS_INVALID")
                if (obj.get("spatial_consensus") or {}).get("recurrent") is not True:
                    raise ValueError("CANDIDATE_CONSENSUS_MISSING")
                if _is_youtube_source(url) and scope.get("segment_guard_passed") is not True:
                    raise ValueError("CANDIDATE_YOUTUBE_SCOPE_NOT_GUARDED")
            record.update({"integrity": "VERIFIED", "status": status,
                           "created_at_utc": timestamp,
                           "event_count": len(obj.get("event_timestamps_s") or [])})
            result["valid_count"] += 1
        except (OSError, KeyError, TypeError, ValueError, OverflowError) as exc:
            error = str(exc)
            record["reason"] = error if error in {
                "SYMLINK_OR_NONFILE", "SIZE_OUT_OF_RANGE",
                "INVALID_OBJECT_OR_RESULT_LEAKAGE", "CONTEST_ID_MISMATCH",
                "EXTRACTOR_VERSION_MISMATCH", "PREDICTIVE_CLAIM_UNSAFE",
                "STATUS_UNRECOGNIZED", "SOURCE_MISSING", "SOURCE_UNVERIFIED",
                "FINGERPRINT_MISMATCH", "CANDIDATE_SCOPE_MISSING",
                "CANDIDATE_EVENTS_INVALID", "CANDIDATE_CONSENSUS_MISSING",
                "CANDIDATE_YOUTUBE_SCOPE_NOT_GUARDED",
            } else type(exc).__name__
            result["invalid_count"] += 1
        result["records"].append(record)
    result["contest_ids"] = sorted(int(r["contest_id"]) for r in result["records"])
    if (not result["truncated"] and result["valid_count"] == expected_count and
            result["invalid_count"] == 0 and result["files_discovered"] == expected_count):
        result["status"] = "CHECKPOINT_INTEGRITY_PASS"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="SMART visual observation batch and consumer")
    parser.add_argument("--manifest", help="JSON list of contest_id and source_url")
    parser.add_argument("--inventory-readonly", action="store_true", help="read-only B2 checkpoint integrity inventory")
    parser.add_argument("--expected-checkpoints", type=int, default=13)
    parser.add_argument("--next-contest")
    parser.add_argument("--target-contest", help="Read-only feature consumer target")
    parser.add_argument("--memory-readonly", action="store_true",
                        help="Read PIT-verified episodic/semantic/graph memory (no model or source gate)")
    parser.add_argument("--cutoff-utc", help="ISO-8601 observation cutoff for consumer")
    parser.add_argument("--checkpoint-dir", default="runtime/video_observation")
    parser.add_argument("--batch-workers", type=int, default=2)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--hypothesis-id")
    parser.add_argument("--force", action="store_true")
    opts = parser.parse_args()
    if sum(bool(x) for x in (opts.manifest, opts.target_contest, opts.inventory_readonly)) != 1:
        parser.error("choose exactly one of --manifest, --target-contest or --inventory-readonly")
    if opts.memory_readonly and not opts.target_contest:
        parser.error("--memory-readonly requires --target-contest and --cutoff-utc")
    if opts.inventory_readonly:
        if opts.force or opts.next_contest or opts.cutoff_utc:
            parser.error("--inventory-readonly cannot mutate or use target options")
        try:
            value = audit_checkpoint_inventory(opts.checkpoint_dir, expected_count=opts.expected_checkpoints)
        except ValueError as exc:
            parser.error(str(exc))
    elif opts.manifest:
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
        reader = get_visual_learning_memory if opts.memory_readonly else get_visual_features
        value = reader(
            opts.target_contest, opts.cutoff_utc, opts.checkpoint_dir,
            opts.hypothesis_id,
        )
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def get_vendor_learning_status() -> dict[str, Any]:
    """Report integrity and explicitly blocked optional model engines."""
    from smart_video_vendor import get_status
    return get_status()


def normalize_observation_entities(text: str) -> str:
    """Use the pinned TaskMem normalization routine without model execution."""
    from smart_video_vendor import normalize_taskmem_entities
    return normalize_taskmem_entities(text)


def get_visual_learning_memory(
    target_contest: str,
    cutoff_utc: str,
    checkpoint_dir: str | Path = "runtime/video_observation",
    hypothesis_id: str | None = None,
    *,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Read PIT-verified episodic, semantic and graph evidence from pinned video."""
    from isolated_source_gate.visual_evidence_memory import get_visual_learning_memory as read_memory
    return read_memory(target_contest, cutoff_utc, checkpoint_dir, hypothesis_id,
                       source_url=source_url)


if __name__ == "__main__":
    raise SystemExit(main())
