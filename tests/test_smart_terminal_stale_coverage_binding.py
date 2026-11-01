"""P14 stale coverage is observed, never promoted as current source proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smart_source_identity import sha256_source_file
from smart_terminal_stale_coverage import verified_stale_coverage_observations


SCHEMA = "SMART_COVERAGE_BINDING_1"


def _setup(tmp_path, *, entries=2):
    paths = []
    doc_paths = []
    for idx in range(entries):
        source = tmp_path / f"source_{idx}.py"
        source.write_bytes(b"def rule():\n    return 1\n")
        report = tmp_path / f"coverage_{idx}.json"
        report.write_bytes(b'{"coverage":"old"}')
        path = tmp_path / f"binding_{idx}.json"
        data = {
            "schema": SCHEMA,
            "source_file": source.name,
            "source_sha256": sha256_source_file(source),
            "coverage_report_file": report.name,
            "coverage_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        paths.append(path)
        doc_paths.append(data)
    calls = []

    def observe():
        return verified_stale_coverage_observations(
            tmp_path, paths, read_json=lambda path: json.loads(path.read_text(encoding="utf-8")),
            sha256_file=lambda path: hashlib.sha256(path.read_bytes()).hexdigest(),
            sha256_source_file=sha256_source_file, coverage_binding_schema=SCHEMA,
            audit_coverage_binding=lambda root, path: calls.append(path.name),
        )
    return paths, doc_paths, calls, observe


def test_stale_and_current_binding_preserve_provenance_separately(tmp_path):
    paths, docs, calls, run = _setup(tmp_path)
    (tmp_path / "source_0.py").write_bytes(b"def rule():\n    return 2\n")
    actual = run()
    assert len(actual) == 2
    assert actual[0]["current_source_coverage_proven"] is False
    assert actual[0]["historical_source_sha256"] == docs[0]["source_sha256"]
    assert actual[0]["current_source_sha256"] == sha256_source_file(tmp_path / "source_0.py")
    assert actual[0]["report_sha256_verified"] is True
    assert actual[1]["current_source_coverage_proven"] is True
    assert calls == ["binding_1.json"]
    assert not list(tmp_path.glob("*tmp*"))


def test_all_current_coverage_cannot_be_downgraded_to_stale(tmp_path):
    paths, docs, calls, run = _setup(tmp_path)
    with pytest.raises(RuntimeError, match="fully current P14 coverage set as stale"):
        run()
    assert calls == ["binding_0.json", "binding_1.json"]


@pytest.mark.parametrize("mutation, error", [
    ("report_tampered", "historical report hash mismatch"),
    ("report_missing", "evidence path is unsafe or missing"),
    ("source_missing", "evidence path is unsafe or missing"),
    ("schema_invalid", "binding schema invalid"),
    ("source_absolute", "source/report path invalid"),
    ("report_absolute", "source/report path invalid"),
    ("source_nonstring", "source/report path invalid"),
    ("report_nonstring", "source/report path invalid"),
    ("source_escape", "evidence path is unsafe or missing"),
    ("binding_outside_root", "binding path is unsafe"),
    ("binding_missing", "binding path is unsafe"),
])
def test_corrupt_coverage_sources_fail_closed(tmp_path, mutation, error):
    paths, docs, calls, run = _setup(tmp_path)
    (tmp_path / "source_0.py").write_bytes(b"changed source")
    if mutation == "report_tampered":
        (tmp_path / "coverage_0.json").write_bytes(b"tampered")
    elif mutation == "report_missing":
        (tmp_path / "coverage_0.json").unlink()
    elif mutation == "source_missing":
        (tmp_path / "source_0.py").unlink()
    elif mutation == "schema_invalid":
        docs[0]["schema"] = "UNTRUSTED"
    elif mutation == "source_absolute":
        docs[0]["source_file"] = str(tmp_path / "source_0.py")
    elif mutation == "report_absolute":
        docs[0]["coverage_report_file"] = str(tmp_path / "coverage_0.json")
    elif mutation == "source_nonstring":
        docs[0]["source_file"] = 42
    elif mutation == "report_nonstring":
        docs[0]["coverage_report_file"] = None
    elif mutation == "source_escape":
        docs[0]["source_file"] = "../missing-source.py"
    elif mutation == "binding_outside_root":
        paths[0] = tmp_path.parent / "missing-outside-binding.json"
    elif mutation == "binding_missing":
        paths[0].unlink()
    if mutation in {"schema_invalid", "source_absolute", "report_absolute",
                    "source_nonstring", "report_nonstring", "source_escape"}:
        paths[0].write_text(json.dumps(docs[0]), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        run()
    assert calls == []


def test_independent_current_binding_audit_error_must_propagate(tmp_path):
    paths, docs, calls, run = _setup(tmp_path, entries=1)
    def audit_fail(root, path):
        raise ValueError("P14 coverage gate failed")
    with pytest.raises(ValueError, match="P14 coverage gate failed"):
        verified_stale_coverage_observations(
            tmp_path, paths, read_json=lambda path: json.loads(path.read_text()),
            sha256_file=lambda path: hashlib.sha256(path.read_bytes()).hexdigest(),
            sha256_source_file=sha256_source_file, coverage_binding_schema=SCHEMA,
            audit_coverage_binding=audit_fail,
        )