import json
import tempfile
import unittest
from pathlib import Path
from isolated_source_gate.checkpoint_cache import CheckpointCache


class CacheTests(unittest.TestCase):
    def test_persistence_and_hash_invalidation(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root, "contest_100.json")
            db = Path(root, "cache.sqlite")
            file.write_text('{"contest_id":"100","created_at_utc":"2026-01-01T00:00:00Z"}')
            cache = CheckpointCache(db)
            first, digest1 = cache.read(file)
            assert cache.metrics()["misses"] == 1
            cache.close()
            cache = CheckpointCache(db)
            second, digest2 = cache.read(file)
            assert first == second and digest1 == digest2
            assert cache.metrics()["hits"] == 1
            file.write_text('{"contest_id":"100","created_at_utc":"2027-01-01T00:00:00Z"}')
            changed, digest3 = cache.read(file)
            assert digest3 != digest2 and changed["created_at_utc"].startswith("2027")
            assert cache.metrics()["invalidations"] == 1
            assert cache.metrics()["misses"] == 1
            assert cache.metrics()["predictive_weight"] == 0.0
            cache.close()

    def test_invalid_json_never_cached(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root, "contest_100.json")
            file.write_text("{")
            cache = CheckpointCache(Path(root, "cache.sqlite"))
            with self.assertRaises(json.JSONDecodeError):
                cache.read(file)
            assert cache.metrics()["hits"] == 0
            cache.close()

    def test_mutated_sqlite_payload_does_not_poison_observed_events(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as root:
            file = Path(root, "contest_100.json")
            db = Path(root, "cache.sqlite")
            file.write_text('{"contest_id":"100","event_timestamps_s":[30,40,50]}')
            cache = CheckpointCache(db)
            original, digest = cache.read(file)
            cache.close()
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE checkpoint_cache SET payload = ?",
                             ('{"contest_id":"100","event_timestamps_s":[1,2,3]}',))
            cache = CheckpointCache(db)
            row, checked_digest = cache.read(file)
            self.assertEqual(row, original)
            self.assertEqual(checked_digest, digest)
            self.assertEqual(cache.metrics()["hits"], 0)
            self.assertEqual(cache.metrics()["invalidations"], 1)
            cache.close()

    def test_old_cache_schema_upgrades_without_trusting_unsigned_rows(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as root:
            file = Path(root, "contest_100.json")
            file.write_text('{"contest_id":"100","event_timestamps_s":[30,40,50]}')
            db = Path(root, "legacy.sqlite")
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "CREATE TABLE checkpoint_cache (name TEXT PRIMARY KEY,"
                    "sha256 TEXT NOT NULL,payload TEXT NOT NULL)"
                )
            cache = CheckpointCache(db)
            first, _ = cache.read(file)
            self.assertEqual(first["event_timestamps_s"], [30,40,50])
            self.assertEqual(cache.metrics()["misses"], 1)
            second, _ = cache.read(file)
            self.assertEqual(second, first)
            self.assertEqual(cache.metrics()["hits"], 1)
            cache.close()

    def test_symlinked_cache_database_denied(self):
        with tempfile.TemporaryDirectory() as root:
            real = Path(root, "foreign.sqlite")
            real.write_bytes(b"")
            pointer = Path(root, "cache.sqlite")
            pointer.symlink_to(real)
            with self.assertRaisesRegex(ValueError, "SYMLINK"):
                CheckpointCache(pointer)

    def test_symlink_denied(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root, "contest_100.json")
            file.write_text("{}")
            link = Path(root, "contest_101.json")
            link.symlink_to(file)
            cache = CheckpointCache(Path(root, "cache.sqlite"))
            with self.assertRaises(ValueError):
                cache.read(link)
            cache.close()


if __name__ == "__main__":
    unittest.main()
