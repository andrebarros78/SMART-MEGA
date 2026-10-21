import json
import os
import tempfile
import unittest
from pathlib import Path
from smart_video_learning import get_vendor_learning_status, normalize_observation_entities
from smart_video_vendor import verify_bundles, m3_observation_prompt, materialize_bundle


class VendorLearningIntegrationTests(unittest.TestCase):
    def test_four_complete_pinned_sources_integrity(self):
        report = verify_bundles()
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(set(report['verified']), {'watch-skill', 'mcp-video-analyzer', 'm3-agent', 'TaskMem'})
        self.assertEqual(report['predictive_weight'], 0.0)

    def test_vendor_lock_tracks_canonical_current_execution_policy(self):
        from smart_github_native_policy import POLICY_ID
        lock = json.loads((Path(__file__).parent /
                           "vendor/visual_learning/VENDOR_LOCK.json").read_text())
        self.assertEqual(lock["production_policy"], POLICY_ID)

    def test_taskmem_original_normalization_is_callable(self):
        self.assertEqual(normalize_observation_entities('FACE_12 and face 9'), '<face_12> and <face_9>')

    def test_m3_original_observation_prompt_is_callable(self):
        prompt = m3_observation_prompt()
        self.assertIn('video', prompt.lower())
        self.assertIn('feature', prompt.lower())

    def test_status_fails_closed_and_exposes_four_engines(self):
        data = get_vendor_learning_status()
        self.assertEqual(set(data['components']), {'watch-skill', 'mcp-video-analyzer', 'm3-agent', 'TaskMem'})
        self.assertFalse(data['model_execution_enabled'])
        self.assertEqual(data['predictive_weight'], 0.0)
        self.assertEqual(data['source_gate'], 'BLOCKED')

    def test_materialization_offline_safe_path(self):
        with tempfile.TemporaryDirectory() as directory:
            result = materialize_bundle('TaskMem', Path(directory) / 'installed')
            self.assertEqual(result['status'], 'MATERIALIZED_SOURCE_ONLY')
            self.assertTrue((Path(directory) / 'installed' / 'memory' / 'short_term_memory.py').is_file())
            self.assertFalse((Path(directory) / 'installed' / '.git').exists())

    def test_tampered_snapshot_denied(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(__file__).parent / 'vendor/visual_learning'
            target = Path(directory)
            (target / 'sources').mkdir()
            lock = json.loads((source/'VENDOR_LOCK.json').read_text())
            for item in lock['sources']:
                for key in ('archive', 'license_file'):
                    os.link(source / item[key], target / item[key])
            item = next(x for x in lock['sources'] if x['name']=='TaskMem')
            (target / item['archive']).unlink()
            (target / item['archive']).write_bytes(b'poison')
            (target/'VENDOR_LOCK.json').write_text(json.dumps(lock))
            with self.assertRaisesRegex(ValueError, 'VENDOR_DIGEST_MISMATCH'):
                verify_bundles(target)


if __name__ == '__main__':
    unittest.main()
