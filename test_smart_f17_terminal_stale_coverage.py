from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import smart_terminal_engine as engine
from smart_source_identity import sha256_source_file


def _fixture(tmp_path: Path):
    root = tmp_path.resolve()
    bindings = []
    for i in range(2):
        source = root / f"source_{i}.py"
        source.write_text("alpha=2\n", encoding="utf-8")
        report = root / f"coverage_{i}.json"
        report.write_text(json.dumps({"meta": {"branch_coverage": True}}), encoding="utf-8")
        binding = root / f"binding_{i}.json"
        doc = {
            "schema": engine.independent_audit.COVERAGE_BINDING_SCHEMA,
            "source_file": source.name,
            "source_sha256": sha256_source_file(source),
            "coverage_report_file": report.name,
            "coverage_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
            "coverage_file_key": source.name,
        }
        binding.write_text(json.dumps(doc), encoding="utf-8")
        bindings.append(binding)
    (root / "source_0.py").write_text("alpha=3\n", encoding="utf-8")
    return root, bindings


def _mock_real_audits(monkeypatch):
    m = engine.independent_audit
    def stale(*args, **kwargs):
        raise ValueError("coverage binding source hash mismatch")
    monkeypatch.setattr(m, "run_independent_audit", stale)
    monkeypatch.setattr(m, "audit_coverage_binding", lambda *a, **k: {"status": "PASS"})
    monkeypatch.setattr(m, "policy_snapshot", lambda: {"fail_closed": True})
    monkeypatch.setattr(m, "audit_independence", lambda root: {"status": "PASS"})
    monkeypatch.setattr(m, "audit_prospective_ledger", lambda root, ledger: {
        "status": "PASS", "pair_count": 1, "no_future_leakage": True
    })
    monkeypatch.setattr(m, "audit_deterministic_replay", lambda *a, **k: {
        "status": "PASS", "independent_decision_oracle": {"verified": True}
    })
    monkeypatch.setattr(m, "load_material_deficiency_registry", lambda root: {
        "open_deficiencies": [],
    })


def test_degraded_consumption_checks_other_audits_but_never_claims_p14_pass(tmp_path, monkeypatch):
    root, bindings = _fixture(tmp_path)
    _mock_real_audits(monkeypatch)
    monkeypatch.setattr(engine, "COVERAGE_BINDINGS",
                        tuple(x.name for x in bindings))
    monkeypatch.setattr(engine, "TARGET", 3068)
    binding = {"ledger": root / "signal-ledger.json", "data": root / "cutoff.xlsx"}
    out = engine._run_independent_audit(root, binding)
    assert out["status"] == "DEGRADED_P14_COVERAGE_STALE"
    assert out["scientific_coverage_certified"] is False
    assert out["terminal_promotion_permitted"] is False
    assert out["checks"]["coverage_lines_and_branches"] is False
    assert out["checks"]["hash_integrity"] is False
    assert out["prospective_ledger"]["pair_count"] == 1
    assert out["historical_coverage_source_bindings"][0]["current_source_coverage_proven"] is False
    assert out["historical_coverage_source_bindings"][1]["current_source_coverage_proven"] is True
    assert (root / engine.INDEPENDENT_AUDIT_FILE).is_file()


def test_stale_coverage_with_tampered_report_remains_fatal(tmp_path, monkeypatch):
    root, bindings = _fixture(tmp_path)
    _mock_real_audits(monkeypatch)
    monkeypatch.setattr(engine, "COVERAGE_BINDINGS",
                        tuple(x.name for x in bindings))
    (root / "coverage_0.json").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="historical report hash mismatch"):
        engine._run_independent_audit(root, {"ledger": root / "ledger", "data": root / "data"})
    assert not (root / engine.INDEPENDENT_AUDIT_FILE).exists()


def test_unrelated_independent_audit_failure_never_uses_degraded_fallback(tmp_path, monkeypatch):
    root, bindings = _fixture(tmp_path)
    monkeypatch.setattr(engine, "COVERAGE_BINDINGS",
                        tuple(x.name for x in bindings))
    def unrelated(*a, **k):
        raise ValueError("prospective ledger hash mismatch")
    monkeypatch.setattr(engine.independent_audit, "run_independent_audit", unrelated)
    with pytest.raises(ValueError, match="prospective ledger hash mismatch"):
        engine._run_independent_audit(root, {"ledger": root / "ledger", "data": root / "data"})


def test_valid_coverage_keeps_existing_strict_behavior(tmp_path, monkeypatch):
    root, bindings = _fixture(tmp_path)
    monkeypatch.setattr(engine, "COVERAGE_BINDINGS", tuple(x.name for x in bindings))
    monkeypatch.setattr(engine.independent_audit, "run_independent_audit",
                        lambda *a, **k: {"status": "PASS"})
    out = engine._run_independent_audit(root, {"ledger": root / "ledger", "data": root / "data"})
    assert out["status"] == "PASS"


def test_nonpassing_full_audit_is_still_rejected(tmp_path, monkeypatch):
    root, bindings = _fixture(tmp_path)
    monkeypatch.setattr(engine, "COVERAGE_BINDINGS", tuple(x.name for x in bindings))
    monkeypatch.setattr(engine.independent_audit, "run_independent_audit",
                        lambda *a, **k: {"status": "FAIL"})
    with pytest.raises(RuntimeError, match="did not pass"):
        engine._run_independent_audit(root, {"ledger": root / "ledger", "data": root / "data"})
