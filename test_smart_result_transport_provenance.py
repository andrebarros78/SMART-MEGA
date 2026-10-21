"""Standalone regression: local result payload cannot impersonate a verified CAIXA API fetch."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from typing import Any


def _load_ingest_without_optional_runtime():
    path = Path(__file__).with_name("smart_official_result_ingest.py")
    node = next(node for node in ast.parse(path.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "ingest")

    class Frame:
        def __len__(self):
            return 2

    ns = {
        "Path": Path, "Any": Any, "datetime": datetime, "timezone": timezone,
        "json": json, "hashlib": hashlib,
        "SCHEMA": "SMART_OFFICIAL_RESULT_INGEST_1",
        "API_URL": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{contest}",
        "sha256_file": lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "build_extended_frame": lambda source, target, official: Frame(),
        "_atomic_excel_write": lambda frame, output: Path(output).write_bytes(b"synthetic test workbook"),
        "validate_official_payload": lambda payload, target: {
            "draw_date_text": "20/10/2026", "numbers": [2, 6, 9, 16, 31, 40]
        },
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return ns["ingest"]


class TestResultTransportProvenance(unittest.TestCase):
    def _run(self, source_label):
        ingest = _load_ingest_without_optional_runtime()
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "source.xlsx").write_bytes(b"synthetic history")
            payload = {"numero": 3072, "listaDezenas": ["02", "06", "09", "16", "31", "40"]}
            if source_label is not None:
                payload["source"] = source_label
            result = ingest(root / "source.xlsx", root / "out.xlsx", root / "proof.json", 3072, payload)
            self.assertEqual(json.loads((root / "proof.json").read_text())["sha256"], result["sha256"])
            return result

    def test_unlabeled_local_payload_is_not_independent_caixa_api_evidence(self):
        result = self._run(None)
        self.assertIs(result["source_independently_verified"], False)
        self.assertIsNone(result["official_endpoint"])
        self.assertEqual(result["result_input_authority"], "UNATTRIBUTED_LOCAL_PAYLOAD")

    def test_explicit_caixa_label_alone_is_not_transport_proof(self):
        result = self._run("CAIXA_CONTEST_API")
        self.assertIs(result["source_independently_verified"], False)

    def test_operator_result_never_claims_caixa_transport(self):
        result = self._run("OPERATOR")
        self.assertIs(result["source_independently_verified"], False)
        self.assertIsNone(result["official_endpoint"])


if __name__ == "__main__":
    unittest.main()
