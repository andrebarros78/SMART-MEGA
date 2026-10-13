"""Durable bridge: official CAIXA catalog -> verified contest queue -> existing video observer.

Discovery and metadata are NOT visual learning. Only uniquely identified official
Mega-Sena contests enter the queue. A checkpoint is evidence of an observation,
not evidence of predictive advantage. No lottery-result labels are read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from smart_video_official_catalog import CHANNEL, read_current
from smart_video_observation import (
    EXTRACTOR_VERSION, PREDICTIVE_EVIDENCE, ObservationConfig,
    _observation_fingerprint, _checkpoint_path, resolve_stream,
    observe_short_sample, locate_mega_segment,
)
from smart_video_learning import observe_batch

SCHEMA = "SMART_CAIXA_VISUAL_QUEUE_V1"
POINTER = "SMART_CAIXA_VISUAL_QUEUE_CURRENT.json"
SUCCEEDED = {"CANDIDATE", "INSUFFICIENT_EVIDENCE"}
ALLOWED_CHECKPOINT_STATUSES = SUCCEEDED | {
    "STREAM_FAILED", "UNRESOLVED", "TIMEOUT", "UNOBSERVABLE"
}


def _encode(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _file_digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


@contextmanager
def _exclusive(root: Path):
    """Cross-platform nonblocking OS file lock, not stale mkdir locks."""
    root.mkdir(parents=True, exist_ok=True)
    file = root / ".smart_caixa_queue.lock"
    if file.is_symlink():
        raise ValueError("QUEUE_LOCK_SYMLINK")
    with file.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("QUEUE_ALREADY_RUNNING") from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("QUEUE_ALREADY_RUNNING") from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_state(root: Path) -> dict[str, Any] | None:
    p = root / POINTER
    if p.is_symlink():
        raise ValueError("QUEUE_POINTER_SYMLINK")
    if not p.exists():
        return None
    if not p.is_file() or p.stat().st_size > 3 * 1024 * 1024:
        raise ValueError("QUEUE_POINTER_INVALID")
    value = json.loads(p.read_text("utf-8"))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("QUEUE_SCHEMA_INVALID")
    claimed = value.get("sha256")
    body = {k: v for k, v in value.items() if k != "sha256"}
    if not isinstance(claimed, str) or _digest(body) != claimed:
        raise ValueError("QUEUE_CHECKSUM_MISMATCH")
    if value.get("predictive_evidence") != PREDICTIVE_EVIDENCE or value.get("predictive_weight") != 0.0:
        raise ValueError("QUEUE_PREDICTIVE_POLICY_VIOLATION")
    if not isinstance(value.get("records"), dict) or len(value["records"]) > 2500:
        raise ValueError("QUEUE_RECORDS_INVALID")
    archive = root / "queue_history" / (claimed + ".json")
    if archive.is_symlink() or not archive.is_file() or archive.read_bytes() != _encode(value):
        raise ValueError("QUEUE_HISTORY_CORRUPT")
    return value


def _publish(root: Path, body: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    current = dict(body)
    comparable = {k: v for k, v in current.items() if k != "previous_sha256"}
    if previous and comparable == {k: v for k, v in previous.items()
                                   if k not in ("previous_sha256", "sha256")}:
        return previous
    current["previous_sha256"] = previous["sha256"] if previous else None
    current["sha256"] = _digest(current)
    archive_dir = root / "queue_history"
    if archive_dir.is_symlink():
        raise ValueError("QUEUE_HISTORY_SYMLINK")
    archive_dir.mkdir(exist_ok=True)
    archive = archive_dir / (current["sha256"] + ".json")
    data = _encode(current)
    if archive.is_symlink():
        raise ValueError("QUEUE_ARCHIVE_SYMLINK")
    if archive.exists():
        if archive.read_bytes() != data:
            raise ValueError("QUEUE_ARCHIVE_COLLISION")
    else:
        try:
            with archive.open("xb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        except FileExistsError:
            if archive.is_symlink() or archive.read_bytes() != data:
                raise ValueError("QUEUE_ARCHIVE_COLLISION")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=root, delete=False,
                                         prefix=".queue.", suffix=".tmp") as output:
            tmp = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, root / POINTER)
        tmp = None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return current


def _official_candidates(catalog: dict[str, Any]) -> tuple[dict[str, dict[str, str]], set[str]]:
    """Deduplicate conservatively; conflicting video IDs for one contest are blocked."""
    if catalog.get("channel_id") != CHANNEL:
        raise ValueError("CATALOG_CHANNEL_UNVERIFIED")
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in catalog["rows"]:
        if entry.get("status") != "CONFIRMED_MEGA_METADATA":
            continue
        contest = str(entry.get("mega_contest") or "")
        video_id = entry.get("id")
        desc_hash = entry.get("description_sha256")
        if not (contest.isascii() and contest.isdecimal() and 1 <= len(contest) <= 12
                and int(contest) > 0 and str(int(contest)) == contest
                and isinstance(video_id, str) and len(video_id) == 11
                and isinstance(desc_hash, str) and len(desc_hash) == 64
                and entry.get("url") == "https://www.youtube.com/watch?v=" + video_id):
            raise ValueError("CONFIRMED_CONTEST_IDENTITY_INVALID")
        groups.setdefault(contest, []).append(entry)
    collisions = {contest for contest, entries in groups.items() if len(entries) != 1}
    result = {
        contest: {
            "contest_id": contest,
            "video_id": entries[0]["id"],
            "source_url": entries[0]["url"],
            "description_sha256": entries[0]["description_sha256"],
        }
        for contest, entries in groups.items() if contest not in collisions
    }
    return dict(sorted(result.items(), key=lambda x: int(x[0]))), collisions


def _checkpoint_proof(root: Path, row: dict[str, Any],
                      config: ObservationConfig, hypothesis_id: str | None
                      ) -> tuple[str, str | None, str | None]:
    path = _checkpoint_path(root, row["contest_id"])
    if not path.exists() and not path.is_symlink():
        return "MISSING", None, None
    if path.is_symlink() or not path.is_file() or not 2 <= path.stat().st_size <= 1024 * 1024:
        return "TAMPERED", None, None
    blob = path.read_bytes()
    try:
        obj = json.loads(blob)
    except (ValueError, UnicodeError):
        return "TAMPERED", None, None
    if not isinstance(obj, dict):
        return "TAMPERED", None, None
    status = obj.get("status")
    if status not in ALLOWED_CHECKPOINT_STATUSES:
        return "TAMPERED", None, None
    # Failed checkpoints may be partial. Never reuse them as finished observations.
    if status not in SUCCEEDED:
        return "FAILED", None, str(status)
    expected = _observation_fingerprint(row["contest_id"], row["source_url"], config, hypothesis_id)
    if (obj.get("schema") != "smart.video_observation.v1"
            or obj.get("contest_id") != row["contest_id"]
            or obj.get("source") != row["source_url"]
            or obj.get("extractor_version") != EXTRACTOR_VERSION
            or obj.get("hypothesis_id") != hypothesis_id
            or obj.get("predictive_evidence") != PREDICTIVE_EVIDENCE
            or obj.get("checkpoint_fingerprint") != expected
            or obj.get("main_params") != vars(config)):
        return "TAMPERED", None, None
    return "VERIFIED", _file_digest(blob), status


def _initial_record(item: dict[str, str]) -> dict[str, Any]:
    return {
        **item, "state": "PENDING", "attempts": 0,
        "checkpoint_sha256": None, "checkpoint_status": None,
    }


def _body(catalog_sha: str, root: Path, hypothesis_id: str | None,
          config: ObservationConfig, records: dict[str, dict[str, Any]]
          ) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "official_channel_id": CHANNEL,
        "catalog_sha256": catalog_sha,
        "checkpoint_dir": str(root.resolve()),
        "hypothesis_id": hypothesis_id,
        "extractor_version": EXTRACTOR_VERSION,
        "config_sha256": _digest(vars(config)),
        "records": records,
        "predictive_evidence": PREDICTIVE_EVIDENCE,
        "predictive_weight": 0.0,
    }


def _summarize(catalog: dict[str, Any], records: dict[str, dict[str, Any]],
               collisions: set[str], attempted: int, waves: int, *, dry_run: bool
               ) -> dict[str, Any]:
    count = lambda state: sum(v["state"] == state for v in records.values())
    return {
        "schema": "SMART_CAIXA_VISUAL_QUEUE_RUN_V1",
        "catalog_broadcasts": len(catalog["rows"]),
        "eligible_unique_contests": len(records),
        "ambiguous_contests_blocked": len(collisions),
        "verified_checkpoints": count("VERIFIED"),
        "pending": count("PENDING") + count("RETRYABLE") + count("RUNNING"),
        "exhausted": count("EXHAUSTED"),
        "quarantined": count("QUARANTINED"),
        "attempted_this_run": attempted,
        "waves_this_run": waves,
        "dry_run": dry_run,
        "predictive_weight": 0.0,
        "predictive_evidence": PREDICTIVE_EVIDENCE,
        "real_media_verified": False,
    }


def run_official_queue(
    catalog_dir: str | Path,
    checkpoint_dir: str | Path,
    queue_dir: str | Path,
    *,
    max_items: int = 500,
    batch_workers: int = 4,
    workers: int = 1,
    max_attempts: int = 3,
    hypothesis_id: str | None = None,
    dry_run: bool = False,
    resolver: Callable = resolve_stream,
    sampler: Callable = observe_short_sample,
    segment_locator: Callable = locate_mega_segment,
) -> dict[str, Any]:
    """Reconcile before every wave. A crash resumes using checked checkpoint hashes.

    Queue state is journaled before an observation begins; after a crash,
    succeeded checkpoints are verified before further video access.
    """
    if type(max_items) is not int or not 1 <= max_items <= 500:
        raise ValueError("MAX_ITEMS_OUT_OF_RANGE")
    if type(batch_workers) is not int or not 1 <= batch_workers <= 8:
        raise ValueError("BATCH_WORKERS_OUT_OF_RANGE")
    if type(workers) is not int or not 1 <= workers <= 8 or workers * batch_workers > 8:
        raise ValueError("RESOURCE_BUDGET_EXCEEDED")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
        raise ValueError("MAX_ATTEMPTS_OUT_OF_RANGE")
    cfg = ObservationConfig(workers=workers).validated()
    cp_root = Path(checkpoint_dir)
    q_root = Path(queue_dir)
    if cp_root.is_symlink() or q_root.is_symlink():
        raise ValueError("QUEUE_OR_CHECKPOINT_SYMLINK")
    if cp_root.resolve() == q_root.resolve():
        raise ValueError("QUEUE_AND_CHECKPOINT_ROOT_MUST_DIFFER")
    catalog = read_current(Path(catalog_dir))
    if catalog is None:
        raise ValueError("OFFICIAL_CATALOG_MISSING")
    eligible, collisions = _official_candidates(catalog)
    if dry_run:
        previous = _read_state(q_root) if q_root.is_dir() else None
        return _reconcile_and_report(catalog, eligible, collisions, cp_root, q_root, cfg,
                                     hypothesis_id, previous, max_attempts, dry_run=True)

    with _exclusive(q_root):
        previous = _read_state(q_root)
        return _execute(catalog, eligible, collisions, cp_root, q_root, cfg, hypothesis_id,
                        previous, max_items, batch_workers, max_attempts,
                        resolver, sampler, segment_locator)


def _reconcile_and_report(catalog, eligible, collisions, cp_root, q_root, cfg,
                          hypothesis_id, previous, max_attempts, *, dry_run=False):
    if previous and (previous["checkpoint_dir"] != str(cp_root.resolve())
                     or previous["hypothesis_id"] != hypothesis_id
                     or previous["extractor_version"] != EXTRACTOR_VERSION
                     or previous["config_sha256"] != _digest(vars(cfg))
                     or previous.get("official_channel_id") != CHANNEL):
        raise ValueError("QUEUE_CONFIG_OR_PATH_DRIFT")
    old = previous["records"] if previous else {}
    if set(old) - set(eligible):
        raise ValueError("QUEUE_OFFICIAL_IDENTITY_DISAPPEARED")
    records: dict[str, dict[str, Any]] = {}
    for contest, identity in eligible.items():
        prior = old.get(contest)
        if prior:
            if any(prior.get(k) != identity[k] for k in identity):
                raise ValueError("QUEUE_SOURCE_IDENTITY_DRIFT")
            entry = dict(prior)
        else:
            entry = _initial_record(identity)
        state, sha, status = _checkpoint_proof(cp_root, identity, cfg, hypothesis_id)
        if entry.get("checkpoint_sha256") and (
                state != "VERIFIED" or entry["checkpoint_sha256"] != sha):
            raise ValueError("COMPLETED_CHECKPOINT_LOST_OR_CHANGED")
        if state == "VERIFIED":
            entry.update(state="VERIFIED", checkpoint_sha256=sha, checkpoint_status=status)
        elif state == "TAMPERED":
            entry.update(state="QUARANTINED", checkpoint_sha256=None, checkpoint_status=None)
        elif entry["state"] not in ("QUARANTINED", "EXHAUSTED"):
            entry.update(state="EXHAUSTED" if entry["attempts"] >= max_attempts else "PENDING",
                         checkpoint_sha256=None, checkpoint_status=status)
        records[contest] = entry
    report = _summarize(catalog, records, collisions, 0, 0, dry_run=dry_run)
    return report if dry_run else (records, _body(catalog["sha256"], cp_root, hypothesis_id, cfg, records))


def _execute(catalog, eligible, collisions, cp_root, q_root, cfg, hypothesis_id,
             previous, max_items, batch_workers, max_attempts,
             resolver, sampler, segment_locator):
    attempted, waves = 0, 0
    while True:
        records, body = _reconcile_and_report(
            catalog, eligible, collisions, cp_root, q_root, cfg,
            hypothesis_id, previous, max_attempts)
        previous = _publish(q_root, body, previous)
        ready = [k for k, row in records.items() if row["state"] == "PENDING"
                 and row["attempts"] < max_attempts]
        if not ready or attempted >= max_items:
            break
        chunk = ready[:min(batch_workers, max_items - attempted)]
        for contest in chunk:
            records[contest]["state"] = "RUNNING"
            records[contest]["attempts"] += 1
        previous = _publish(q_root, _body(catalog["sha256"], cp_root, hypothesis_id,
                                         cfg, records), previous)
        # The existing observer owns checkpoint creation and memory; this bridge
        # deliberately never fakes a completed observation or rewrites it.
        observe_batch(
            [{"contest_id": contest, "source_url": eligible[contest]["source_url"]}
             for contest in chunk],
            cp_root, cfg, batch_workers=len(chunk), hypothesis_id=hypothesis_id,
            force=True, resolver=resolver, sampler=sampler,
            segment_locator=segment_locator,
        )
        attempted += len(chunk)
        waves += 1
        # Re-read checkpoint bytes and journal before considering another wave.
        records, body = _reconcile_and_report(
            catalog, eligible, collisions, cp_root, q_root, cfg,
            hypothesis_id, previous, max_attempts)
        previous = _publish(q_root, body, previous)
    records, _ = _reconcile_and_report(
        catalog, eligible, collisions, cp_root, q_root, cfg, hypothesis_id,
        previous, max_attempts)
    result = _summarize(catalog, records, collisions, attempted, waves, dry_run=False)
    result["queue_state_sha256"] = previous["sha256"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Official CAIXA catalog -> durable visual checkpoint queue")
    parser.add_argument("--catalog-dir", required=True)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--queue-dir", required=True)
    parser.add_argument("--max-items", type=int, default=500)
    parser.add_argument("--batch-workers", type=int, default=4)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--hypothesis-id")
    parser.add_argument("--dry-run", action="store_true")
    a = parser.parse_args()
    result = run_official_queue(
        a.catalog_dir, a.checkpoint_dir, a.queue_dir,
        max_items=a.max_items, batch_workers=a.batch_workers,
        workers=a.workers, max_attempts=a.max_attempts,
        hypothesis_id=a.hypothesis_id, dry_run=a.dry_run,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
