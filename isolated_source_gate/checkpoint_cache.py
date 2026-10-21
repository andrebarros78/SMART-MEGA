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
        self.hits = 0
        self.misses = 0
        self.invalidations = 0
        self.reads = 0
        self._db = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.path), timeout=2)
            self._db.execute("CREATE TABLE IF NOT EXISTS checkpoint_cache (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload TEXT NOT NULL)")
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
                saved = self._db.execute("SELECT sha256,payload FROM checkpoint_cache WHERE name=?", (key,)).fetchone()
                if saved and saved[0] == digest:
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
                self._db.execute("INSERT OR REPLACE INTO checkpoint_cache(name,sha256,payload) VALUES(?,?,?)", (key, digest, json.dumps(row, separators=(",", ":"))))
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
