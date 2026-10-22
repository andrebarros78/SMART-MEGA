"""Prod-base consumer contract: acquired source provenance never grants PIT bypass."""
import json
import tempfile
import unittest
from pathlib import Path
from smart_video_learning import get_visual_features, get_vendor_learning_status
from smart_video_observation import ObservationConfig, EXTRACTOR_VERSION, PREDICTIVE_EVIDENCE, _observation_fingerprint


class ProductionLearningConsumerTests(unittest.TestCase):
    @staticmethod
    def make_checkpoint(root, contest, timestamp):
        cfg = ObservationConfig()
        url = f'https://example.org/{contest}.mp4'
        data = {
            'schema': 'smart.video_observation.v1', 'contest_id': str(contest),
            'source': url, 'extractor_version': EXTRACTOR_VERSION,
            'predictive_evidence': PREDICTIVE_EVIDENCE, 'hypothesis_id': None,
            'main_params': vars(cfg),
            'checkpoint_fingerprint': _observation_fingerprint(str(contest), url, cfg, None),
            'status': 'CANDIDATE', 'analysis_scope': {'start_s': 0, 'end_s': 100,
                'segment_guard_passed': True}, 'spatial_consensus': {'recurrent': True},
            'event_timestamps_s': [40, 50, 60], 'created_at_utc': timestamp,
        }
        path = root / f'contest_{contest}.json'
        path.write_text(json.dumps(data))
        return path

    def test_historical_only_then_cutoff_revoked_after_cache_warmed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for contest in (100, 101, 102, 103):
                self.make_checkpoint(root, contest, '2026-10-10T17:00:00Z')
            kwargs = {'target_contest':'103','cutoff_utc':'2026-10-11T00:00:00Z',
                      'checkpoint_dir':root}
            initial = get_visual_features(**kwargs)
            self.assertEqual(initial['source_contests'], [100, 101, 102])
            self.assertEqual(initial['observational_features']['eligible_observations'], 3)
            self.assertEqual(initial['predictive_weight'], 0.0)
            self.assertFalse(initial['predictive_weight_authorized'])
            self.assertEqual(get_visual_features(**kwargs)['source_sha256'], initial['source_sha256'])
            poisoned = root/'contest_102.json'
            obj = json.loads(poisoned.read_text())
            obj['created_at_utc'] = '2026-10-12T00:00:00Z'
            poisoned.write_text(json.dumps(obj))
            corrected = get_visual_features(**kwargs)
            self.assertEqual(corrected['source_contests'], [100, 101])
            self.assertNotIn('102', corrected['source_sha256'])
            self.assertEqual(corrected['predictive_evidence'], 'NOT_ESTABLISHED')

    def test_invalid_temporal_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            for bad in ('garbage', '2026-10-10T10:00:00', ''):
                with self.assertRaises(ValueError):
                    get_visual_features('103', bad, directory)
            with self.assertRaises(ValueError):
                get_visual_features('0', '2026-10-11T00:00:00Z', directory)

    def test_vendor_engines_never_enable_source_or_predictions(self):
        status = get_vendor_learning_status()
        self.assertEqual(status['source_gate'], 'BLOCKED')
        self.assertTrue(all(not x['operational'] for x in status['components'].values()))
        self.assertEqual(status['predictive_weight'], 0.0)


if __name__ == '__main__':
    unittest.main()
