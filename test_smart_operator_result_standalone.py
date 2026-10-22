"""Registration contract is testable without statistical runtime dependencies."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from smart_official_result_validation import validate_official_payload
from smart_operator_result import register, fetch


class StandaloneResultTest(unittest.TestCase):
    def test_operator_register_idempotent_and_hash_checked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"schema": "SMART_OPERATOR_RESULT_INPUT_1", "target_contest": 3071,
                       "draw_date": "18/10/2026", "numbers": [12, 22, 41, 45, 51, 52]}
            source = root / "result.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            first = register(root, 3071, source)
            self.assertEqual(register(root, 3071, source), first)
            official, evidence = fetch(root, 3071)
            self.assertEqual(official["listaDezenas"], ["12", "22", "41", "45", "51", "52"])
            self.assertFalse(evidence["dual_channel_corroborated"])
            self.assertFalse(evidence["predictive_weight_authorized"])
            out = root / "SMART_OPERATOR_RESULT_3071.json"
            tampered = json.loads(out.read_text())
            tampered["actual_numbers"] = [1, 2, 3, 4, 5, 6]
            out.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash"):
                fetch(root, 3071)

    def test_rejects_invalid_draws(self):
        sample = {"numero": 3071, "dataApuracao": "18/10/2026",
                  "listaDezenas": [12, 22, 41, 45, 51, 52]}
        self.assertEqual(validate_official_payload(sample, 3071)["numbers"], sample["listaDezenas"])
        for invalid in ([12, 12, 41, 45, 51, 52], [0, 22, 41, 45, 51, 52],
                        [12, 22, 41, 45, 51, 61]):
            # Preserve all negative inputs; pytest 9's passed unittest
            # subtests inflate JUnit totals without serializing testcases.
            with self.assertRaises(ValueError):
                validate_official_payload({**sample, "listaDezenas": invalid}, 3071)
        with self.assertRaises(ValueError):
            validate_official_payload({**sample, "numero": 3070}, 3071)


if __name__ == "__main__":
    unittest.main()
