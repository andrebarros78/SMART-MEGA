import json
import tempfile
import unittest
from pathlib import Path
from smart_video_observation import (learned_motion_prior, ObservationConfig,
    EXTRACTOR_VERSION, PREDICTIVE_EVIDENCE, _observation_fingerprint)


class CachedPITTests(unittest.TestCase):
    def test_cached_checkpoint_mutated_after_cutoff_is_excluded(self):
        cfg = ObservationConfig()
        with tempfile.TemporaryDirectory() as directory:
            for contest in (100, 101, 102, 103):
                url = f"https://example.org/{contest}.mp4"
                payload = {
                    "contest_id": str(contest), "source": url,
                    "extractor_version": EXTRACTOR_VERSION,
                    "predictive_evidence": PREDICTIVE_EVIDENCE,
                    "hypothesis_id": None, "main_params": vars(cfg),
                    "checkpoint_fingerprint": _observation_fingerprint(str(contest), url, cfg, None),
                    "status": "CANDIDATE", "spatial_consensus": {"recurrent": True},
                    "analysis_scope": {"start_s": 0, "end_s": 100},
                    "event_timestamps_s": [30, 40, 50],
                    "created_at_utc": "2026-10-10T00:00:00Z",
                }
                Path(directory, f"contest_{contest}.json").write_text(json.dumps(payload))
            args = (directory, "103")
            first = learned_motion_prior(*args, cutoff_utc="2026-10-11T00:00:00Z")
            self.assertEqual(first["training_contests"], [100, 101, 102])
            second = learned_motion_prior(*args, cutoff_utc="2026-10-11T00:00:00Z")
            self.assertEqual(first["training_sha256"], second["training_sha256"])
            file = Path(directory, "contest_102.json")
            payload = json.loads(file.read_text())
            payload["created_at_utc"] = "2026-10-12T00:00:00Z"
            file.write_text(json.dumps(payload))
            third = learned_motion_prior(*args, cutoff_utc="2026-10-11T00:00:00Z")
            self.assertEqual(third["training_contests"], [100, 101])
            self.assertNotIn("102", third["training_sha256"])
            self.assertEqual(third["predictive_evidence"], "NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()
