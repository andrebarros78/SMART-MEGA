from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

QUALITY_SCHEMA = "SMART_DRAW_DATA_QUALITY_V1"
DRAW_COLUMNS = tuple(f"Bola{i}" for i in range(1, 7))


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class DataQualityReport:
    schema: str
    status: str
    file: str
    file_sha256: str
    row_count: int
    contest_min: int | None
    contest_max: int | None
    required_columns_present: bool
    null_cell_count: int
    duplicate_contest_count: int
    out_of_order_count: int
    invalid_draw_count: int
    non_integer_value_count: int
    future_contest_count: int
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_draw_file(path: str | Path, expected_max_contest: int | None = None) -> DataQualityReport:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    df = pd.read_excel(file_path)
    required = ("Concurso",) + DRAW_COLUMNS
    required_present = all(c in df.columns for c in required)
    if not required_present:
        missing = [c for c in required if c not in df.columns]
        raise ValueError(f"required draw columns missing: {missing}")

    work = df.loc[:, required].copy()
    null_count = int(work.isna().sum().sum())
    duplicate_contests = int(work["Concurso"].duplicated(keep=False).sum())

    contest_numeric = pd.to_numeric(work["Concurso"], errors="coerce")
    draw_numeric = work.loc[:, DRAW_COLUMNS].apply(pd.to_numeric, errors="coerce")
    non_integer = int(contest_numeric.isna().sum() + draw_numeric.isna().sum().sum())
    if non_integer == 0:
        contest_non_integral = (contest_numeric % 1 != 0)
        draw_non_integral = (draw_numeric % 1 != 0)
        non_integer += int(contest_non_integral.sum() + draw_non_integral.sum().sum())

    contests = contest_numeric.dropna().astype(int).tolist()
    out_of_order = sum(1 for a, b in zip(contests, contests[1:]) if b <= a)

    invalid_draws = 0
    if len(draw_numeric) > 0:
        for row in draw_numeric.itertuples(index=False, name=None):
            if any(pd.isna(v) for v in row):
                invalid_draws += 1
                continue
            vals = [float(v) for v in row]
            if any(v % 1 != 0 for v in vals):
                invalid_draws += 1
                continue
            ints = [int(v) for v in vals]
            if len(set(ints)) != 6 or min(ints) < 1 or max(ints) > 60:
                invalid_draws += 1

    future_count = 0
    if expected_max_contest is not None:
        future_count = int((contest_numeric > expected_max_contest).fillna(False).sum())

    checks = {
        "required_columns": required_present,
        "no_nulls": null_count == 0,
        "unique_contests": duplicate_contests == 0,
        "strictly_increasing_contests": out_of_order == 0,
        "integer_values": non_integer == 0,
        "valid_six_unique_numbers_1_to_60": invalid_draws == 0,
        "cutoff_respected": future_count == 0,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return DataQualityReport(
        schema=QUALITY_SCHEMA,
        status=status,
        file=file_path.name,
        file_sha256=sha256_file(file_path),
        row_count=int(len(work)),
        contest_min=min(contests) if contests else None,
        contest_max=max(contests) if contests else None,
        required_columns_present=required_present,
        null_cell_count=null_count,
        duplicate_contest_count=duplicate_contests,
        out_of_order_count=int(out_of_order),
        invalid_draw_count=int(invalid_draws),
        non_integer_value_count=int(non_integer),
        future_contest_count=future_count,
        checks=checks,
    )


def enforce_draw_quality(path: str | Path, expected_max_contest: int | None = None) -> DataQualityReport:
    report = audit_draw_file(path, expected_max_contest=expected_max_contest)
    if report.status != "PASS":
        failed = [name for name, ok in report.checks.items() if not ok]
        raise ValueError(f"draw data quality gate failed: {failed}")
    return report


__all__ = ["DataQualityReport", "audit_draw_file", "enforce_draw_quality", "sha256_file"]
