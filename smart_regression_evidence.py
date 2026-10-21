from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
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
