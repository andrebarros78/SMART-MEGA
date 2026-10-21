"""B2 physical checkpoint gate: no source mutation or asserted predictive value."""
import json
import tempfile
import unittest
from pathlib import Path

from test_smart_visual_memory_gate import VisualMemoryGateTests

from smart_b2_physical_learning_gate import audit_b2_physical_learning


class B2PhysicalLearningGateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = VisualMemoryGateTests()

    def test_missing_physical_source_is_blocked_not_reported_as_zero_observations(self):
        with tempfile.TemporaryDirectory() as parent:
            result = audit_b2_physical_learning(
                Path(parent) / "missing", "103", "2026-10-11T00:00:00Z",
                expected_count=3,
            )
        self.assertEqual(result["status"], "PHYSICAL_SOURCE_UNAVAILABLE")
        self.assertEqual(result["physical_files_read"], 0)
        self.assertIsNone(result["observational_utility"])
        self.assertEqual(result["predictive_weight"], 0.0)
        self.assertFalse(result["pit_independently_attested"])

    def test_physical_snapshot_is_read_only_and_exposes_true_observational_counts(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent, "b2")
            root.mkdir()
            for contest in (100, 101, 102):
                self.fixture.make_checkpoint(root, contest)
            original = {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                        for p in root.iterdir()}
            result = audit_b2_physical_learning(
                root, "103", "2026-10-11T00:00:00Z", expected_count=3,
            )
            self.assertEqual(result["status"], "OBSERVATIONAL_SHADOW_ONLY")
            self.assertEqual(result["physical_files_read"], 3)
            self.assertEqual(result["file_integrity"]["valid_count"], 3)
            self.assertEqual(result["observational_utility"]["eligible_episodes"], 3)
            self.assertEqual(result["observational_utility"]["observed_motion_events"], 9)
            self.assertEqual(result["observational_utility"]["graph_edges"], 9)
            self.assertEqual(result["temporal_provenance"]["self_reported_pre_cutoff"], 3)
            self.assertEqual(result["temporal_provenance"]["independently_attested"], 0)
            self.assertIsNone(result["measured_predictive_gain"])
            self.assertFalse(result["pit_independently_attested"])
            self.assertEqual(original, {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                                        for p in root.iterdir()})
            self.assertFalse((root / ".checkpoint_cache.sqlite").exists())
            self.assertFalse((root / ".visual_learning_memory.sqlite").exists())
            self.assertEqual(result["predictive_weight"], 0.0)

    def test_motion_episodes_without_decoder_counters_are_unverified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for n in (100, 101, 102):
                self.fixture.make_checkpoint(root, n)
            result = audit_b2_physical_learning(
                root, "103", "2026-10-11T00:00:00Z", expected_count=3
            )
            q = result["observational_utility"]["decoder_quality"]
            self.assertEqual(q["candidate_episodes"], 3)
            self.assertEqual(q["with_consistent_decoder_counters"], 0)
            self.assertEqual(q["without_decoder_counters"], 3)
            self.assertEqual(q["invalid_decoder_counters"], 0)
            self.assertEqual(q["motion_events_with_decoder_counter_support"], 0)
            self.assertEqual(q["candidate_counter_coverage_ratio"], 0.0)
            self.assertEqual(q["motion_event_counter_coverage_ratio"], 0.0)
            self.assertIsNone(q["independently_verified_decoded_frames"])
            self.assertEqual(q["basis"], "UNTRUSTED_CHECKPOINT_COUNTERS_ONLY")
            self.assertEqual(result["predictive_weight"], 0.0)

    def test_frame_counter_coverage_counts_only_consistent_coarse_and_refined_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for n in (100, 101, 102):
                cp = self.fixture.make_checkpoint(root, n)
                if n != 102:
                    data = json.loads(cp.read_text())
                    data["coarse"] = [{"status": "OK", "read_frames": 20, "analyzed_frames": 11}]
                    data["analyzed_windows"] = [{"status": "OK", "read_frames": 30, "analyzed_frames": 13}]
                    cp.write_text(json.dumps(data))
                else:
                    data = json.loads(cp.read_text())
                    data["coarse"] = [{"status": "OK", "read_frames": 0, "analyzed_frames": 10}]
                    data["analyzed_windows"] = [{"status": "OK", "read_frames": 24, "analyzed_frames": 16}]
                    cp.write_text(json.dumps(data))
            result = audit_b2_physical_learning(
                root, "103", "2026-10-11T00:00:00Z", expected_count=3
            )
            q = result["observational_utility"]["decoder_quality"]
            self.assertEqual(q["candidate_episodes"], 3)
            self.assertEqual(q["with_consistent_decoder_counters"], 2)
            self.assertEqual(q["invalid_decoder_counters"], 1)
            self.assertEqual(q["motion_events_with_decoder_counter_support"], 6)
            self.assertEqual(q["candidate_counter_coverage_ratio"], 0.666667)
            self.assertEqual(q["motion_event_counter_coverage_ratio"], 0.666667)
            self.assertEqual(q["reported_frames_read_in_supported_episodes"], 100)
            self.assertFalse(q["frame_content_authenticity_established"])

    def test_fake_boolean_and_oversized_frame_counters_never_support_events(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for n in (100, 101):
                cp = self.fixture.make_checkpoint(root, n)
                data = json.loads(cp.read_text())
                data["coarse"] = [{
                    "status": "OK", "read_frames": True if n == 100 else 10_000_000,
                    "analyzed_frames": 5,
                }]
                data["analyzed_windows"] = [{
                    "status": "OK", "read_frames": 20, "analyzed_frames": 10,
                }]
                cp.write_text(json.dumps(data))
            result = audit_b2_physical_learning(
                root, "103", "2026-10-11T00:00:00Z", expected_count=2,
            )
            q = result["observational_utility"]["decoder_quality"]
            self.assertEqual(q["with_consistent_decoder_counters"], 0)
            self.assertEqual(q["invalid_decoder_counters"], 2)
            self.assertEqual(q["reported_frames_read_in_supported_episodes"], 0)
            self.assertEqual(q["motion_events_with_decoder_counter_support"], 0)

    def test_future_checkpoint_is_not_counted_in_frame_quality(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for n in (100, 101, 102):
                cp = self.fixture.make_checkpoint(root, n)
                data = json.loads(cp.read_text())
                data["coarse"] = [{"status": "OK", "read_frames": 20, "analyzed_frames": 8}]
                data["analyzed_windows"] = [{"status": "OK", "read_frames": 18, "analyzed_frames": 7}]
                if n == 102:
                    data["created_at_utc"] = "2026-10-12T00:00:00Z"
                cp.write_text(json.dumps(data))
            result = audit_b2_physical_learning(
                root, "103", "2026-10-11T00:00:00Z", expected_count=3
            )
            q = result["observational_utility"]["decoder_quality"]
            self.assertEqual(q["candidate_episodes"], 2)
            self.assertEqual(q["with_consistent_decoder_counters"], 2)
            self.assertEqual(q["motion_events_with_decoder_counter_support"], 6)
            self.assertFalse(result["pit_independently_attested"])

    def test_future_dated_checkpoint_is_excluded_not_cloaked_as_pit(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent, "b2")
            root.mkdir()
            for contest in (100, 101, 102):
                self.fixture.make_checkpoint(root, contest)
            target = root / "contest_102.json"
            changed = json.loads(target.read_text())
            changed["created_at_utc"] = "2026-10-12T00:00:00Z"
            target.write_text(json.dumps(changed))
            result = audit_b2_physical_learning(
                root, "103", "2026-10-11T00:00:00Z", expected_count=3,
            )
            self.assertEqual(result["temporal_provenance"]["self_reported_post_cutoff"], 1)
            self.assertEqual(result["observational_utility"]["eligible_episodes"], 2)
            self.assertEqual(result["observational_utility"]["observed_motion_events"], 6)
            self.assertEqual(result["predictive_evidence"], "NOT_ESTABLISHED")

    def test_result_label_leakage_fails_gate_closed(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent, "b2")
            root.mkdir()
            for contest in (100, 101, 102):
                self.fixture.make_checkpoint(root, contest)
            path = root / "contest_101.json"
            row = json.loads(path.read_text())
            row["winning_numbers"] = [1, 2, 3, 4, 5, 6]
            path.write_text(json.dumps(row))
            result = audit_b2_physical_learning(
                root, "103", "2026-10-11T00:00:00Z", expected_count=3,
            )
            self.assertEqual(result["status"], "PHYSICAL_INTEGRITY_REJECTED")
            self.assertIsNone(result["observational_utility"])
            self.assertEqual(result["file_integrity"]["invalid_count"], 1)

    def test_thirteen_fixture_checkpoints_accounted_for_exactly(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent, "b2")
            root.mkdir()
            for contest in range(100, 113):
                self.fixture.make_checkpoint(root, contest)
            result = audit_b2_physical_learning(
                root, "113", "2026-10-11T00:00:00Z", expected_count=13,
            )
            self.assertEqual(result["physical_files_read"], 13)
            self.assertEqual(result["observational_utility"]["eligible_episodes"], 13)
            self.assertEqual(result["observational_utility"]["observed_motion_events"], 39)
            self.assertEqual(
                result["observational_utility"]["decoder_quality"]["motion_events_with_decoder_counter_support"],
                0,
            )
            self.assertEqual(
                result["observational_utility"]["decoder_quality"]["candidate_counter_coverage_ratio"],
                0.0,
            )
            self.assertEqual(result["temporal_provenance"]["independently_attested"], 0)
            self.assertEqual(result["predictive_weight"], 0.0)

    def test_explicit_synthetic_only_b2_directories_are_quarantined(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "SMART-MEGA-VISUAL-INVENTORY-20261013" / "SYNTHETIC_ONLY_13"
            root.mkdir(parents=True)
            self.fixture.make_checkpoint(root, 100)
            result = audit_b2_physical_learning(
                root, "101", "2026-10-11T00:00:00Z", expected_count=1,
            )
            self.assertEqual(result["status"], "SYNTHETIC_SOURCE_QUARANTINED")
            self.assertEqual(result["physical_files_read"], 0)
            self.assertIsNone(result["observational_utility"])
            self.assertEqual(result["predictive_weight"], 0.0)

    def test_synthetic_only_official_queue_is_not_official_physical_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "SYNTHETIC_ONLY_OFFICIAL_QUEUE_13" / "checkpoints"
            root.mkdir(parents=True)
            self.fixture.make_checkpoint(root, 100)
            result = audit_b2_physical_learning(
                root, "101", "2026-10-11T00:00:00Z", expected_count=1,
            )
            self.assertEqual(result["status"], "SYNTHETIC_SOURCE_QUARANTINED")
            self.assertFalse(result["pit_independently_attested"])
            self.assertIsNone(result["measured_predictive_gain"])

    def test_windows_backslash_synthetic_only_path_is_also_quarantined(self):
        root = r"C:\ProgramData\B2-Learning-Work\SMART-MEGA-VISUAL-INVENTORY-20261013\SYNTHETIC_ONLY_OFFICIAL_QUEUE_13\checkpoints"
        output = audit_b2_physical_learning(
            root, "92014", "2026-10-11T00:00:00Z", expected_count=13,
        )
        self.assertEqual(output["status"], "SYNTHETIC_SOURCE_QUARANTINED")
        self.assertEqual(output["source_classification"], "SYNTHETIC_FIXTURE")
        self.assertIsNone(output["observational_utility"])

    def test_wrong_expected_count_does_not_invent_13_files(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent, "b2")
            root.mkdir()
            self.fixture.make_checkpoint(root, 100)
            result = audit_b2_physical_learning(
                root, "103", "2026-10-11T00:00:00Z", expected_count=13,
            )
            self.assertEqual(result["status"], "PHYSICAL_COUNT_NOT_VERIFIED")
            self.assertEqual(result["physical_files_read"], 1)
            self.assertIsNone(result["observational_utility"])

    def test_invalid_target_and_naive_cutoff_rejected(self):
        with tempfile.TemporaryDirectory() as parent:
            for args in (("0", "2026-10-11T00:00:00Z"),
                         ("103", "2026-10-11T00:00:00"),
                         ("bad", "2026-10-11T00:00:00Z")):
                with self.assertRaises(ValueError):
                    audit_b2_physical_learning(parent, *args)

    def test_symlinked_physical_root_is_not_treated_as_attested_source(self):
        with tempfile.TemporaryDirectory() as parent:
            real = Path(parent, "real")
            real.mkdir()
            link = Path(parent, "linked")
            link.symlink_to(real, target_is_directory=True)
            output = audit_b2_physical_learning(
                link, "103", "2026-10-11T00:00:00Z", expected_count=3,
            )
            self.assertEqual(output["status"], "PHYSICAL_SOURCE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
