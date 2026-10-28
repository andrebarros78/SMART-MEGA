from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
import re
from defusedxml import ElementTree as ET
from pathlib import Path
from typing import Any

SCHEMA = "SMART_REGRESSION_EVIDENCE_PROMOTION_1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def junit_summary(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("unsupported JUnit root")

    def observed_counts(node) -> dict[str, int]:
        cases = list(node.iter("testcase"))
        return {
            "tests": len(cases),
            "failures": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }

    counts = observed_counts(root)
    consistent = True
    for node in root.iter():
        if node.tag not in {"testsuite", "testsuites"}:
            continue
        observed = observed_counts(node)
        for name, count in observed.items():
            if name in node.attrib:
                try:
                    consistent = consistent and int(node.attrib[name]) == count
                except ValueError:
                    consistent = False
    tests, failures, errors, skipped = (counts[name] for name in ("tests", "failures", "errors", "skipped"))
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "status": "PASS" if consistent and failures == 0 and errors == 0 and skipped == 0 and tests > 0 else "FAIL",
        "sha256": sha256_file(path),
    }


def normalize_pytest_subtest_junit(
    original: Path, terminal_log: Path, normalized: Path
) -> dict[str, Any]:
    """Repair only a Pytest subtests suite-count discrepancy, never test outcomes.

    Pytest may include successful subtests in testsuite@tests but not serialize
    them as separate testcase nodes. Strict certification must still reject
    malformed JUnit. This explicit, provenance-bound conversion preserves the
    original and refuses discrepancies not corroborated by the terminal log.
    """
    original, terminal_log, normalized = map(Path, (original, terminal_log, normalized))
    for source in (original, terminal_log):
        if not source.is_file() or source.is_symlink():
            raise ValueError("original JUnit and terminal log must be regular files")
        if source.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("JUnit normalization input exceeds safe size")
    if normalized.absolute() in {original.absolute(), terminal_log.absolute()}:
        raise ValueError("normalized JUnit must be a distinct new file")
    if normalized.is_symlink() or normalized.exists():
        raise FileExistsError(normalized)

    raw = original.read_bytes()
    doc = ET.fromstring(raw)
    if doc.tag != "testsuites" or "tests" in doc.attrib:
        raise ValueError("only Pytest's single-suite JUnit layout is supported")
    suites = list(doc)
    if len(suites) != 1 or suites[0].tag != "testsuite":
        raise ValueError("exactly one JUnit testsuite is required")
    suite = suites[0]
    cases = list(suite.iter("testcase"))
    actual_tests = len(cases)
    if actual_tests <= 0:
        raise ValueError("JUnit must include serialized testcase nodes")
    if any(node.find(label) is not None for node in cases
           for label in ("failure", "error", "skipped")):
        raise ValueError("failed, errored or skipped testcases cannot be normalized")
    try:
        if any(int(suite.attrib.get(name, "-1")) != 0
               for name in ("failures", "errors", "skipped")):
            raise ValueError("nonzero or absent JUnit outcome metadata")
        declared_tests = int(suite.attrib["tests"])
    except (KeyError, TypeError) as exc:
        raise ValueError("missing JUnit suite tests count") from exc

    log_raw = terminal_log.read_bytes()
    try:
        log_text = (log_raw.decode("utf-16") if log_raw[:2] in (b"\xff\xfe", b"\xfe\xff")
                    else log_raw.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValueError("unsupported Pytest terminal log encoding") from exc
    lines = [line.strip() for line in log_text.splitlines()
             if re.search(r"\b\d+ subtests passed\b", line)]
    if len(lines) != 1:
        raise ValueError("single Pytest terminal summary with subtests required")
    summary_line = lines[0]
    passed = re.search(r"(?<!\w)(\d+) passed\b", summary_line)
    subtests = re.search(r"\b(\d+) subtests passed\b", summary_line)
    if re.search(r"\b[1-9]\d*\s+deselected\b", summary_line):
        raise ValueError("Pytest terminal summary contains deselected tests")
    if (passed is None or subtests is None
            or re.search(r"\b[1-9]\d*\s+(?:failed|errors?|skipped)\b", summary_line)):
        raise ValueError("Pytest terminal summary is not a clean passing run")
    passed_count = int(passed.group(1))
    subtest_count = int(subtests.group(1))
    if (passed_count != actual_tests or subtest_count <= 0
            or declared_tests != actual_tests + subtest_count):
        raise ValueError("JUnit and Pytest subtest counts are not corroborated")

    # Do not reinterpret or silently relax junit_summary. Change exactly one
    # attribute in the original XML bytes and preserve all testcase nodes.
    start_tags = list(re.finditer(rb"<testsuite(?=[\s>])[^>]*>", raw))
    if len(start_tags) != 1:
        raise ValueError("exactly one concrete testsuite opening tag required")
    tag = start_tags[0].group(0)
    old = b'tests="' + str(declared_tests).encode("ascii") + b'"'
    new = b'tests="' + str(actual_tests).encode("ascii") + b'"'
    if tag.count(old) != 1:
        raise ValueError("JUnit suite tests count cannot be replaced unambiguously")
    changed_tag = tag.replace(old, new, 1)
    converted = raw[:start_tags[0].start()] + changed_tag + raw[start_tags[0].end():]
    if converted.replace(changed_tag, tag, 1) != raw:
        raise RuntimeError("source JUnit bytes not preserved by metadata-only conversion")
    checked = ET.fromstring(converted)
    if (len(list(checked.iter("testcase"))) != actual_tests
            or int(checked.find("testsuite").attrib["tests"]) != actual_tests):
        raise RuntimeError("converted JUnit testcase structure invalid")
    with normalized.open("xb") as output:
        output.write(converted)
    try:
        after = junit_summary(normalized)
        if (after["status"] != "PASS" or after["tests"] != actual_tests
                or any(after[key] for key in ("failures", "errors", "skipped"))
                or original.read_bytes() != raw):
            raise RuntimeError("normalized candidate did not pass strict JUnit validation")
    except Exception:
        normalized.unlink()
        raise
    return {
        "schema": "SMART_PYTEST_SUBTEST_JUNIT_METADATA_NORMALIZATION_1",
        "status": "PASS_METADATA_ONLY",
        "original_junit_sha256": hashlib.sha256(raw).hexdigest(),
        "terminal_log_sha256": hashlib.sha256(log_raw).hexdigest(),
        "normalized_junit_sha256": after["sha256"],
        "serialized_testcases": actual_tests,
        "reported_total_before": declared_tests,
        "subtests": subtest_count,
        "original_unchanged": True,
        "testcases_unchanged": True,
        "product_certification_performed": False,
    }

def promote(candidate: Path, current: Path) -> dict[str, Any]:
    candidate = Path(candidate)
    current = Path(current)
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    summary = junit_summary(candidate)
    if summary["status"] != "PASS":
        raise ValueError("candidate regression evidence is not green")
    current.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=current.name + ".", suffix=".tmp", dir=current.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        shutil.copyfile(candidate, temp)
        if sha256_file(temp) != summary["sha256"]:
            raise RuntimeError("temporary regression evidence hash mismatch")
        os.replace(temp, current)
    finally:
        if temp.exists():
            temp.unlink()
    if sha256_file(current) != summary["sha256"]:
        raise RuntimeError("promoted regression evidence hash mismatch")
    return {"schema": SCHEMA, "candidate": str(candidate), "current": str(current), **summary}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default="SMART_AUDIT_JUNIT_CANDIDATE.xml")
    parser.add_argument("--current", default="SMART_AUDIT_JUNIT_CURRENT.xml")
    args = parser.parse_args()
    import json
    print(json.dumps(promote(Path(args.candidate), Path(args.current)), ensure_ascii=False))


if __name__ == "__main__":
    main()
