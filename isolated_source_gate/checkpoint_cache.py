"""Persistent digest-verified checkpoint JSON cache. No media/network access.

Every lookup hashes current bytes before trusting cached JSON; PIT and identity
checks remain in the official consumer. SQLite is an optimization, not authority.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path


class CheckpointCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError("SYMLINK_CACHE_PATH")
        self.hits = 0
        self.misses = 0
        self.invalidations = 0
        self.reads = 0
        self._db = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.path), timeout=2)
            self._db.execute("CREATE TABLE IF NOT EXISTS checkpoint_cache (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload TEXT NOT NULL, payload_sha256 TEXT)")
            columns = {row[1] for row in self._db.execute("PRAGMA table_info(checkpoint_cache)")}
            if "payload_sha256" not in columns:
                self._db.execute("ALTER TABLE checkpoint_cache ADD COLUMN payload_sha256 TEXT")
            self._db.commit()
        except (sqlite3.Error, OSError):
            self.close()

    def read(self, path: Path) -> tuple[dict, str]:
        if path.is_symlink() or not path.is_file():
            raise ValueError("INVALID_CHECKPOINT_PATH")
        raw = path.read_bytes()
        self.reads += 1
        if len(raw) > 1024 * 1024:
            raise ValueError("CHECKPOINT_TOO_LARGE")
        digest = hashlib.sha256(raw).hexdigest()
        key = str(path.resolve())
        if self._db is not None:
            try:
                saved = self._db.execute("SELECT sha256,payload,payload_sha256 FROM checkpoint_cache WHERE name=?", (key,)).fetchone()
                # Legacy (unsigned) rows are never treated as trustworthy hits.
                if (saved and saved[0] == digest and saved[2] is not None
                        and hashlib.sha256(saved[1].encode("utf-8")).hexdigest() == saved[2]):
                    row = json.loads(saved[1])
                    if isinstance(row, dict):
                        self.hits += 1
                        return row, digest
                if saved:
                    self.invalidations += 1
            except (sqlite3.Error, ValueError, TypeError, json.JSONDecodeError):
                pass
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError("INVALID_CHECKPOINT_PAYLOAD")
        self.misses += 1
        if self._db is not None:
            try:
                encoded = json.dumps(row, separators=(",", ":"), ensure_ascii=False)
                payload_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                self._db.execute(
                    "INSERT OR REPLACE INTO checkpoint_cache(name,sha256,payload,payload_sha256)"
                    " VALUES(?,?,?,?)", (key, digest, encoded, payload_digest)
                )
                self._db.commit()
            except sqlite3.Error:
                pass
        return row, digest

    def metrics(self) -> dict:
        return {"schema": "SMART_VIDEO_CHECKPOINT_CACHE_V1", "hits": self.hits,
                "misses": self.misses, "invalidations": self.invalidations,
                "bytes_verified_reads": self.reads, "hash_verification": "EVERY_READ",
                "predictive_weight": 0.0}

    def close(self) -> None:
        if self._db is not None:
            try:
                self._db.close()
            finally:
                self._db = None
