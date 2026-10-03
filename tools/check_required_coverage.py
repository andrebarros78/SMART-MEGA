from __future__ import annotations

import json
import sys
from pathlib import Path

from smart_global_integrity import REQUIRED_GLOBAL_COVERAGE_SOURCES


REPORT_PATH = Path("SMART_COVERAGE_GLOBAL_CURRENT.json")
SUMMARY_PATH = Path("SMART_COVERAGE_REQUIRED_SUMMARY.json")
SCHEMA = "SMART_REQUIRED_COVERAGE_SUMMARY_1"


def _coverage_row(files: dict[str, object], source: str) -> tuple[str, dict[str, object]]:
    direct = files.get(source)
    if isinstance(direct, dict):
        return source, direct

    normalized_source = source.replace("\\", "/")
    matches: list[tuple[str, dict[str, object]]] = []
    for key, value in files.items():
        if not isinstance(value, dict):
            continue
        normalized_key = str(key).replace("\\", "/")
        if normalized_key == normalized_source or normalized_key.endswith("/" + normalized_source):
            matches.append((str(key), value))
    if len(matches) != 1:
        raise ValueError(f"coverage source resolution failed for {source}: matches={len(matches)}")
    return matches[0]


def main() -> int:
    if not REPORT_PATH.is_file():
        raise SystemExit(f"coverage report missing: {REPORT_PATH}")

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if report.get("meta", {}).get("branch_coverage") is not True:
        raise SystemExit("branch coverage is not enabled")

    files = report.get("files")
    if not isinstance(files, dict):
        raise SystemExit("coverage report files map missing")

    rows: list[dict[str, object]] = []
    failures: list[str] = []

    for source in REQUIRED_GLOBAL_COVERAGE_SOURCES:
        try:
            resolved_key, row = _coverage_row(files, source)
            summary = row.get("summary")
            if not isinstance(summary, dict):
                raise ValueError("summary missing")

            covered_lines = int(summary.get("covered_lines", -1))
            statements = int(summary.get("num_statements", -2))
            missing_lines = int(summary.get("missing_lines", -1))
            covered_branches = int(summary.get("covered_branches", -1))
            branches = int(summary.get("num_branches", -2))
            missing_branches = int(summary.get("missing_branches", -1))

            passed = (
                missing_lines == 0
                and missing_branches == 0
                and covered_lines == statements
                and covered_branches == branches
            )
            status = "PASS" if passed else "FAIL"
            print(
                f"COVERAGE_REQUIRED {source} {status} "
                f"lines={covered_lines}/{statements} missing_lines={missing_lines} "
                f"branches={covered_branches}/{branches} missing_branches={missing_branches}"
            )
            rows.append(
                {
                    "source": source,
                    "resolved_key": resolved_key,
                    "status": status,
                    "covered_lines": covered_lines,
                    "statements": statements,
                    "missing_lines": missing_lines,
                    "covered_branches": covered_branches,
                    "branches": branches,
                    "missing_branches": missing_branches,
                    "missing_line_numbers": row.get("missing_lines", []),
                    "missing_branch_arcs": row.get("missing_branches", []),
                }
            )
            if not passed:
                failures.append(source)
        except Exception as exc:
            print(f"COVERAGE_REQUIRED {source} FAIL error={exc}")
            rows.append({"source": source, "status": "FAIL", "error": str(exc)})
            failures.append(source)

    payload = {
        "schema": SCHEMA,
        "report_file": str(REPORT_PATH),
        "required_count": len(REQUIRED_GLOBAL_COVERAGE_SOURCES),
        "pass_count": len(REQUIRED_GLOBAL_COVERAGE_SOURCES) - len(failures),
        "fail_count": len(failures),
        "failed_sources": failures,
        "status": "PASS" if not failures else "FAIL",
        "rows": rows,
    }
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if failures:
        print(f"REQUIRED_COVERAGE=FAIL failed={len(failures)} sources={','.join(failures)}")
        return 1
    print("REQUIRED_COVERAGE=PASS 23/23")
    return 0


if __name__ == "__main__":
    sys.exit(main())
