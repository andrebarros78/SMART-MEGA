"""CAIXA public-page transcription remains explicitly non-API-authoritative."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from smart_official_result_validation import validate_official_payload

ROOT = Path(__file__).resolve().parent
SCHEMA = "SMART_CAIXA_PORTAL_TRANSCRIPTION_BATCH_1"
AUTHORITY = "CAIXA_PUBLIC_PORTAL_TRANSCRIPTION_NOT_API_VERIFIED"
PORTAL_URL = "https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx"
API_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/3072"


def sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def loader():
    source = (ROOT / "smart_missed_catchup.py").read_text()
    node = next(x for x in ast.parse(source).body
                if isinstance(x, ast.FunctionDef) and x.name == "load_official_payload_batch")
    ns = dict(Path=Path, Any=Any, json=json, OFFICIAL_BATCH_SCHEMA="SMART_OFFICIAL_RESULT_BATCH_1",
              validate_official_payload=validate_official_payload,
              sha256_file=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
              _sha_json=sha)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "smart_missed_catchup.py", "exec"), ns)
    return ns["load_official_payload_batch"]


def payload():
    return {
        "numero": 3072, "dataApuracao": "20/10/2026",
        "listaDezenas": ["02", "06", "09", "16", "31", "40"],
        "source": "CAIXA_PORTAL_TRANSCRIPTION", "endpoint": PORTAL_URL,
    }


def batch(schema=SCHEMA, source=None):
    row = dict(payload(), **(source or {}))
    obj = {
        "schema": schema, "authority": AUTHORITY, "portal_url": PORTAL_URL,
        "raw_api_independently_verified": False,
        "retrieved_at_utc": "2026-10-21T10:00:00+00:00",
        "capture_transport": "PUBLIC_CAIXA_PAGE_TRANSCRIPTION",
        "results": [row],
    }
    obj["sha256"] = sha(obj)
    return obj


class TestPortalTranscription(unittest.TestCase):
    def test_portal_result_is_usable_for_operational_catchup_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.json"
            path.write_text(json.dumps(batch()), encoding="utf-8")
            rows, evidence = loader()(path)
        self.assertEqual(rows[3072]["source"], "CAIXA_PORTAL_TRANSCRIPTION")
        self.assertEqual(evidence["authority"], AUTHORITY)
        self.assertFalse(evidence["raw_api_independently_verified"])

    def test_unverified_portal_row_cannot_impersonate_api(self):
        forged = batch(schema="SMART_OFFICIAL_RESULT_BATCH_1")
        forged["authority"] = "CAIXA_LOTERIAS_OFFICIAL_API"
        forged["results"][0]["endpoint"] = API_URL
        forged["sha256"] = sha({k: v for k, v in forged.items() if k != "sha256"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.json"
            path.write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "API.*source"):
                loader()(path)

    def test_portal_cannot_falsely_set_independent_api_verified(self):
        forged = batch()
        forged["raw_api_independently_verified"] = True
        forged["sha256"] = sha({k: v for k, v in forged.items() if k != "sha256"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.json"
            path.write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "independent"):
                loader()(path)

    def test_real_public_capture_3072_is_bound_and_not_official_api(self):
        path = ROOT / "SMART_PUBLIC_RESULT_BATCH_3072.json"
        rows, evidence = loader()(path)
        self.assertEqual(list(rows), [3072])
        self.assertEqual(rows[3072]["listaDezenas"], ["02", "06", "09", "16", "31", "40"])
        self.assertEqual(evidence["authority"], "TWO_PUBLIC_SOURCES_NOT_CAIXA_API_VERIFIED")
        self.assertFalse(evidence["raw_api_independently_verified"])

    def test_two_public_providers_must_match_the_result_row(self):
        source = json.loads((ROOT / "SMART_PUBLIC_RESULT_BATCH_3072.json").read_text())
        source["providers"][0]["numbers"] = [1, 2, 3, 4, 5, 6]
        source["sha256"] = sha({k: v for k,v in source.items() if k != "sha256"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake.json"
            path.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, "crosscheck provenance"):
                loader()(path)

    def test_ingest_records_public_corroboration_as_unverified_api(self):
        source = (ROOT / "smart_official_result_ingest.py").read_text()
        node = next(x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef) and x.name == "ingest")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "old.xlsx"
            data.write_bytes(b"prior")
            dest = root / "next.xlsx"
            proof = root / "proof.json"
            ns = dict(Path=Path, Any=Any, json=json, hashlib=hashlib, datetime=datetime,
                      timezone=timezone, SCHEMA="SMART_OFFICIAL_RESULT_INGEST_1",
                      API_URL="https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{contest}",
                      validate_official_payload=validate_official_payload,
                      sha256_file=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
                      build_extended_frame=lambda src,t,p: [p],
                      _atomic_excel_write=lambda frame,p: Path(p).write_bytes(b"newxlsx"))
            exec(compile(ast.Module(body=[node], type_ignores=[]), "official_ingest.py", "exec"), ns)
            payload = json.loads((ROOT / "SMART_PUBLIC_RESULT_BATCH_3072.json").read_text())["results"][0]
            result = ns["ingest"](data,dest,proof,3072,payload)
        self.assertFalse(result["source_independently_verified"])
        self.assertEqual(result["result_input_authority"], "PUBLIC_CROSSCHECK_UNVERIFIED_OFFICIAL")
        self.assertIsNone(result["official_endpoint"])

    def test_ingest_records_portal_without_automatic_api_certification(self):
        source = (ROOT / "smart_official_result_ingest.py").read_text()
        node = next(x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef) and x.name == "ingest")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "old.xlsx"
            data.write_bytes(b"prior")
            dest = root / "next.xlsx"
            proof = root / "proof.json"
            import types
            ns = dict(Path=Path, Any=Any, json=json, hashlib=hashlib, datetime=datetime,
                      timezone=timezone, SCHEMA="SMART_OFFICIAL_RESULT_INGEST_1",
                      API_URL="https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{contest}",
                      validate_official_payload=validate_official_payload,
                      sha256_file=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
                      build_extended_frame=lambda src,t,p: [p],
                      _atomic_excel_write=lambda frame,p: Path(p).write_bytes(b"newxlsx"))
            exec(compile(ast.Module(body=[node], type_ignores=[]), "official_ingest.py", "exec"), ns)
            result = ns["ingest"](data,dest,proof,3072,payload())
        self.assertFalse(result["source_independently_verified"])
        self.assertEqual(result["result_input_authority"], "CAIXA_PORTAL_TRANSCRIPTION")
        self.assertEqual(result["official_endpoint"], PORTAL_URL)


if __name__ == "__main__":
    unittest.main()
