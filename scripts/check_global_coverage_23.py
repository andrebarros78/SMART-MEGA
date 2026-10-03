from __future__ import annotations

import hashlib
import json
from pathlib import Path

from smart_global_integrity import REQUIRED_GLOBAL_COVERAGE_SOURCES
from smart_source_identity import sha256_source_file

REPORT_PATH = Path("SMART_COVERAGE_GLOBAL_CURRENT.json")
AUDIT_PATH = Path("SMART_COVERAGE_23_AUDIT.json")
SCHEMA = "SMART_GLOBAL_COVERAGE_23_AUDIT_1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    branch_coverage = report.get("meta", {}).get("branch_coverage") is True
    files = report.get("files", {})

    rows: list[dict[str, object]] = []
    failed: list[str] = []

    for source in REQUIRED_GLOBAL_COVERAGE_SOURCES:
        row = files.get(source)
        if not isinstance(row, dict):
            item = {
                "source": source,
                "status": "FAIL",
                "reason": "source_missing_from_report",
            }
            rows.append(item)
            failed.append(source)
            print(f"FAIL {source}: source missing from report")
            continue

        summary = row.get("summary", {})
        covered_lines = int(summary.get("covered_lines", -1))
        statements = int(summary.get("num_statements", -2))
        missing_lines = int(summary.get("missing_lines", -1))
        covered_branches = int(summary.get("covered_branches", -1))
        branches = int(summary.get("num_branches", -2))
        missing_branches = int(summary.get("missing_branches", -1))

        ok = (
            branch_coverage
            and missing_lines == 0
            and missing_branches == 0
            and covered_lines == statements
            and covered_branches == branches
        )
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed.append(source)

        source_path = Path(source)
        item = {
            "source": source,
            "status": status,
            "source_sha256": sha256_source_file(source_path) if source_path.is_file() else None,
            "covered_lines": covered_lines,
            "statements": statements,
            "missing_lines": missing_lines,
            "covered_branches": covered_branches,
            "branches": branches,
            "missing_branches": missing_branches,
            "missing_line_numbers": row.get("missing_lines", []),
            "missing_branch_pairs": row.get("missing_branches", []),
        }
        rows.append(item)
        print(
            f"{status} {source}: lines {covered_lines}/{statements} "
            f"branches {covered_branches}/{branches}"
        )

    payload = {
        "schema": SCHEMA,
        "status": "PASS" if not failed and branch_coverage else "FAIL",
        "coverage_report": str(REPORT_PATH),
        "coverage_report_sha256": _sha256_file(REPORT_PATH),
        "branch_coverage": branch_coverage,
        "required_count": len(REQUIRED_GLOBAL_COVERAGE_SOURCES),
        "passed_count": len(REQUIRED_GLOBAL_COVERAGE_SOURCES) - len(failed),
        "failed_count": len(failed),
        "failed_sources": failed,
        "rows": rows,
    }
    AUDIT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"GLOBAL_COVERAGE_23={payload['status']} "
        f"passed={payload['passed_count']}/{payload['required_count']}"
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
