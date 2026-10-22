"""Memory learning must be consumed by official batch, never predictive."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from smart_video_learning import observe_batch
import test_smart_visual_memory_gate as memory_fixtures


class BatchMemoryIntegration(unittest.TestCase):
    def test_official_batch_returns_verified_observational_memory_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixtures = memory_fixtures.VisualMemoryGateTests()
            fixtures.make_checkpoint(root, 100)
            fixtures.make_checkpoint(root, 101)
            with (patch("smart_video_learning.analyze_contest",
                        return_value={"contest_id": "102", "status": "CANDIDATE", "checkpoint_reused": False}),
                  patch("smart_video_learning.persist_visual_learning_state",
                        return_value={"sha256": "a" * 64, "training_observations": 2}),
                  patch("smart_video_learning.publish_visual_study",
                        return_value={"sha256": "b" * 64, "studied_contests": 2})):
                result = observe_batch(
                    [{"contest_id": "102", "source_url": "https://example.org/102.mp4"}],
                    root, next_contest="103", batch_workers=1,
                )
            observed = result["observational_memory"]
            self.assertEqual(observed["schema"], "SMART_BATCH_MEMORY_RECEIPT_V1")
            self.assertEqual(observed["episode_count"], 2)
            self.assertEqual(observed["motion_event_count"], 6)
            self.assertEqual(observed["graph_edges"], 6)
            self.assertEqual(len(observed["provenance_sha256"]), 64)
            self.assertEqual(observed["predictive_weight"], 0.0)
            self.assertFalse(observed["predictive_weight_authorized"])
            self.assertEqual(result["consumer_features"]["source_contests"], [100, 101])

    def test_repeated_batch_with_same_point_in_time_reuses_verified_memory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = memory_fixtures.VisualMemoryGateTests()
            helper.make_checkpoint(root, 100)
            helper.make_checkpoint(root, 101)
            with (patch("smart_video_learning._utc_now",
                        return_value="2026-10-11T00:00:00Z"),
                  patch("smart_video_learning.analyze_contest",
                        return_value={"contest_id": "102", "status": "CANDIDATE",
                                      "checkpoint_reused": True}),
                  patch("smart_video_learning.persist_visual_learning_state",
                        return_value={"sha256": "a" * 64, "training_observations": 2}),
                  patch("smart_video_learning.publish_visual_study",
                        return_value={"sha256": "b" * 64, "studied_contests": 2})):
                args = ([{"contest_id": "102",
                          "source_url": "https://example.org/102.mp4"}], root)
                cold = observe_batch(*args, next_contest="103", batch_workers=1)
                warm = observe_batch(*args, next_contest="103", batch_workers=1)
            self.assertFalse(cold["observational_memory"]["index_hit"])
            self.assertTrue(warm["observational_memory"]["index_hit"])
            self.assertEqual(cold["observational_memory"]["provenance_sha256"],
                             warm["observational_memory"]["provenance_sha256"])
            self.assertEqual(warm["observational_memory"]["predictive_weight"], 0.0)

    def test_batch_fails_closed_if_memory_source_disagrees_with_features(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            memory_fixtures.VisualMemoryGateTests().make_checkpoint(root, 100)
            with (patch("smart_video_learning.analyze_contest",
                        return_value={"contest_id": "102", "status": "CANDIDATE", "checkpoint_reused": False}),
                  patch("smart_video_learning.persist_visual_learning_state",
                        return_value={"sha256": "a" * 64, "training_observations": 1}),
                  patch("smart_video_learning.publish_visual_study",
                        return_value={"sha256": "b" * 64, "studied_contests": 1}),
                  patch("smart_video_learning.get_visual_learning_memory",
                        return_value={"schema": "SMART_VISUAL_EVIDENCE_MEMORY_V1",
                                      "episodic": [], "semantic": {"observed_event_count": 0},
                                      "graph": {"edge_count": 0}, "provenance_sha256": "x",
                                      "source_manifest_sha256": "not-the-canonical-digest",
                                      "predictive_weight": 0.0, "source_gate": "BLOCKED",
                                      "model_execution_enabled": False})):
                with self.assertRaisesRegex(ValueError, "MEMORY_SOURCE_MANIFEST_MISMATCH"):
                    observe_batch(
                        [{"contest_id": "102", "source_url": "https://example.org/102.mp4"}],
                        root, next_contest="103", batch_workers=1,
                    )


if __name__ == "__main__":
    unittest.main()
