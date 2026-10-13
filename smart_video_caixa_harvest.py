"""Bounded, restart-safe CAIXA public video metadata harvesting.

Only metadata whose source video ID and official channel are verified is cached.
Video frames are never downloaded. Negative retries are persisted separately.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from smart_video_official_catalog import CHANNEL, enrich, read_current

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
MARKER = re.compile(r"ytInitialPlayerResponse\s*=\s*")


def _hash(d: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _encode(d: dict[str, Any]) -> bytes:
    return (json.dumps(d, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _valid(details: Any, vid: str) -> dict[str, str]:
    if not isinstance(details, dict) or details.get("id") != vid or details.get("channel_id") != CHANNEL:
        raise ValueError("VIDEO_CREATOR_OR_ID_MISMATCH")
    text = details.get("description")
    if not isinstance(text, str) or len(text) > 50000:
        raise ValueError("PUBLIC_DESCRIPTION_UNAVAILABLE")
    return {"id": vid, "channel_id": CHANNEL, "description": text}


def fetch_public(vid: str, *, timeout: int = 12) -> dict[str, str]:
    req = urllib.request.Request(
        "https://www.youtube.com/watch?v=" + vid,
        headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        if res.status != 200:
            raise RuntimeError("YOUTUBE_HTTP_NOT_OK")
        body = res.read(2_000_001)
        if len(body) > 2_000_000:
            raise RuntimeError("YOUTUBE_HTML_TOO_LARGE")
    match = MARKER.search(body.decode("utf-8", errors="replace"))
    if match is None:
        raise RuntimeError("YOUTUBE_METADATA_MISSING")
    raw = body.decode("utf-8", errors="replace")
    player, _ = json.JSONDecoder().raw_decode(raw[match.end():])
    if (player.get("playabilityStatus") or {}).get("status") != "OK":
        raise RuntimeError("YOUTUBE_PUBLIC_ACCESS_UNAVAILABLE")
    vd = player.get("videoDetails") or {}
    return _valid({"id": vd.get("videoId"), "channel_id": vd.get("channelId"),
                   "description": vd.get("shortDescription")}, vid)


def cached_read(path: Path, vid: str) -> dict[str, str]:
    if path.is_symlink():
        raise ValueError("YOUTUBE_CACHE_SYMLINK")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != "SMART_CAIXA_PUBLIC_META_V1" or doc.get("sha256") != _hash({
        key: value for key, value in doc.items() if key != "sha256"
    }):
        raise ValueError("YOUTUBE_CACHE_INTEGRITY_FAIL")
    return _valid(doc, vid)


def cached_store(cache: Path, details: dict[str, Any], vid: str) -> dict[str, str]:
    checked = _valid(details, vid)  # MUST validate before writing even one byte.
    doc = {"schema": "SMART_CAIXA_PUBLIC_META_V1", **checked}
    doc["sha256"] = _hash(doc)
    path = cache / (vid + ".json")
    if path.is_symlink():
        raise ValueError("YOUTUBE_CACHE_SYMLINK")
    if path.exists():
        return cached_read(path, vid)
    try:
        with path.open("xb") as file:
            file.write(_encode(doc))
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError:
        return cached_read(path, vid)
    return checked


def cooldown_active(path: Path, vid: str) -> bool:
    if path.is_symlink():
        raise ValueError("YOUTUBE_RETRY_SYMLINK")
    if not path.is_file():
        return False
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("id") != vid or doc.get("sha256") != _hash({
        key: value for key, value in doc.items() if key != "sha256"
    }):
        raise ValueError("YOUTUBE_RETRY_TAMPERED")
    return datetime.fromisoformat(doc["retry_after_utc"]) > datetime.now(timezone.utc)


def failed_store(root: Path, vid: str, error: str, cooldown: int) -> None:
    doc = {"schema": "SMART_CAIXA_RETRY_V1", "id": vid,
           "error_type": error[:80],
           "retry_after_utc": (datetime.now(timezone.utc) + timedelta(seconds=cooldown)).isoformat()}
    doc["sha256"] = _hash(doc)
    tmp = root / ("." + vid + "." + str(os.getpid()) + ".tmp")
    with tmp.open("xb") as f:
        f.write(_encode(doc))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, root / (vid + ".json"))


def harvest(catalog_dir: str | Path, *, offset: int = 0, take: int = 50,
            workers: int = 4, cooldown: int = 3600) -> dict[str, Any]:
    if (type(offset) is not int or offset < 0 or type(take) is not int or
            not 1 <= take <= 100 or type(workers) is not int or not 1 <= workers <= 6 or
            type(cooldown) is not int or not 60 <= cooldown <= 86400):
        raise ValueError("HARVEST_BOUNDS_INVALID")
    root = Path(catalog_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("CATALOG_NOT_INSTALLED")
    original = read_current(root)
    if original is None:
        raise ValueError("CATALOG_NOT_INSTALLED")
    selected = original["rows"][offset:offset + take]
    cache, errors = root / "youtube_metadata", root / "metadata_retry"
    if cache.is_symlink() or errors.is_symlink():
        raise ValueError("CACHE_ROOT_SYMLINK")
    cache.mkdir(exist_ok=True)
    errors.mkdir(exist_ok=True)
    descriptions, pending = [], []
    reused = skipped = 0
    for row in selected:
        vid = row["id"]
        path = cache / (vid + ".json")
        if path.is_symlink():
            raise ValueError("CACHE_SYMLINK")
        if path.is_file():
            descriptions.append(cached_read(path, vid))
            reused += 1
        elif cooldown_active(errors / (vid + ".json"), vid):
            skipped += 1
        else:
            pending.append(vid)
    good, bad = [], {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(fetch_public, vid): vid for vid in pending}
        for future in as_completed(tasks):
            vid = tasks[future]
            try:
                good.append(cached_store(cache, future.result(), vid))
            except Exception as exc:
                bad[vid] = type(exc).__name__
                failed_store(errors, vid, type(exc).__name__, cooldown)
    descriptions.extend(good)
    updated = enrich(descriptions, root, max_items=max(1, len(descriptions))) if descriptions else None
    return {
        "schema": "SMART_CAIXA_PUBLIC_METADATA_HARVEST_V1",
        "offset": offset, "requested": len(selected), "new_verified": len(good),
        "cache_reused": reused, "failed": len(bad), "cooldown_skipped": skipped,
        "confirmed_mega_count": updated["status_counts"]["CONFIRMED_MEGA_METADATA"] if updated
            else sum(r["status"] == "CONFIRMED_MEGA_METADATA" for r in original["rows"]),
        "catalog_sha256": updated["catalog_sha256"] if updated else original["sha256"],
        "video_frames_analyzed": 0, "predictive_weight": 0.0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Checkpointed public CAIXA metadata acquisition")
    p.add_argument("--catalog-dir", default="runtime/video_official_catalog")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--take", type=int, default=50)
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    print(json.dumps(harvest(a.catalog_dir, offset=a.offset, take=a.take,
                             workers=a.workers), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
