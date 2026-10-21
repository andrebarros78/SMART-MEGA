from pathlib import Path

import smart_product_certification as certification
from smart_global_integrity import CRITICAL_SOURCE_FILES

ROOT = Path(__file__).resolve().parent


def test_product_certification_fingerprint_covers_global_critical_surface() -> None:
    names = {path.name for path in certification._code_files(ROOT)}
    assert set(CRITICAL_SOURCE_FILES) <= names
    assert "adjudicate_signal_challenger.py" in names
    assert "freeze_next_research.py" in names
    assert "p14_coverage_plugin.py" in names


def test_product_certification_fingerprint_changes_for_nonprefix_critical_source(tmp_path: Path) -> None:
    source = tmp_path / "adjudicate_signal_challenger.py"
    source.write_text("alpha\n", encoding="utf-8")
    before = certification.code_fingerprint(tmp_path)["sha256"]
    source.write_text("beta\n", encoding="utf-8")
    after = certification.code_fingerprint(tmp_path)["sha256"]
    assert before != after

def test_product_certification_canonical_authority_is_bound_to_current_junit() -> None:
    junit = ROOT / "SMART_AUDIT_JUNIT_CURRENT.xml"
    regression = certification.junit_summary(junit)
    binding = certification.canonical_root_authority_binding(ROOT, junit, regression)
    assert binding["status"] == "PASS"
    assert all(binding["checks"].values())


def test_product_certification_canonical_authority_fails_closed_on_stale_junit_hash(tmp_path: Path) -> None:
    junit = tmp_path / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text("<testsuites name='pytest tests'><testsuite name='pytest' tests='1' failures='0' errors='0' skipped='0'><testcase classname='x' name='y'/></testsuite></testsuites>", encoding="utf-8")
    regression = certification.junit_summary(junit)
    authority = {
        "schema": "SMART_CANONICAL_ROOT_V1",
        "project": "SMART-MEGA",
        "version": "6.3.1",
        "canonical_root": str(tmp_path.resolve()),
        "legacy_alias_present": False,
        "canonical_state": "CANONICAL_ONLY",
        "certified_regression_tests": regression["tests"],
        "certified_regression_failures": regression["failures"],
        "certified_regression_errors": regression["errors"],
        "certified_regression_junit": junit.name,
        "certified_regression_junit_sha256": "0" * 64,
        "certified_regression": {
            "tests": regression["tests"], "failures": regression["failures"], "errors": regression["errors"],
            "junit_file": junit.name, "junit_sha256": "0" * 64,
        },
    }
    authority["sha256"] = certification._sha256_json(authority)
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(__import__("json").dumps(authority), encoding="utf-8")
    binding = certification.canonical_root_authority_binding(tmp_path.resolve(), junit, regression)
    assert binding["status"] == "FAIL"
    assert binding["checks"]["junit_sha_bound"] is False



def test_verify_current_code_rejects_stale_tested_source(tmp_path: Path, monkeypatch) -> None:
    import json
    import pytest

    code = tmp_path / "smart_example.py"
    code.write_text("print('current')\n", encoding="utf-8")
    junit = tmp_path / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text("<testsuites><testsuite tests='1' failures='0' errors='0' skipped='0'><testcase classname='x' name='y'/></testsuite></testsuites>", encoding="utf-8")
    fingerprint = {"sha256": "f" * 64}
    regression = {"tests": 1, "failures": 0, "errors": 0, "skipped": 0, "status": "PASS", "sha256": "j" * 64}
    authority = {"status": "PASS"}
    source = {"status": "PASS", "source_commit": "a" * 40}
    monkeypatch.setattr(certification, "code_fingerprint", lambda root: fingerprint)
    monkeypatch.setattr(certification, "junit_summary", lambda path: regression)
    monkeypatch.setattr(certification, "canonical_root_authority_binding", lambda root, path, summary: authority)
    monkeypatch.setattr(certification, "regression_source_binding", lambda root, path, fp: {"status": "FAIL"})
    doc = {
        "schema": certification.SCHEMA,
        "status": "CONSTRUCTION_PROVEN",
        "checks": {"full_regression_green": True},
        "code_fingerprint": fingerprint,
        "critical_code_manifest": certification.build_critical_code_manifest(tmp_path),
        "canonical_root_authority": authority,
        "regression_source": source,
    }
    doc["sha256"] = certification._sha256_json(doc)
    path = tmp_path / "SMART_PRODUCT_CERTIFICATION.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="regression source is stale"):
        certification.verify_product_certification(path, root=tmp_path, require_current_code=True)


def test_verify_current_code_accepts_matching_tested_source_despite_checkout_mtime(tmp_path: Path, monkeypatch) -> None:
    import json
    import os

    code = tmp_path / "smart_example.py"
    code.write_text("print('current')\n", encoding="utf-8")
    junit = tmp_path / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text("<testsuites><testsuite tests='1' failures='0' errors='0' skipped='0'><testcase classname='x' name='y'/></testsuite></testsuites>", encoding="utf-8")
    os.utime(junit, (1000, 1000))
    os.utime(code, (2000, 2000))
    fingerprint = {"sha256": "f" * 64}
    regression = {"tests": 1, "failures": 0, "errors": 0, "skipped": 0, "status": "PASS", "sha256": "j" * 64}
    authority = {"status": "PASS"}
    source = {"status": "PASS", "source_commit": "a" * 40}
    monkeypatch.setattr(certification, "code_fingerprint", lambda root: fingerprint)
    monkeypatch.setattr(certification, "junit_summary", lambda path: regression)
    monkeypatch.setattr(certification, "canonical_root_authority_binding", lambda root, path, summary: authority)
    monkeypatch.setattr(certification, "regression_source_binding", lambda root, path, fp: source)
    doc = {
        "schema": certification.SCHEMA,
        "status": "CONSTRUCTION_PROVEN",
        "checks": {"full_regression_green": True},
        "code_fingerprint": fingerprint,
        "critical_code_manifest": certification.build_critical_code_manifest(tmp_path),
        "canonical_root_authority": authority,
        "regression_source": source,
    }
    doc["sha256"] = certification._sha256_json(doc)
    path = tmp_path / "SMART_PRODUCT_CERTIFICATION.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert certification.verify_product_certification(path, root=tmp_path, require_current_code=True)["status"] == "CONSTRUCTION_PROVEN"


def test_regression_source_binding_rejects_source_drift(tmp_path: Path) -> None:
    import json
    import subprocess
    from smart_agent_runtime import sha256_file

    code = tmp_path / "smart_example.py"
    code.write_text("print('tested')\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", tmp_path.as_posix()], check=True)
    subprocess.run(["git", "add", "smart_example.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
                    "commit", "-qm", "tested source"], cwd=tmp_path, check=True)
    source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                            capture_output=True, text=True).stdout.strip()
    junit = tmp_path / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text("<testsuites><testsuite tests='1' failures='0' errors='0' skipped='0'><testcase classname='x' name='y'/></testsuite></testsuites>", encoding="utf-8")
    fp = certification.code_fingerprint(tmp_path)
    authority = {
        "certified_source_commit": source,
        "certified_ci_run_id": "123",
        "certified_execution": {"kind": "GITHUB_ACTIONS", "run_id": "123"},
        "certified_source_code_fingerprint_sha256": fp["sha256"],
        "certified_regression_junit_sha256": sha256_file(junit),
    }
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority), encoding="utf-8")
    assert certification.regression_source_binding(tmp_path, junit, fp)["status"] == "PASS"
    code.write_text("print('untested')\n", encoding="utf-8")
    assert certification.regression_source_binding(tmp_path, junit, certification.code_fingerprint(tmp_path))["status"] == "FAIL"


def test_pytest_discovery_excludes_state_archive() -> None:
    text = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if row.strip().startswith("norecursedirs"))
    excluded = set(line.split("=", 1)[1].split())
    assert "SMART_STATE_ARCHIVE" in excluded


def test_state_archive_has_no_collectible_pytest_modules() -> None:
    archive = ROOT / "SMART_STATE_ARCHIVE"
    bad = sorted(str(path.relative_to(ROOT)) for path in archive.rglob("test_*.py")) if archive.is_dir() else []
    assert bad == []


def test_canonical_authority_fails_when_declared_removed_legacy_alias_physically_exists(tmp_path: Path) -> None:
    import json, socket
    junit = tmp_path / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text("<testsuites><testsuite tests='1' failures='0' errors='0' skipped='0'><testcase classname='x' name='y'/></testsuite></testsuites>", encoding="utf-8")
    regression = certification.junit_summary(junit)
    legacy = tmp_path / "legacy"; legacy.mkdir()
    jsha = certification.sha256_file(junit)
    authority = {
        "schema": "SMART_CANONICAL_ROOT_V1", "project": "SMART-MEGA", "version": "6.3.1",
        "canonical_root": str(tmp_path.resolve()), "hostname": socket.gethostname(),
        "legacy_alias": str(legacy), "legacy_alias_type": "REMOVED", "legacy_alias_present": False,
        "canonical_state": "CANONICAL_ONLY",
        "certified_regression_tests": 1, "certified_regression_failures": 0, "certified_regression_errors": 0,
        "certified_regression_junit": junit.name, "certified_regression_junit_sha256": jsha,
        "certified_regression": {"tests":1,"failures":0,"errors":0,"junit_file":junit.name,"junit_sha256":jsha},
    }
    authority["sha256"] = certification._sha256_json(authority)
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority), encoding="utf-8")
    binding = certification.canonical_root_authority_binding(tmp_path.resolve(), junit, regression)
    assert binding["status"] == "FAIL"
    assert binding["checks"]["legacy_alias_physically_absent"] is False
