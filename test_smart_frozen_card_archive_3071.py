"""3071 remains readable from immutable history after 3072 rollover."""
from __future__ import annotations
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from smart_frozen_card_reader import read_frozen_card, verify_result

ROOT = Path(__file__).resolve().parent
ARCHIVE = next((ROOT / 'SMART_STATE_ARCHIVE' / 'adjudicated-epochs' / '3071').glob('*/'), None)

class TestImmutableArchivedCard(unittest.TestCase):
    def test_archived_card_3071_remains_readable_without_new_generation(self):
        self.assertIsNotNone(ARCHIVE)
        before = (ARCHIVE / 'ARCHIVE_MANIFEST.json').read_bytes()
        result = read_frozen_card(ROOT, 3071)
        self.assertEqual(result['numbers'], [10,11,27,38,43,53])
        self.assertTrue(result['readonly'])
        self.assertFalse(result['result_used_in_generation'])
        self.assertTrue(verify_result(result))
        self.assertEqual(before, (ARCHIVE / 'ARCHIVE_MANIFEST.json').read_bytes())

    def _copy_archive(self, destination):
        relative = ARCHIVE.relative_to(ROOT)
        place = destination / relative
        place.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ARCHIVE, place)
        return place

    def test_manifest_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            place = self._copy_archive(root)
            manifest = place / 'ARCHIVE_MANIFEST.json'
            obj = json.loads(manifest.read_text())
            obj['byte_for_byte_verified'] = False
            manifest.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError, 'archive.*hash'):
                read_frozen_card(root, 3071)

    def test_archived_card_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            place = self._copy_archive(root)
            card = place / 'epoch' / 'SMART_3071_PRIMARY_CARD.json'
            card.write_text('{}')
            with self.assertRaisesRegex(ValueError, '(archive|card).*SHA|archive.*hash'):
                read_frozen_card(root, 3071)

    def test_multiple_manifest_candidates_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            place = self._copy_archive(root)
            shutil.copytree(place, place.parent / 'untrusted-duplicate')
            with self.assertRaisesRegex(ValueError, 'unique immutable archive'):
                read_frozen_card(root, 3071)

if __name__ == '__main__':
    unittest.main()
