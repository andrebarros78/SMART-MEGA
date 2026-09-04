from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
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
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag == "testsuites" and root.attrib.get("tests") is not None:
        tests = int(root.attrib.get("tests", 0))
        failures = int(root.attrib.get("failures", 0))
        errors = int(root.attrib.get("errors", 0))
        skipped = int(root.attrib.get("skipped", 0))
    else:
        tests = sum(int(s.attrib.get("tests", 0)) for s in suites)
        failures = sum(int(s.attrib.get("failures", 0)) for s in suites)
        errors = sum(int(s.attrib.get("errors", 0)) for s in suites)
        skipped = sum(int(s.attrib.get("skipped", 0)) for s in suites)
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "status": "PASS" if failures == 0 and errors == 0 and tests > 0 else "FAIL",
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
