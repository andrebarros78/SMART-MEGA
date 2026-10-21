import tempfile
import unittest
from pathlib import Path
from isolated_source_gate.video_learning_fastpath import candidate_checkpoints, learning_metrics


class FastPathTests(unittest.TestCase):
    def test_prior_only_sorted_and_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            for n in (99, 100, 101, 102, 97):
                (Path(root) / f"contest_{n}.json").write_text("{}")
            got = candidate_checkpoints(root, "101", limit=2)
            self.assertEqual([p.stem for p in got], ["contest_100", "contest_99"])

    def test_rejects_invalid_target(self):
        with tempfile.TemporaryDirectory() as root:
            for target in ("0", "-1", "test"):
                with self.assertRaises(ValueError):
                    candidate_checkpoints(root, target)

    def test_invalid_limits(self):
        with tempfile.TemporaryDirectory() as root:
            for limit in (0, 513, True):
                with self.assertRaises(ValueError):
                    candidate_checkpoints(root, "101", limit=limit)

    def test_missing_directory(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(candidate_checkpoints(Path(root) / "missing", "101"), [])

    def test_metrics_do_not_promote(self):
        data = learning_metrics(discovered=10, eligible=3, reused=2, elapsed_ms=9.5)
        self.assertEqual(data["predictive_weight"], 0.0)
        self.assertEqual(data["predictive_evidence"], "NOT_ESTABLISHED")

    def test_invalid_metrics(self):
        with self.assertRaises(ValueError):
            learning_metrics(discovered=2, eligible=3, reused=1, elapsed_ms=1)


if __name__ == "__main__":
    unittest.main()
