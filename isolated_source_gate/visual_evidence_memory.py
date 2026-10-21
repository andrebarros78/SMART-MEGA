"""PIT-safe, bounded episodic+graph evidence memory for SMART-MEGA V6.

Native TaskMem/M3-style memory organization; not their GPU/LLM inference
engines. Only an already-verified historical checkpoint consumer can authorize
an episode. Persisted snapshots are descriptive and never influence a card.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_VISUAL_EVIDENCE_MEMORY_V1"
MAX_EPISODE_EVENTS = 512
INDEX_NAME = ".visual_learning_memory.sqlite"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _validated_cutoff(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("PIT_CUTOFF_INVALID")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("PIT_CUTOFF_INVALID") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("PIT_CUTOFF_UNZONED")
    return stamp.astimezone(timezone.utc).isoformat()


def _open_store(root: Path) -> sqlite3.Connection:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("UNSAFE_MEMORY_ROOT")
    index = root / INDEX_NAME
    if index.is_symlink() or (index.exists() and not index.is_file()):
        raise ValueError("UNSAFE_MEMORY_INDEX")
    try:
        db = sqlite3.connect(str(index), timeout=5)
        db.execute(
            "CREATE TABLE IF NOT EXISTS memory_snapshots ("
            "cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL,"
            "payload_sha256 TEXT NOT NULL)"
        )
        db.commit()
    except sqlite3.Error as exc:
        raise ValueError("MEMORY_INDEX_UNAVAILABLE") from exc
    return db


def _create_snapshot(root: Path, features: dict, target: int, cutoff: str) -> dict:
    episodes = []
    graph_edges = []
    histogram = [0] * 10
    seen_sources = set()
    for contest in features["source_contests"]:
        if type(contest) is not int or contest <= 0 or contest >= target:
            raise ValueError("PIT_CONTEST_NOT_PRIOR")
        path = root / f"contest_{contest}.json"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("SOURCE_CHECKPOINT_UNAVAILABLE")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != features["source_sha256"].get(str(contest)):
            raise ValueError("SOURCE_CHANGED_DURING_MEMORY_BUILD")
        row = json.loads(raw)
        if not isinstance(row, dict) or str(row.get("contest_id")) != str(contest):
            raise ValueError("SOURCE_IDENTITY_INVALID")
        # The official historical consumer already applied the same PIT/source/
        # fingerprint/uniqueness filters to this exact source digest. Reject
        # duplicate videos here independently.
        source = row.get("source")
        if not isinstance(source, str) or source in seen_sources:
            raise ValueError("DUPLICATED_MEMORY_SOURCE")
        seen_sources.add(source)
        scope = row.get("analysis_scope")
        if not isinstance(scope, dict):
            raise ValueError("INVALID_MEMORY_SCOPE")
        lo, hi = float(scope["start_s"]), float(scope["end_s"])
        if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
            raise ValueError("INVALID_MEMORY_SCOPE")
        observed_at = _validated_cutoff(row.get("created_at_utc"))
        if observed_at > cutoff:
            raise ValueError("PIT_POST_CUTOFF_EPISODE")
        values = row.get("event_timestamps_s")
        if not isinstance(values, list) or len(values) > MAX_EPISODE_EVENTS:
            raise ValueError("UNBOUNDED_EPISODE")
        positions = []
        for value in values:
            moment = float(value)
            if not math.isfinite(moment) or not lo <= moment <= hi:
                raise ValueError("INVALID_OBSERVED_MOTION")
            position = round((moment - lo) / (hi - lo), 6)
            positions.append(position)
            histogram[min(9, int(position * 10))] += 1
        positions.sort()
        episodes.append({
            "contest_id": contest, "checkpoint_sha256": digest,
            "observed_at_utc": observed_at,
            "event_positions": positions, "motion_event_count": len(positions),
        })
        for i, position in enumerate(positions):
            graph_edges.append({
                "contest_id": contest, "event_ordinal": i,
                "normalized_position": position,
                "relationship": "OBSERVED_MOTION_ONLY",
            })
    episodes.sort(key=lambda item: item["contest_id"])
    return {
        "schema": SCHEMA, "target_contest": str(target), "as_of_utc": cutoff,
        "status": features["status"], "episodic": episodes,
        "semantic": {
            "observational_motion_histogram_10_bins": histogram,
            "observed_event_count": sum(histogram),
            "normalized_event_center": features["observational_features"]["normalized_event_center"],
            "observed_spread": features["observational_features"]["observed_spread"],
        },
        "graph": {
            "relationship": "OBSERVED_MOTION_ONLY",
            "episode_count": len(episodes), "edge_count": len(graph_edges),
            "edges": graph_edges,
        },
        "source_manifest_sha256": _digest(features["source_sha256"]),
        "predictive_weight": 0.0, "predictive_evidence": "NOT_ESTABLISHED",
        "source_gate": "BLOCKED", "model_execution_enabled": False,
    }



def _consistent_snapshot(payload: dict, features: dict, target: int) -> bool:
    """Cross-check cached episode, graph and semantic claims without a model."""
    episodes = payload.get("episodic")
    graph = payload.get("graph")
    semantic = payload.get("semantic")
    if not isinstance(episodes, list) or not isinstance(graph, dict) or not isinstance(semantic, dict):
        return False
    if payload.get("status") != features["status"]:
        return False
    if len(episodes) != len(features["source_contests"]):
        return False
    histogram = [0] * 10
    expected_graph = []
    observed_ids = []
    for episode in episodes:
        if not isinstance(episode, dict):
            return False
        contest = episode.get("contest_id")
        if type(contest) is not int or contest <= 0 or contest >= target:
            return False
        if episode.get("checkpoint_sha256") != features["source_sha256"].get(str(contest)):
            return False
        if _validated_cutoff(episode.get("observed_at_utc")) > features["as_of_utc"]:
            return False
        positions = episode.get("event_positions")
        if not isinstance(positions, list) or len(positions) > MAX_EPISODE_EVENTS:
            return False
        if episode.get("motion_event_count") != len(positions) or positions != sorted(positions):
            return False
        for i, position in enumerate(positions):
            if type(position) not in (float, int) or not math.isfinite(position) or not 0 <= position <= 1:
                return False
            histogram[min(9, int(position * 10))] += 1
            expected_graph.append({
                "contest_id": contest,
                "event_ordinal": i,
                "normalized_position": position,
                "relationship": "OBSERVED_MOTION_ONLY",
            })
        observed_ids.append(contest)
    if observed_ids != features["source_contests"]:
        return False
    return (
        semantic == {
            "observational_motion_histogram_10_bins": histogram,
            "observed_event_count": sum(histogram),
            "normalized_event_center": features["observational_features"]["normalized_event_center"],
            "observed_spread": features["observational_features"]["observed_spread"],
        }
        and graph == {
            "relationship": "OBSERVED_MOTION_ONLY",
            "episode_count": len(episodes), "edge_count": len(expected_graph),
            "edges": expected_graph,
        }
    )

def get_visual_learning_memory(
    target_contest: str, cutoff_utc: str,
    checkpoint_dir: str | Path = "runtime/video_observation",
    hypothesis_id: str | None = None, *,
    source_url: str | None = None,
) -> dict:
    """Read only earlier/fingerprint-checked source evidence; reuse sealed index."""
    target = str(target_contest)
    if not target.isascii() or not target.isdecimal() or int(target) <= 0:
        raise ValueError("INVALID_TARGET_CONTEST")
    cutoff = _validated_cutoff(cutoff_utc)
    root = Path(checkpoint_dir)
    if root.is_symlink():
        raise ValueError("UNSAFE_MEMORY_ROOT")
    if not root.is_dir():
        raise ValueError("MEMORY_SOURCE_DIRECTORY_MISSING")

    # Canonical existing consumer revalidates hashes and PIT *every call*,
    # including warm-cache reads and source content mutations.
    from smart_video_learning import get_visual_features
    features = get_visual_features(target, cutoff, root, hypothesis_id, source_url=source_url)
    manifest = {
        "contest": target, "cutoff": cutoff,
        "hypothesis_id": hypothesis_id, "source_url": source_url,
        "extractor": features["extractor_version"],
        "features_status": features["status"],
        "source_sha256": features["source_sha256"],
        "source_contests": features["source_contests"],
        "observational_features": features["observational_features"],
    }
    key = _digest(manifest)
    db = _open_store(root)
    try:
        saved = db.execute(
            "SELECT payload, payload_sha256 FROM memory_snapshots WHERE cache_key=?",
            (key,),
        ).fetchone()
        if saved and hashlib.sha256(saved[0].encode("utf-8")).hexdigest() == saved[1]:
            try:
                payload = json.loads(saved[0])
                if (isinstance(payload, dict) and payload.get("schema") == SCHEMA
                        and payload.get("target_contest") == target
                        and payload.get("as_of_utc") == cutoff
                        and payload.get("source_manifest_sha256") == _digest(features["source_sha256"])
                        and payload.get("provenance_sha256") == key
                        and payload.get("predictive_weight") == 0.0
                        and payload.get("source_gate") == "BLOCKED"
                        and payload.get("model_execution_enabled") is False):
                    # Verify exact episode identities/digests before cache reuse.
                    expected = {
                        int(n): sha for n, sha in features["source_sha256"].items()
                    }
                    cached = {
                        e["contest_id"]: e["checkpoint_sha256"]
                        for e in payload.get("episodic", [])
                    }
                    if (cached == expected
                            and all(type(n) is int and 0 < n < int(target) for n in cached)
                            and _consistent_snapshot(payload, features, int(target))):
                        return {**payload, "metrics": {
                            "schema": "SMART_VIDEO_MEMORY_INDEX_METRICS_V1",
                            "index_hit": True,
                            "episode_count": len(expected), "indexed_sources": len(expected),
                        }}
            except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
                pass

        payload = _create_snapshot(root, features, int(target), cutoff)
        payload["provenance_sha256"] = key
        serial = _canonical(payload)
        digest = hashlib.sha256(serial.encode("utf-8")).hexdigest()
        db.execute(
            "INSERT OR REPLACE INTO memory_snapshots(cache_key,payload,payload_sha256)"
            " VALUES (?,?,?)", (key, serial, digest),
        )
        db.commit()
        return {**payload, "metrics": {
            "schema": "SMART_VIDEO_MEMORY_INDEX_METRICS_V1",
            "index_hit": False,
            "episode_count": len(payload["episodic"]),
            "indexed_sources": len(payload["episodic"]),
        }}
    except sqlite3.Error as exc:
        raise ValueError("MEMORY_INDEX_IO_FAILURE") from exc
    finally:
        db.close()
