"""Execute real pytest coverage and consume source-bound missing-line evidence.

Engineering-only diagnostic: no prediction, training, weights or sealed results.
Not an invocation of any similarly named external skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SCHEMA = "SMART_TEST_GAP_NATIVE_CONSUMPTION_1"
SOURCE_FILES = (
    "smart_experiment_lab.py",
    "smart_operator.py",
    "smart_skill_runtime.py",
    "smart_post_result_report.py",
    "smart_skill_reconciliation.py",
)
TEST_FILES = (
    "test_smart_post_result_mlflow.py",
    "test_smart_operator_result_materialization.py",
    "test_smart_skill_runtime.py",
    "test_smart_post_result_report.py",
)
TEST_SELECTOR = (
    "test_mlflow_real_signed_observation_persists_replays_and_recovers or "
    "test_mlflow_signed_observation_rejects_wrong_hash_and_tampering or "
    "test_result_materialization_is_byte_exact_and_idempotent or "
    "test_unknown_capability_and_bad_payload_fail_closed or "
    "test_remaining_capability_reconciliation_refuses_forged_receipts"
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _inputs(root: Path) -> dict[str, str]:
    return {name: _sha256_file(root / name) for name in (*SOURCE_FILES, *TEST_FILES)}


def execute_test_gap(root: str | Path) -> dict[str, Any]:
    """Measure statement/branch gaps with Coverage.py tracing a real pytest run."""
    import coverage

    root = Path(root).resolve()
    identities_before = _inputs(root)
    with tempfile.TemporaryDirectory(prefix="smartmega-gap-coverage-") as directory:
        temp = Path(directory)
        data_file = temp / "coverage.data"
        junit = temp / "junit.xml"
        command = [sys.executable, "-m", "coverage", "run", "--branch",
                   f"--data-file={data_file}",
                   f"--source={','.join(Path(name).stem for name in SOURCE_FILES)}",
                   "-m", "pytest", "-q", "-p", "no:cacheprovider", "--disable-warnings",
                   f"--junitxml={junit}", *TEST_FILES, "-k", TEST_SELECTOR]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        run = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, check=False)
        if run.returncode != 0:
            raise ValueError(f"native test-gap coverage pytest failed: exit={run.returncode}; tail={run.stdout[-400:]}; stderr={run.stderr[-200:]}")
        if not junit.is_file() or not data_file.is_file():
            raise ValueError("coverage run did not produce JUnit and tracer data")
        suite = ET.parse(junit).getroot()
        suites = [suite] if suite.tag == "testsuite" else list(suite.iter("testsuite"))
        tests = int(sum(int(x.get("tests", 0)) for x in suites))
        failures = sum(int(x.get("failures", 0)) + int(x.get("errors", 0)) for x in suites)
        skipped = sum(int(x.get("skipped", 0)) for x in suites)
        if tests < len(TEST_FILES) or failures or skipped:
            raise ValueError("coverage test receipt lacks passing executed tests")
        tracer = coverage.Coverage(data_file=str(data_file))
        tracer.load()
        report = temp / "coverage.json"
        tracer.json_report(outfile=str(report), show_contexts=False)
        values = json.loads(report.read_text(encoding="utf-8"))
        module_rows: dict[str, dict[str, Any]] = {}
        for name in SOURCE_FILES:
            item = values.get("files", {}).get(name)
            if isinstance(item, dict):
                summary = item["summary"]
                missing = sorted(int(v) for v in item["missing_lines"])
                total = int(summary["num_statements"])
                covered = int(summary["covered_lines"])
                traced = True
                branches = [list(pair) for pair in item.get("missing_branches", [])]
            else:
                # Coverage JSON omits modules not imported by selected tests.
                # Declare a zero-covered module based on Coverage.py's own
                # executable-statement analysis, never silently omit gaps.
                _file, executable, _excluded, uncovered, _formatted = tracer.analysis2(str(root / name))
                total = len(executable)
                missing = sorted(int(v) for v in uncovered)
                covered = 0
                traced = False
                branches = None
            if total < 1 or covered + len(missing) != total or any(n < 1 for n in missing):
                raise ValueError(f"coverage statement count inconsistent: {name}")
            module_rows[name] = {
                "source_sha256": identities_before[name],
                "statements": total, "covered_lines": covered,
                "missing_lines": missing, "missing_line_count": len(missing),
                "percent_covered": round(100.0 * covered / total, 4),
                "missing_branches": branches,
                "imported_by_selected_tests": traced,
            }
        if _inputs(root) != identities_before:
            raise ValueError("source or test file mutated during test-gap collection")
        proof = {
            "schema": SCHEMA,
            "status": "PASS",
            "capability": "test-gap-analysis",
            "native_function_executed": "coverage.Coverage.json_report / pytest",
            "consumer": "smart_test_gap_analysis.verify_test_gap",
            "python_test_files_executed": list(TEST_FILES),
            "pytest_selection_expression": TEST_SELECTOR,
            "junit_tests": tests, "junit_failures": failures, "junit_skipped": skipped,
            "input_files_sha256": identities_before,
            "source_module_coverage": module_rows,
            "total_missing_lines": sum(x["missing_line_count"] for x in module_rows.values()),
            "observability_scope": "ENGINEERING_TESTS_ONLY",
            "external_skill_code_executed": False,
            "predictive_weight_authorized": False,
            "prospective_superiority_proven": False,
        }
        proof["execution_sha256"] = _hash(proof)
        return proof


def verify_test_gap(report: dict[str, Any], root: str | Path) -> dict[str, Any]:
    """Consume and check a persisted receipt; never equate uncovered lines to bugs."""
    root = Path(root).resolve()
    if report.get("schema") != SCHEMA or report.get("status") != "PASS":
        raise ValueError("invalid native test-gap report")
    unsigned = dict(report)
    signed = unsigned.pop("execution_sha256", None)
    if signed != _hash(unsigned):
        raise ValueError("test-gap evidence receipt SHA mismatch")
    if (report.get("capability") != "test-gap-analysis"
            or report.get("consumer") != "smart_test_gap_analysis.verify_test_gap"
            or report.get("predictive_weight_authorized") is not False
            or report.get("external_skill_code_executed") is not False
            or report.get("prospective_superiority_proven") is not False):
        raise ValueError("test-gap receipt authority or consumer invalid")
    if (report.get("python_test_files_executed") != list(TEST_FILES)
            or report.get("pytest_selection_expression") != TEST_SELECTOR):
        raise ValueError("test-gap test suite does not match approved manifest")
    if report.get("input_files_sha256") != _inputs(root):
        raise ValueError("test-gap receipt bound to different source snapshot")
    if report.get("junit_tests", 0) < 1 or report.get("junit_failures") != 0 or report.get("junit_skipped") != 0:
        raise ValueError("test-gap execution did not pass")
    rows = report.get("source_module_coverage", {})
    if not isinstance(rows, dict) or set(rows) != set(SOURCE_FILES):
        raise ValueError("test-gap source module coverage incomplete")
    misses = 0
    for name, row in rows.items():
        if row.get("source_sha256") != report["input_files_sha256"][name]:
            raise ValueError("test-gap source binding differs")
        missing = row.get("missing_lines")
        covered, total = row.get("covered_lines"), row.get("statements")
        if (not isinstance(missing, list) or not all(isinstance(n, int) and n > 0 for n in missing)
                or len(set(missing)) != len(missing) or missing != sorted(missing)
                or not isinstance(covered, int) or not isinstance(total, int)
                or covered + len(missing) != total
                or row.get("missing_line_count") != len(missing)
                or round(100 * covered / total, 4) != row.get("percent_covered")):
            raise ValueError("test-gap measured coverage invalid")
        misses += len(missing)
    if report.get("total_missing_lines") != misses:
        raise ValueError("test-gap uncovered-line total invalid")
    return {
        "status": "NATIVE_EXECUTION_CONSUMED_VERIFIED",
        "capability": "test-gap-analysis",
        "execution_sha256": signed,
        "consumer": "smart_test_gap_analysis.verify_test_gap",
        "tested_modules": len(rows),
        "observed_missing_lines": misses,
        "tests_passed": report["junit_tests"],
        "predictive_weight_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute/consume real engineering test-gap evidence")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if bool(args.write) == bool(args.check):
        parser.error("specify exactly one of --write or --check")
    if args.write:
        out = root / args.write
        if out.resolve().parent != root:
            raise ValueError("test-gap evidence output must be at canonical root")
        payload = execute_test_gap(root)
        verify_test_gap(payload, root)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = {"status": "RECORDED", "path": out.name,
                  "consumed": verify_test_gap(payload, root)}
    else:
        source = root / args.check
        if source.resolve().parent != root or not source.is_file():
            raise ValueError("test-gap evidence missing or outside canonical root")
        result = verify_test_gap(json.loads(source.read_text(encoding="utf-8")), root)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
