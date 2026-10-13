"""Official YouTube Data API v3 metadata batches for already cataloged CAIXA videos.

No credentials in URLs or disk. Queries only IDs in the official catalog.
Videos missing from the official API are not labeled as Mega-Sena. This module
does not download media, read outcomes, or authorize predictive weights.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from smart_video_official_catalog import CHANNEL, enrich, read_current
from smart_video_caixa_harvest import cached_read, cached_store, failed_store, cooldown_active

API_URL = "https://www.googleapis.com/youtube/v3/videos"
API_ENV = "SMART_MEGA_YOUTUBE_API_KEY"
VID_RE = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def _query(ids: list[str], api_key: str, *, timeout: int = 22) -> dict[str, Any]:
    if not ids or len(ids) > 50 or len(set(ids)) != len(ids) or any(
            not isinstance(v, str) or not VID_RE.fullmatch(v) for v in ids):
        raise ValueError("INVALID_API_BATCH")
    if not api_key or len(api_key) > 1024:
        raise ValueError("YOUTUBE_API_KEY_NOT_CONFIGURED")
    url = API_URL + "?" + urllib.parse.urlencode({
        "part": "snippet", "id": ",".join(ids),
        "fields": "items(id,snippet(channelId,description))",
    })
    req = urllib.request.Request(
        url, headers={"x-goog-api-key": api_key, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError("YOUTUBE_API_NON_200")
            raw = response.read(2_000_001)
    except urllib.error.HTTPError as exc:
        # Never disclose response body, request headers or key.
        raise RuntimeError("YOUTUBE_API_HTTP_" + str(exc.code)) from None
    if len(raw) > 2_000_000:
        raise ValueError("YOUTUBE_API_RESPONSE_TOO_LARGE")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("YOUTUBE_API_RESPONSE_INVALID")
    return payload


def normalize_items(requested: list[str], response: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    wanted = set(requested)
    if not isinstance(response, dict) or not isinstance(response.get("items"), list):
        raise ValueError("INVALID_API_RESPONSE")
    accepted, seen = [], set()
    for video in response["items"]:
        if not isinstance(video, dict):
            raise ValueError("INVALID_VIDEO_RESOURCE")
        vid = video.get("id")
        if vid not in wanted or vid in seen:
            raise ValueError("UNREQUESTED_OR_DUPLICATE_VIDEO")
        seen.add(vid)
        snippet = video.get("snippet")
        if not isinstance(snippet, dict):
            raise ValueError("INVALID_VIDEO_SNIPPET")
        if snippet.get("channelId") != CHANNEL:
            raise ValueError("VIDEO_CREATOR_NOT_CAIXA")
        desc = snippet.get("description")
        if not isinstance(desc, str) or len(desc) > 50000:
            raise ValueError("VIDEO_DESCRIPTION_UNAVAILABLE")
        accepted.append({"id": vid, "channel_id": CHANNEL, "description": desc})
    missing = [vid for vid in requested if vid not in seen]
    return accepted, missing


def hydrate_api(catalog_dir: str | Path, *, limit: int = 500,
                batch_size: int = 50,
                api_key: str | None = None,
                query: Callable[..., dict[str, Any]] = _query) -> dict[str, Any]:
    if (type(limit) is not int or not 1 <= limit <= 2000 or
            type(batch_size) is not int or not 1 <= batch_size <= 50):
        raise ValueError("API_BATCH_LIMIT_INVALID")
    root = Path(catalog_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("CATALOG_NOT_INSTALLED")
    doc = read_current(root)
    if doc is None:
        raise ValueError("CATALOG_NOT_INSTALLED")
    key = api_key if api_key is not None else os.environ.get(API_ENV)
    if not key:
        raise ValueError("YOUTUBE_API_KEY_NOT_CONFIGURED")
    cached = root / "youtube_metadata"
    errors = root / "metadata_retry"
    if cached.is_symlink() or errors.is_symlink():
        raise ValueError("API_CACHE_SYMLINK")
    cached.mkdir(exist_ok=True)
    errors.mkdir(exist_ok=True)
    todo, records = [], []
    cache_hits = 0
    for row in doc["rows"]:
        if len(todo) + cache_hits >= limit:
            break
        vid = row["id"]
        p = cached / (vid + ".json")
        if p.is_symlink():
            raise ValueError("CACHE_PATH_SYMLINK")
        if p.is_file():
            records.append(cached_read(p, vid))
            cache_hits += 1
        else:
            # API is governed by its own project quotas; skip a globally blocked
            # website but respect per-video HTTP cooldown where applicable.
            if not cooldown_active(errors / (vid + ".json"), vid):
                todo.append(vid)
    batches, got, missing_total = 0, 0, 0
    for i in range(0, len(todo), batch_size):
        batch = todo[i:i + batch_size]
        response = query(batch, key)
        details, missing = normalize_items(batch, response)
        # All results must pass official channel/id validation before writes.
        for item in details:
            records.append(cached_store(cached, item, item["id"]))
        got += len(details)
        missing_total += len(missing)
        batches += 1
        if details:
            # One immutable snapshot per batch; already-validated cache makes
            # crash/retry idempotent and avoids repeating successful API calls.
            enrich(details, root, max_items=len(details))
        for vid in missing:
            failed_store(errors, vid, "YOUTUBE_DATA_API_VIDEO_NOT_RETURNED", 86400)
    return {
        "schema": "SMART_CAIXA_DATA_API_INGEST_V1",
        "requested_from_api": len(todo),
        "api_requests": batches,
        "batch_size": batch_size,
        "new_verified_metadata": got,
        "cached_reused": cache_hits,
        "missing_video_resources": missing_total,
        "catalog_sha256": read_current(root)["sha256"],
        "video_frames_analyzed": 0,
        "predictive_weight": 0.0,
        "api_key_exposed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Official YouTube Data API CAIXA batch metadata")
    p.add_argument("--catalog-dir", default="runtime/video_official_catalog")
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--batch-size", type=int, default=50)
    a = p.parse_args()
    print(json.dumps(hydrate_api(a.catalog_dir, limit=a.limit, batch_size=a.batch_size),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
