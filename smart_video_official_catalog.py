"""Loss-resistant index of official CAIXA YouTube streams.

A broadcast listing is not a Mega-Sena observation. No lottery predictions,
winning numbers, video downloads or result-driven weights are generated here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

CHANNEL = "UCPbhr02AfVb2nd5pm12BxTw"
URL = "https://www.youtube.com/channel/" + CHANNEL + "/streams"
SCHEMA = "SMART_CAIXA_OFFICIAL_VIDEO_CATALOG_V1"
STATUSES = {"UNCONFIRMED_MEGA", "CONFIRMED_MEGA_METADATA", "AMBIGUOUS_MEGA_METADATA"}
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
MEGA = re.compile(
    r"mega[\s-]*sena\s*[:\-–|]?\s*(?:concurso\s*)?(?:n(?:[º°.o]|[úu]mero)?\s*)?(\d{3,5})\b",
    re.I,
)


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False).encode("utf-8")).hexdigest()


def encode(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def normalize(data: dict[str, Any], max_items: int = 500) -> list[dict[str, Any]]:
    if type(max_items) is not int or not 1 <= max_items <= 2500:
        raise ValueError("INVALID_ITEM_LIMIT")
    if not isinstance(data, dict) or data.get("channel_id", data.get("official_channel_id")) != CHANNEL:
        raise ValueError("OFFICIAL_CHANNEL_ID_MISMATCH")
    if data.get("source_url", URL) != URL:
        raise ValueError("OFFICIAL_CHANNEL_URL_MISMATCH")
    entries = data.get("entries", data.get("records"))
    if not isinstance(entries, list) or len(entries) > max_items:
        raise ValueError("BROADCAST_LIMIT_OR_FORMAT")
    result, seen = [], set()
    for row in entries:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not VIDEO_ID.fullmatch(row["id"]):
            raise ValueError("VIDEO_ID_INVALID")
        vid = row["id"]
        if vid in seen:
            raise ValueError("VIDEO_ID_DUPLICATE")
        seen.add(vid)
        if row.get("channel_id") not in (None, "", CHANNEL):
            raise ValueError("ROW_CHANNEL_MISMATCH")
        title = row.get("title") or ""
        if not isinstance(title, str) or len(title) > 300:
            raise ValueError("INVALID_TITLE")
        # Never trust arbitrary per-entry URL; derive from the validated ID.
        result.append({
            "id": vid, "title": title, "url": "https://www.youtube.com/watch?v=" + vid,
            "status": "UNCONFIRMED_MEGA", "mega_contest": None,
            "description_sha256": None, "video_analyzed": False,
        })
    return result


def verify(doc: dict[str, Any]) -> None:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or doc.get("channel_id") != CHANNEL:
        raise ValueError("CATALOG_SCHEMA_INVALID")
    c = dict(doc)
    sha = c.pop("sha256", None)
    if not isinstance(sha, str) or digest(c) != sha:
        raise ValueError("CATALOG_SHA_INVALID")
    if doc.get("predictive_weight") != 0.0 or doc.get("predictive_evidence") != "NOT_ESTABLISHED":
        raise ValueError("CATALOG_PREDICTION_UNSAFE")
    rows = doc.get("rows")
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError("CATALOG_ROWS_INVALID")
    ids = set()
    for row in rows:
        vid = row.get("id")
        if not isinstance(vid, str) or not VIDEO_ID.fullmatch(vid) or vid in ids:
            raise ValueError("CATALOG_DUPLICATE_OR_INVALID_ID")
        ids.add(vid)
        if row.get("url") != "https://www.youtube.com/watch?v=" + vid:
            raise ValueError("CATALOG_URL_INVALID")
        if row.get("status") not in STATUSES or row.get("video_analyzed") is not False:
            raise ValueError("CATALOG_STATUS_UNSAFE")


@contextmanager
def lock_catalog(root: Path):
    path = root / ".catalog.lock"
    if path.is_symlink():
        raise ValueError("CATALOG_LOCK_SYMLINK")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("CATALOG_BUSY") from exc
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def read_current(root: Path) -> dict[str, Any] | None:
    pointer = root / "SMART_CAIXA_CATALOG_CURRENT.json"
    if pointer.is_symlink():
        raise ValueError("CATALOG_POINTER_SYMLINK")
    if not pointer.exists():
        return None
    doc = json.loads(pointer.read_text(encoding="utf-8"))
    verify(doc)
    archive = root / "catalog_history" / (doc["sha256"] + ".json")
    if archive.is_symlink() or not archive.is_file() or archive.read_bytes() != encode(doc):
        raise ValueError("CATALOG_HISTORY_MISSING_OR_CORRUPT")
    return doc


def save(root: Path, body: dict[str, Any], prior: dict[str, Any] | None) -> dict[str, Any]:
    if prior and body["rows"] == prior["rows"]:
        return prior
    doc = dict(body)
    doc["sha256"] = digest(doc)
    verify(doc)
    history = root / "catalog_history"
    if history.is_symlink():
        raise ValueError("CATALOG_HISTORY_SYMLINK")
    history.mkdir(exist_ok=True)
    archived = history / (doc["sha256"] + ".json")
    if archived.is_symlink():
        raise ValueError("CATALOG_ARCHIVE_SYMLINK")
    data = encode(doc)
    if archived.exists():
        if archived.read_bytes() != data:
            raise ValueError("CATALOG_ARCHIVE_CONFLICT")
    else:
        try:
            with archived.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if archived.is_symlink() or archived.read_bytes() != data:
                raise ValueError("CATALOG_ARCHIVE_CONFLICT")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".catalog.", suffix=".tmp",
                                         mode="wb", delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, root / "SMART_CAIXA_CATALOG_CURRENT.json")
        tmp = None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return doc


def summary(doc: dict[str, Any], added: int, changed: bool) -> dict[str, Any]:
    return {
        "schema": "SMART_CAIXA_CATALOG_SUMMARY_V1",
        "channel_id": CHANNEL,
        "indexed": len(doc["rows"]),
        "new_broadcasts": added,
        "status_counts": {s: sum(x["status"] == s for x in doc["rows"]) for s in sorted(STATUSES)},
        "catalog_sha256": doc["sha256"],
        "changed": changed,
        "real_videos_analyzed": 0,
        "predictive_weight": 0.0,
    }


def ingest(data: dict[str, Any], root: str | Path, *, max_items: int = 500) -> dict[str, Any]:
    rows = normalize(data, max_items)
    target = Path(root)
    if target.is_symlink():
        raise ValueError("CATALOG_DIR_SYMLINK")
    target.mkdir(parents=True, exist_ok=True)
    with lock_catalog(target):
        prev = read_current(target)
        merged = [dict(x) for x in prev["rows"]] if prev else []
        found = {row["id"] for row in merged}
        added = 0
        for row in rows:
            if row["id"] not in found:
                merged.append(row)
                found.add(row["id"])
                added += 1
        body = {
            "schema": SCHEMA, "channel_id": CHANNEL, "source_url": URL,
            "rows": merged, "previous_sha256": prev["sha256"] if prev else None,
            "predictive_evidence": "NOT_ESTABLISHED", "predictive_weight": 0.0,
        }
        doc = save(target, body, prev)
        return summary(doc, added, prev is None or doc["sha256"] != prev["sha256"])


def enrich(details: list[dict[str, Any]], root: str | Path, *, max_items: int = 500) -> dict[str, Any]:
    """Validate multiple descriptions and commit one atomic revision."""
    if not isinstance(details, list) or len(details) > max_items or not details:
        raise ValueError("INVALID_METADATA_BATCH")
    target = Path(root)
    if target.is_symlink() or not target.is_dir():
        raise ValueError("CATALOG_NOT_INITIALIZED")
    with lock_catalog(target):
        prev = read_current(target)
        if not prev:
            raise ValueError("CATALOG_NOT_INITIALIZED")
        rows = [dict(r) for r in prev["rows"]]
        mapping = {x["id"]: x for x in rows}
        seen = set()
        for item in details:
            if not isinstance(item, dict) or item.get("channel_id") != CHANNEL:
                raise ValueError("VIDEO_OFFICIAL_CREATOR_UNVERIFIED")
            id_ = item.get("id")
            if id_ not in mapping or id_ in seen:
                raise ValueError("VIDEO_NOT_FOUND_OR_DUPLICATE")
            seen.add(id_)
            description = item.get("description")
            if not isinstance(description, str) or len(description) > 50000:
                raise ValueError("VIDEO_DESCRIPTION_UNAVAILABLE")
            nums = sorted(set(int(n) for n in MEGA.findall(description)))
            row = mapping[id_]
            row["description_sha256"] = hashlib.sha256(description.encode("utf-8")).hexdigest()
            row["status"] = ("CONFIRMED_MEGA_METADATA" if len(nums) == 1 else
                             "AMBIGUOUS_MEGA_METADATA" if len(nums) > 1 else "UNCONFIRMED_MEGA")
            row["mega_contest"] = str(nums[0]) if len(nums) == 1 else None
        body = {
            "schema": SCHEMA, "channel_id": CHANNEL, "source_url": URL,
            "rows": rows, "previous_sha256": prev["sha256"],
            "predictive_evidence": "NOT_ESTABLISHED", "predictive_weight": 0.0,
        }
        doc = save(target, body, prev)
        return summary(doc, 0, doc["sha256"] != prev["sha256"])


def discover(*, limit: int = 500, timeout: int = 170) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 2500:
        raise ValueError("INVALID_LIMIT")
    argv = [
        sys.executable, "-m", "yt_dlp", "--flat-playlist",
        "--playlist-end", str(limit), "--dump-single-json",
        "--skip-download", "--no-warnings", "--socket-timeout", "12",
        "--retries", "1", URL,
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode:
        raise RuntimeError("OFFICIAL_YOUTUBE_DISCOVERY_UNAVAILABLE")
    data = json.loads(proc.stdout)
    normalize(data, limit)
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Immutable official CAIXA broadcast catalog")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--flat-json")
    mode.add_argument("--discover-official", action="store_true")
    mode.add_argument("--details-json")
    parser.add_argument("--catalog-dir", default="runtime/video_official_catalog")
    parser.add_argument("--max-items", type=int, default=500)
    args = parser.parse_args(argv)
    if args.details_json:
        doc = json.loads(Path(args.details_json).read_text(encoding="utf-8"))
        result = enrich(doc, args.catalog_dir, max_items=args.max_items)
    else:
        original = (discover(limit=args.max_items) if args.discover_official else
                    json.loads(Path(args.flat_json).read_text(encoding="utf-8")))
        result = ingest(original, args.catalog_dir, max_items=args.max_items)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
