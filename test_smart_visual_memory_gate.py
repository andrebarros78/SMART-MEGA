"""PIT-checked, persistent M3/TaskMem-inspired observational memory gate."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from smart_video_observation import (
    ObservationConfig, EXTRACTOR_VERSION, PREDICTIVE_EVIDENCE,
    _observation_fingerprint,
)
from smart_video_learning import get_visual_learning_memory


class VisualMemoryGateTests(unittest.TestCase):
    def make_checkpoint(self, root, contest, *, observed="2026-10-10T12:00:00Z",
                        source=None, events=(30., 40., 50.)):
        cfg = ObservationConfig()
        url = source or f"https://example.org/{contest}.mp4"
        data = {
            "schema": "smart.video_observation.v1", "contest_id": str(contest),
            "source": url, "extractor_version": EXTRACTOR_VERSION,
            "predictive_evidence": PREDICTIVE_EVIDENCE, "hypothesis_id": None,
            "main_params": vars(cfg),
            "checkpoint_fingerprint": _observation_fingerprint(str(contest), url, cfg, None),
            "status": "CANDIDATE",
            "analysis_scope": {"start_s": 0., "end_s": 100., "segment_guard_passed": True},
            "spatial_consensus": {"recurrent": True},
            "event_timestamps_s": list(events),
            "created_at_utc": observed,
        }
        path = root / f"contest_{contest}.json"
        path.write_text(json.dumps(data))
        return path

    def test_memory_index_has_only_prior_observed_provenance_and_no_lottery_weights(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in (100, 101, 102, 103, 104):
                self.make_checkpoint(root, n)
            result = get_visual_learning_memory("103", "2026-10-11T00:00:00Z", root)
            self.assertEqual([e["contest_id"] for e in result["episodic"]], [100, 101, 102])
            self.assertEqual([e["event_positions"] for e in result["episodic"]],
                             [[.3, .4, .5]] * 3)
            self.assertEqual(result["semantic"]["observed_event_count"], 9)
            self.assertEqual(result["graph"]["episode_count"], 3)
            self.assertEqual(result["graph"]["edge_count"], 9)
            self.assertEqual(result["predictive_weight"], 0.0)
            self.assertEqual(result["source_gate"], "BLOCKED")
            self.assertEqual(result["predictive_evidence"], "NOT_ESTABLISHED")
            self.assertEqual(result["metrics"]["index_hit"], False)

    def test_persisted_snapshot_reused_across_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in (100, 101, 102):
                self.make_checkpoint(root, n)
            kwargs = ("103", "2026-10-11T00:00:00Z", root)
            first = get_visual_learning_memory(*kwargs)
            second = get_visual_learning_memory(*kwargs)
            self.assertFalse(first["metrics"]["index_hit"])
            self.assertTrue(second["metrics"]["index_hit"])
            self.assertEqual(first["provenance_sha256"], second["provenance_sha256"])
            self.assertEqual(first["semantic"], second["semantic"])
            self.assertTrue((root / ".visual_learning_memory.sqlite").is_file())

    def test_cache_invalidation_after_timestamp_mutation_and_pit_cutoff(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in (100, 101, 102):
                self.make_checkpoint(root, n)
            args = ("103", "2026-10-11T00:00:00Z", root)
            before = get_visual_learning_memory(*args)
            file = root / "contest_102.json"
            data = json.loads(file.read_text())
            data["created_at_utc"] = "2026-10-12T00:00:00Z"
            file.write_text(json.dumps(data))
            after = get_visual_learning_memory(*args)
            self.assertNotEqual(before["provenance_sha256"], after["provenance_sha256"])
            self.assertEqual([e["contest_id"] for e in after["episodic"]], [100, 101])
            self.assertFalse(after["metrics"]["index_hit"])

    def test_unsafe_or_future_source_never_enters_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in (100, 101):
                self.make_checkpoint(root, n)
            self.make_checkpoint(root, 102, source="https://other.example.net/movie.mp4")
            self.make_checkpoint(root, 103)
            output = get_visual_learning_memory("103", "2026-10-11T00:00:00Z", root,
                                                source_url="https://example.org/index.mp4")
            self.assertEqual([e["contest_id"] for e in output["episodic"]], [100, 101])

    def test_tampered_persistent_snapshot_must_not_be_used(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in (100, 101, 102):
                self.make_checkpoint(root, n)
            args = ("103", "2026-10-11T00:00:00Z", root)
            first = get_visual_learning_memory(*args)
            with sqlite3.connect(root / ".visual_learning_memory.sqlite") as db:
                db.execute("UPDATE memory_snapshots SET payload = ?", ('{"poisoned":true}',))
            second = get_visual_learning_memory(*args)
            self.assertEqual(len(second["episodic"]), 3)
            self.assertEqual(first["provenance_sha256"], second["provenance_sha256"])
            self.assertFalse(second["metrics"]["index_hit"])

    def test_forged_memory_summary_cannot_be_reused_even_with_matching_stored_digest(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in (100, 101, 102):
                self.make_checkpoint(root, n)
            args = ("103", "2026-10-11T00:00:00Z", root)
            first = get_visual_learning_memory(*args)
            with sqlite3.connect(root / ".visual_learning_memory.sqlite") as db:
                key, encoded = db.execute("SELECT cache_key,payload FROM memory_snapshots").fetchone()
                data = json.loads(encoded)
                data["semantic"]["observed_event_count"] = 1000
                forged = json.dumps(data)
                digest = hashlib.sha256(forged.encode()).hexdigest()
                db.execute("UPDATE memory_snapshots SET payload=?,payload_sha256=? WHERE cache_key=?",
                           (forged, digest, key))
            second = get_visual_learning_memory(*args)
            self.assertEqual(second["semantic"]["observed_event_count"], 9)
            self.assertEqual(first["provenance_sha256"], second["provenance_sha256"])
            self.assertFalse(second["metrics"]["index_hit"])

    def test_forged_consistent_episode_graph_cannot_override_source_bytes(self):
        # Attacker can recompute the *unkeyed* SQLite payload hash; the
        # checkpoint content SHA must remain authoritative on a warm hit.
        import hashlib
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for n in (100, 101, 102):
                self.make_checkpoint(root, n)
            args = ("103", "2026-10-11T00:00:00Z", root)
            initial = get_visual_learning_memory(*args)
            with sqlite3.connect(root / ".visual_learning_memory.sqlite") as db:
                key, encoded = db.execute(
                    "SELECT cache_key,payload FROM memory_snapshots"
                ).fetchone()
                doc = json.loads(encoded)
                doc["episodic"][0]["event_positions"] = [.1, .4, .5]
                doc["semantic"]["observational_motion_histogram_10_bins"] = [
                    0, 1, 0, 6, 2, 0, 0, 0, 0, 0,
                ]
                # Independently fix exact histogram from all forged episodes.
                bins = [0] * 10
                edges = []
                for episode in doc["episodic"]:
                    for i, position in enumerate(episode["event_positions"]):
                        bins[min(9, int(position * 10))] += 1
                        edges.append({
                            "contest_id": episode["contest_id"],
                            "event_ordinal": i,
                            "normalized_position": position,
                            "relationship": "OBSERVED_MOTION_ONLY",
                        })
                doc["semantic"]["observational_motion_histogram_10_bins"] = bins
                doc["graph"]["edges"] = edges
                encoded = json.dumps(doc, separators=(",", ":"))
                db.execute(
                    "UPDATE memory_snapshots SET payload=?,payload_sha256=? WHERE cache_key=?",
                    (encoded, hashlib.sha256(encoded.encode()).hexdigest(), key),
                )
            checked = get_visual_learning_memory(*args)
            self.assertFalse(checked["metrics"]["index_hit"])
            self.assertEqual(checked["episodic"], initial["episodic"])
            self.assertEqual(checked["graph"], initial["graph"])
            self.assertEqual(checked["semantic"], initial["semantic"])

    def test_forged_predictive_claim_is_rejected_even_when_rehashed(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in (100, 101, 102):
                self.make_checkpoint(root, n)
            args = ("103", "2026-10-11T00:00:00Z", root)
            get_visual_learning_memory(*args)
            with sqlite3.connect(root / ".visual_learning_memory.sqlite") as db:
                key, original = db.execute(
                    "SELECT cache_key,payload FROM memory_snapshots"
                ).fetchone()
                payload = json.loads(original)
                payload["predictive_evidence"] = "ESTABLISHED"
                forged = json.dumps(payload)
                db.execute(
                    "UPDATE memory_snapshots SET payload=?,payload_sha256=? WHERE cache_key=?",
                    (forged, hashlib.sha256(forged.encode()).hexdigest(), key),
                )
            verified = get_visual_learning_memory(*args)
            self.assertEqual(verified["predictive_evidence"], "NOT_ESTABLISHED")
            self.assertFalse(verified["metrics"]["index_hit"])

    def test_mutated_cached_episode_timestamp_is_not_reused(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in (100, 101, 102):
                self.make_checkpoint(root, n)
            args = ("103", "2026-10-11T00:00:00Z", root)
            get_visual_learning_memory(*args)
            with sqlite3.connect(root / ".visual_learning_memory.sqlite") as db:
                key, encoded = db.execute("SELECT cache_key,payload FROM memory_snapshots").fetchone()
                value = json.loads(encoded)
                value["episodic"][0]["observed_at_utc"] = "2026-10-12T00:00:00+00:00"
                tampered = json.dumps(value)
                db.execute("UPDATE memory_snapshots SET payload=?,payload_sha256=? WHERE cache_key=?",
                           (tampered, hashlib.sha256(tampered.encode()).hexdigest(), key))
            clean = get_visual_learning_memory(*args)
            self.assertFalse(clean["metrics"]["index_hit"])
            self.assertEqual(clean["episodic"][0]["observed_at_utc"],
                             "2026-10-10T12:00:00+00:00")

    def test_checkpoint_root_symlink_cannot_write_through_cache(self):
        from smart_video_observation import learned_motion_prior
        with tempfile.TemporaryDirectory() as temp:
            actual = Path(temp, "actual")
            actual.mkdir()
            self.make_checkpoint(actual, 100)
            linked = Path(temp, "linked")
            linked.symlink_to(actual, target_is_directory=True)
            result = learned_motion_prior(linked, "103",
                                          cutoff_utc="2026-10-11T00:00:00Z")
            self.assertEqual(result["training_contests"], [])
            self.assertFalse((actual / ".checkpoint_cache.sqlite").exists())

    def test_cli_memory_consumer_matches_python_api(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for n in (100, 101, 102):
                self.make_checkpoint(root, n)
            cmd = [
                sys.executable, str(Path(__file__).with_name("smart_video_learning.py")),
                "--target-contest", "103", "--cutoff-utc", "2026-10-11T00:00:00Z",
                "--checkpoint-dir", str(root), "--memory-readonly",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema"], "SMART_VISUAL_EVIDENCE_MEMORY_V1")
            self.assertEqual(payload["semantic"]["observed_event_count"], 9)
            self.assertEqual(payload["predictive_weight"], 0.0)

    def test_invalid_target_timestamp_or_symlink_store_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                get_visual_learning_memory("0", "2026-10-11T00:00:00Z", root)
            with self.assertRaises(ValueError):
                get_visual_learning_memory("103", "2026-10-11T00:00:00", root)
            destination = root / "other.sqlite"
            destination.write_bytes(b"")
            (root / ".visual_learning_memory.sqlite").symlink_to(destination)
            with self.assertRaises(ValueError):
                get_visual_learning_memory("103", "2026-10-11T00:00:00Z", root)


if __name__ == "__main__":
    unittest.main()
