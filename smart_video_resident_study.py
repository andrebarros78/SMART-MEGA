"""Finite 10–15-hour B2 resident study supervisor (stdlib + existing SMART-MEGA).

Runs independently of the ChatGPT session. No YouTube requests are made here:
the worker only reconciles existing official checkpoints and per-video quality.
An externally authorized, independently tested observation executor must be
connected before actual media acquisition may start. Authentication challenges
never trigger implicit browser-cookie use or proxy fallback.
"""
from __future__ import annotations

import argparse
import json
import re
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from smart_video_official_catalog import read_current
from smart_video_official_queue import _read_state, _digest, _encode
from smart_video_observation_quality import save_quality_snapshot
from smart_video_source_access import read_source_gate

SCHEMA = "SMART_CAIXA_RESIDENT_STUDY_V1"
DATABASE = "SMART_CAIXA_RESIDENT.sqlite3"
LOCK = ".smart_caixa_resident.lock"
STATES = {
    "PAUSED_SOURCE_ACCESS", "PAUSED_AWAITING_MEDIA_AUTHORIZATION",
    "WINDOW_FINISHED", "QUARANTINED_SOURCE_GATE",
}
DEFAULT_INTERVAL_SECONDS = 300


@contextmanager
def _exclusive(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / LOCK
    if lock.is_symlink():
        raise ValueError("RESIDENT_LOCK_SYMLINK")
    with lock.open("a+b") as h:
        h.seek(0, os.SEEK_END)
        if h.tell() == 0:
            h.write(b"\0")
            h.flush()
        h.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                h.seek(0)
                msvcrt.locking(h.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("RESIDENT_ALREADY_RUNNING") from exc
            try:
                yield
            finally:
                h.seek(0)
                msvcrt.locking(h.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(h.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("RESIDENT_ALREADY_RUNNING") from exc
            try:
                yield
            finally:
                fcntl.flock(h.fileno(), fcntl.LOCK_UN)


def _connect(root: Path):
    path = root / DATABASE
    if path.is_symlink():
        raise ValueError("RESIDENT_SQLITE_SYMLINK")
    conn = sqlite3.connect(path, timeout=12)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resident (
            id INTEGER PRIMARY KEY CHECK(id=1),
            started_at_epoch INTEGER NOT NULL,
            deadline_epoch INTEGER NOT NULL,
            source_queue_sha256 TEXT NOT NULL,
            source_catalog_sha256 TEXT NOT NULL,
            state TEXT NOT NULL,
            heartbeat_count INTEGER NOT NULL,
            heartbeat_epoch INTEGER NOT NULL,
            quality_sha256 TEXT,
            source_gate_sha256 TEXT
        )
    """)
    conn.commit()
    return conn



def _reconcile_queue_history(queue_root: Path, current: dict, baseline_sha: str):
    """Accept only cryptographically journaled, identity-preserving progress.

    The last recognized SHA is an ancestor, not necessarily the direct parent:
    one observation wave may publish multiple immutable queue snapshots.
    """
    if baseline_sha == current["sha256"]:
        return
    if not isinstance(baseline_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", baseline_sha):
        raise ValueError("RESIDENT_QUEUE_HISTORY_INVALID")
    visited = {current["sha256"]}
    node = current
    ancestor = None
    for _ in range(4000):
        old = node.get("previous_sha256")
        if not isinstance(old, str) or not re.fullmatch(r"[0-9a-f]{64}", old) or old in visited:
            raise ValueError("RESIDENT_QUEUE_HISTORY_INVALID")
        visited.add(old)
        archive = queue_root / "queue_history" / (old + ".json")
        if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 3 * 1024 * 1024:
            raise ValueError("RESIDENT_QUEUE_HISTORY_INVALID")
        blob = archive.read_bytes()
        try:
            doc = json.loads(blob)
        except (ValueError, UnicodeError) as exc:
            raise ValueError("RESIDENT_QUEUE_HISTORY_INVALID") from exc
        if (not isinstance(doc, dict) or doc.get("sha256") != old
                or _digest({k: v for k, v in doc.items() if k != "sha256"}) != old
                or blob != _encode(doc)):
            raise ValueError("RESIDENT_QUEUE_HISTORY_INVALID")
        if old == baseline_sha:
            ancestor = doc
            break
        node = doc
    if ancestor is None:
        raise ValueError("RESIDENT_QUEUE_HISTORY_INVALID")
    if (ancestor.get("catalog_sha256") != current.get("catalog_sha256")
            or ancestor.get("checkpoint_dir") != current.get("checkpoint_dir")
            or ancestor.get("config_sha256") != current.get("config_sha256")
            or ancestor.get("official_channel_id") != current.get("official_channel_id")
            or ancestor.get("hypothesis_id") != current.get("hypothesis_id")
            or ancestor.get("predictive_weight") != 0.0
            or current.get("predictive_weight") != 0.0):
        raise ValueError("RESIDENT_QUEUE_IDENTITY_DRIFT")
    earlier = ancestor.get("records") or {}
    later = current.get("records") or {}
    if set(earlier) != set(later):
        raise ValueError("RESIDENT_QUEUE_IDENTITY_DRIFT")
    identity_keys = ("contest_id", "video_id", "source_url", "description_sha256")
    for contest, past in earlier.items():
        after = later[contest]
        if any(past.get(k) != after.get(k) for k in identity_keys):
            raise ValueError("RESIDENT_QUEUE_IDENTITY_DRIFT")
        old_attempts, new_attempts = past.get("attempts"), after.get("attempts")
        if (type(old_attempts) is not int or type(new_attempts) is not int
                or old_attempts < 0 or new_attempts < old_attempts or new_attempts > 5):
            raise ValueError("RESIDENT_QUEUE_ATTEMPT_REGRESSION")
        if (past.get("state") == "VERIFIED" and
                (after.get("state") != "VERIFIED" or
                 after.get("checkpoint_sha256") != past.get("checkpoint_sha256"))):
            raise ValueError("RESIDENT_QUEUE_COMPLETION_REGRESSION")
        if past.get("state") in {"QUARANTINED", "EXHAUSTED"} and past != after:
            raise ValueError("RESIDENT_QUEUE_TERMINAL_REGRESSION")


def read_status(root: str | Path):
    p = Path(root) / DATABASE
    if p.is_symlink():
        raise ValueError("RESIDENT_SQLITE_SYMLINK")
    if not p.is_file():
        return {"schema": SCHEMA, "state": "NOT_STARTED"}
    conn = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rec = conn.execute("SELECT * FROM resident WHERE id=1").fetchone()
        if rec is None:
            return {"schema": SCHEMA, "state": "NOT_STARTED"}
        return {
            "schema": SCHEMA, "state": rec["state"],
            "started_at_epoch": rec["started_at_epoch"],
            "deadline_epoch": rec["deadline_epoch"],
            "heartbeat_count": rec["heartbeat_count"],
            "last_heartbeat_epoch": rec["heartbeat_epoch"],
            "queue_sha256": rec["source_queue_sha256"],
            "catalog_sha256": rec["source_catalog_sha256"],
            "quality_sha256": rec["quality_sha256"],
            "source_gate_sha256": rec["source_gate_sha256"],
            "media_requests_this_tick": 0,
            "official_frames_decoded_verified": 0,
            "learning_complete": False,
            "predictive_weight": 0.0,
        }
    finally:
        conn.close()


def tick(
    root: str | Path, catalog_dir: str | Path,
    checkpoint_dir: str | Path, queue_dir: str | Path,
    *, window_hours: int = 15, now: int | float | None = None,
):
    """One durable transaction and quality reconciliation, with zero network I/O."""
    if type(window_hours) is not int or not 10 <= window_hours <= 15:
        raise ValueError("RESIDENT_WINDOW_HOURS_INVALID")
    epoch = int(time.time() if now is None else now)
    if epoch < 0:
        raise ValueError("RESIDENT_EPOCH_INVALID")
    root, catalog_dir, cp_root, q_root = map(
        Path, (root, catalog_dir, checkpoint_dir, queue_dir)
    )
    if any(p.is_symlink() for p in (root, catalog_dir, cp_root, q_root)):
        raise ValueError("RESIDENT_ROOT_SYMLINK")
    resolved = [p.resolve() for p in (root, catalog_dir, cp_root, q_root)]
    if len(set(resolved)) != 4:
        raise ValueError("RESIDENT_ROOT_COLLISION")
    if not q_root.is_dir() or not catalog_dir.is_dir():
        raise ValueError("RESIDENT_CATALOG_OR_QUEUE_MISSING")

    with _exclusive(root):
        # Check signed catalog and queue pointers; checkpoint data itself never
        # enters the resident database (only hashes and counts do).
        cat = read_current(catalog_dir)
        queue = _read_state(q_root)
        if cat is None or queue is None or queue["catalog_sha256"] != cat["sha256"]:
            raise ValueError("RESIDENT_CATALOG_OR_QUEUE_DRIFT")
        if queue["checkpoint_dir"] != str(cp_root.resolve()):
            raise ValueError("RESIDENT_CHECKPOINT_DIR_DRIFT")

        conn = _connect(root)
        try:
            previous = conn.execute("SELECT * FROM resident WHERE id=1").fetchone()
            if previous is None:
                conn.execute(
                    """INSERT INTO resident
                       (id,started_at_epoch,deadline_epoch,source_queue_sha256,
                        source_catalog_sha256,state,heartbeat_count,heartbeat_epoch)
                       VALUES (1,?,?,?,?,?,?,?)""",
                    (epoch, epoch + window_hours*3600, queue["sha256"],
                     cat["sha256"], "PAUSED_AWAITING_MEDIA_AUTHORIZATION", 0, epoch)
                )
                conn.commit()
                previous = conn.execute("SELECT * FROM resident WHERE id=1").fetchone()
            if previous["source_catalog_sha256"] != cat["sha256"]:
                raise ValueError("RESIDENT_CATALOG_OR_QUEUE_DRIFT")
            _reconcile_queue_history(q_root, queue, previous["source_queue_sha256"])
            if previous["deadline_epoch"] - previous["started_at_epoch"] != window_hours*3600:
                raise ValueError("RESIDENT_WINDOW_CONFIG_DRIFT")
            if epoch < previous["started_at_epoch"]:
                raise ValueError("RESIDENT_CLOCK_ROLLBACK")

            # If the official access contract is missing/tampered, quarantine.
            try:
                source = read_source_gate(q_root)
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
                conn.execute("UPDATE resident SET state=?,heartbeat_epoch=? WHERE id=1",
                             ("QUARANTINED_SOURCE_GATE", epoch))
                conn.commit()
                raise ValueError("RESIDENT_SOURCE_GATE_INVALID")

            prior = conn.execute("SELECT state FROM resident WHERE id=1").fetchone()["state"]
            if prior == "QUARANTINED_SOURCE_GATE":
                raise ValueError("RESIDENT_SOURCE_GATE_QUARANTINED")

            # Reporting can consume existing observations, never fetch media.
            if epoch < previous["deadline_epoch"]:
                quality = save_quality_snapshot(
                    catalog_dir, cp_root, q_root, workers=1
                )
                if quality.get("queue_sha256") != queue["sha256"]:
                    raise ValueError("RESIDENT_QUEUE_CONCURRENT_UPDATE")
                unsafe = {"CHECKPOINT_UNTRUSTED", "CHECKPOINT_SHA_MISMATCH",
                          "CHECKPOINT_CORRUPT_OR_MISSING"}
                if any(quality.get("count_by_quality", {}).get(key, 0) > 0
                       for key in unsafe):
                    raise ValueError("RESIDENT_CHECKPOINT_INTEGRITY_VIOLATION")
                state = ("PAUSED_SOURCE_ACCESS" if source["state"] == "BLOCKED"
                         else "PAUSED_AWAITING_MEDIA_AUTHORIZATION")
            else:
                state = "WINDOW_FINISHED"
                # Last verified quality pointer is retained if the window ended.
                p = q_root / "SMART_CAIXA_OBSERVATIONAL_QUALITY_CURRENT.json"
                quality = json.loads(p.read_text("utf-8")) if p.is_file() else None
            qs = quality.get("sha256") if quality else previous["quality_sha256"]
            conn.execute(
                """UPDATE resident SET state=?,heartbeat_epoch=?,
                   heartbeat_count=heartbeat_count+1,
                   quality_sha256=?,source_gate_sha256=?,
                   source_queue_sha256=? WHERE id=1""",
                (state, epoch, qs, source.get("sha256"), queue["sha256"])
            )
            conn.commit()
            summary = read_status(root)
            summary.update({
                "contests_in_queue": len(queue["records"]),
                "queue_pending": sum(row.get("state") == "PENDING"
                                     for row in queue["records"].values()),
                "quality_classification": quality.get("count_by_quality", {}) if quality else {},
                "frames_analyzed": 0,
                "source_gate_blocked": source["state"] == "BLOCKED",
                "media_requests_this_tick": 0,
            })
            return summary
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="15h durable supervisor; NO unauthorised YouTube/video access"
    )
    parser.add_argument("--root", required=True)
    parser.add_argument("--catalog-dir")
    parser.add_argument("--checkpoint-dir")
    parser.add_argument("--queue-dir")
    parser.add_argument("--window-hours", type=int, default=15)
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(read_status(args.root), ensure_ascii=False, sort_keys=True))
        return 0
    if any(not item for item in (args.catalog_dir, args.checkpoint_dir, args.queue_dir)):
        parser.error("catalog, checkpoint and queue directories required")
    if not 60 <= args.interval_seconds <= 900:
        parser.error("interval seconds must be 60..900")
    while True:
        state = tick(
            args.root, args.catalog_dir, args.checkpoint_dir, args.queue_dir,
            window_hours=args.window_hours,
        )
        print(json.dumps(state, sort_keys=True), flush=True)
        if args.once or state["state"] in ("WINDOW_FINISHED", "QUARANTINED_SOURCE_GATE"):
            return 0
        remaining = state["deadline_epoch"] - int(time.time())
        if remaining <= 0:
            return 0
        time.sleep(min(args.interval_seconds, remaining))


if __name__ == "__main__":
    raise SystemExit(main())
