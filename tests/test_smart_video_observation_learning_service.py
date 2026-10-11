"""Standard-library regression tests for the incremental visual learning service."""
import json
import io
import sys
from contextlib import redirect_stdout
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import smart_video_observation as observation


def candidate(root, contest, created_at, *, source=None, wrong_digest=False):
    cfg = observation.ObservationConfig()
    url = source or f"https://example.org/video_{contest}.mp4"
    record = {
        "contest_id": str(contest), "source": url,
        "status": "CANDIDATE", "semantic_label": "MOTION_EVENT_CANDIDATE",
        "extractor_version": observation.EXTRACTOR_VERSION,
        "hypothesis_id": None, "predictive_evidence": observation.PREDICTIVE_EVIDENCE,
        "main_params": vars(cfg),
        "checkpoint_fingerprint": observation._observation_fingerprint(str(contest), url, cfg, None),
        "spatial_consensus": {"recurrent": True},
        "analysis_scope": {"start_s": 0, "end_s": 100, "segment_guard_passed": True},
        "event_timestamps_s": [40, 50, 60],
        "coverage_ratio": 0.35,
        "created_at_utc": created_at,
    }
    if wrong_digest:
        record["checkpoint_fingerprint"] = "tampered"
    (root / f"contest_{contest}.json").write_text(json.dumps(record), encoding="utf-8")


class VisualLearningServiceTests(unittest.TestCase):
    def test_consumer_enforces_cutoff_and_target_and_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            for c in (3000, 3001, 3002):
                candidate(p, c, "2026-10-09T00:00:00+00:00")
            candidate(p, 3003, "2026-10-09T00:00:00+00:00")
            candidate(p, 2999, "2026-10-12T00:00:00+00:00")
            candidate(p, 2998, "2026-10-09T00:00:00+00:00", wrong_digest=True)
            r = observation.get_visual_features(p, "3003", "2026-10-10T00:00:00Z")
            self.assertEqual(r["source_contests"], [3000, 3001, 3002])
            self.assertEqual(r["observation_count"], 3)
            self.assertEqual(r["status"], "OBSERVATIONAL_CONSENSUS")
            self.assertEqual(len(r["source_sha256"]), 3)
            self.assertFalse(r["predictive_weight_authorized"])
            self.assertEqual(r["predictive_weight"], 0.0)
            self.assertEqual(r["quality"]["eligible_event_count"], 9)

    def test_consumer_requires_aware_time(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                observation.get_visual_features(d, "3059", "2026-10-11T18:00:00")
            with self.assertRaises(ValueError):
                observation.get_visual_features(d, "not-a-contest", "2026-10-11T18:00:00Z")

    def test_empty_consumer_is_fail_closed_and_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            state = observation.get_visual_features(p, "3060", "2026-10-11T18:00:00Z")
            self.assertEqual(state["status"], "INSUFFICIENT_EVIDENCE")
            self.assertEqual(list(p.iterdir()), [])

    def test_batch_parallel_and_single_memory_consolidation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            lock = threading.Lock()
            running = [0]
            max_seen = [0]
            memory_calls = []
            def resolver(url, _timeout):
                with lock:
                    running[0] += 1
                    max_seen[0] = max(max_seen[0], running[0])
                time.sleep(0.035)
                with lock:
                    running[0] -= 1
                return {"source_url": url, "stream_url": url,
                        "video_id": url, "duration_s": 80, "format_id": "test",
                        "protocol": "https"}
            def sampler(spec, _timeout):
                s = float(spec["start_s"])
                if spec["duration_s"] < 3:
                    return {"status": "OK", "start_s": s,
                            "duration_s": spec["duration_s"],
                            "mean_motion": 0.03, "median_motion": 0.03,
                            "max_motion": 0.08, "grid_energy": [0.01] * 12,
                            "grid_energy_alt": [0.01] * 16,
                            "global_motion_fraction": 0.0}
                grid = [0.001] * 12
                grid[4] = 0.2
                alt = [0.001] * 16
                alt[5] = 0.2
                return {"status": "OK", "start_s": s,
                        "duration_s": spec["duration_s"],
                        "mean_motion": 0.05,
                        "motion_scores": [0.01, 0.02, 0.09, 0.01, 0.08, 0.01, 0.10],
                        "sample_times": [s + x * 0.6 for x in range(7)],
                        "grid_energy": grid, "grid_energy_alt": alt,
                        "global_motion_fraction": 0.0}
            def persist(root, target, hypothesis_id, **kwargs):
                memory_calls.append((str(target), kwargs))
                return {"sha256": "test-memory-sha"}
            items = [{"contest_id": str(x), "url": f"https://example.org/{x}.mp4"} for x in range(3040, 3044)]
            cfg = observation.ObservationConfig(coarse_points=4, max_refined_regions=1, workers=2)
            with mock.patch.object(observation, "persist_visual_learning_state", side_effect=persist):
                first = observation.observe_batch(items, p, cfg,
                    max_concurrent_contests=2, resolver=resolver, sampler=sampler)
                self.assertEqual(len(memory_calls), 1)
                self.assertEqual(max_seen[0], 2)
                self.assertEqual(first["total"], 4)
                self.assertEqual(first["memory_state"], "PERSISTED")
                self.assertTrue(all((p / f"contest_{x}.json").exists() for x in range(3040, 3044)))
                def prohibited(*args):
                    raise AssertionError("valid checkpoints must avoid replay")
                second = observation.observe_batch(items, p, cfg,
                    max_concurrent_contests=2, resolver=prohibited, sampler=sampler)
            self.assertEqual(second["checkpoint_reused"], 4)
            self.assertEqual(len(memory_calls), 2)

    def test_duplicate_manifest_fails_before_any_write(self):
        with tempfile.TemporaryDirectory() as d:
            items = [{"contest_id": "3050", "url": "https://example.org/a.mp4"},
                     {"contest_id": "3050", "url": "https://example.org/b.mp4"}]
            with self.assertRaisesRegex(ValueError, "duplicate"):
                observation.observe_batch(items, d)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_worker_error_is_isolated_and_memory_failure_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            def fail_resolver(url, timeout):
                raise RuntimeError("offline")
            result = observation.observe_batch(
                [{"contest_id": "3050", "url": "https://example.org/a.mp4"}],
                p, resolver=fail_resolver)
            self.assertEqual(result["status"], "PARTIAL")
            self.assertEqual(result["status_counts"], {"STREAM_FAILED": 1})
            self.assertEqual(result["memory_state"], "PERSISTED")
            self.assertEqual(result["predictive_evidence"], "NOT_ESTABLISHED")


    def test_consumer_cli_exports_reproducible_json_without_rewatch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for c in (3000, 3001, 3002):
                candidate(root, c, "2026-10-09T00:00:00+00:00")
            report = root / "derived_visual_features.json"
            argv = [
                "smart_video_observation.py", "--features-contest", "3003",
                "--cutoff-utc", "2026-10-10T00:00:00Z",
                "--checkpoint-dir", str(root), "--output-json", str(report),
            ]
            out = io.StringIO()
            with mock.patch.object(sys, "argv", argv), redirect_stdout(out):
                self.assertEqual(observation._main(), 0)
            printed = json.loads(out.getvalue())
            self.assertEqual(printed, json.loads(report.read_text(encoding="utf-8")))
            self.assertEqual(printed["source_contests"], [3000, 3001, 3002])
            self.assertEqual(printed["predictive_weight"], 0.0)
            self.assertTrue((root / "contest_3000.json").exists())

    def test_batch_cli_reuses_checkpoints_without_video_network(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for c in (3000, 3001, 3002):
                candidate(root, c, "2026-10-09T00:00:00+00:00")
            inputs = [{"contest_id": str(c), "url": f"https://example.org/video_{c}.mp4"} for c in (3000, 3001, 3002)]
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema": "SMART_VISUAL_BATCH_MANIFEST_V1",
                                            "next_contest": "3003", "items": inputs}), encoding="utf-8")
            snapshot = {c: (root / f"contest_{c}.json").read_bytes() for c in (3000, 3001, 3002)}
            report = root / "batch_report.json"
            argv = ["smart_video_observation.py", "--batch-manifest", str(manifest),
                    "--checkpoint-dir", str(root), "--output-json", str(report)]
            out = io.StringIO()
            with mock.patch.object(sys, "argv", argv), redirect_stdout(out):
                self.assertEqual(observation._main(), 0)
            data = json.loads(out.getvalue())
            self.assertEqual(data["checkpoint_reused"], 3)
            self.assertEqual(data["memory_state"], "PERSISTED")
            self.assertEqual(data["total"], 3)
            self.assertEqual(data, json.loads(report.read_text(encoding="utf-8")))
            for c, raw in snapshot.items():
                self.assertEqual(raw, (root / f"contest_{c}.json").read_bytes())
            self.assertTrue((root / "SMART_VISUAL_LEARNING_STATE.json").exists())

    def test_cli_refuses_to_overwrite_immutable_checkpoint_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            candidate(root, 3000, "2026-10-09T00:00:00+00:00")
            protected = root / "contest_3000.json"
            before = protected.read_bytes()
            argv = ["smart_video_observation.py", "--features-contest", "3001",
                    "--cutoff-utc", "2026-10-10T00:00:00Z",
                    "--checkpoint-dir", str(root), "--output-json", str(protected)]
            with mock.patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    observation._main()
            self.assertEqual(cm.exception.code, 2)
            self.assertEqual(before, protected.read_bytes())

    def test_invalid_manifest_does_not_trigger_observation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema": "wrong", "items": []}), encoding="utf-8")
            argv = ["smart_video_observation.py", "--batch-manifest", str(manifest),
                    "--checkpoint-dir", str(root)]
            with mock.patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    observation._main()
            self.assertEqual(cm.exception.code, 2)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["manifest.json"])


if __name__ == "__main__":
    unittest.main()
