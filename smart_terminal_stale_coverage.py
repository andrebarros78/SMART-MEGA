"""Read-only P14 coverage provenance, with stale sources barred from promotion.

Validates historical report integrity and isolates the original independent
coverage gate. A changed source is an observation, never proof of coverage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def verified_stale_coverage_observations(
    root: Path, bindings: list[Path], *, read_json: Callable,
    sha256_file: Callable, sha256_source_file: Callable,
    coverage_binding_schema: str, audit_coverage_binding: Callable,
) -> list[dict[str, Any]]:
    """Record old P14 coverage as STALE evidence, never new source coverage."""
    observed = []
    for path in bindings:
        path = Path(path).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.is_symlink():
            raise ValueError("P14 coverage binding path is unsafe")
        doc = read_json(path)
        if doc.get("schema") != coverage_binding_schema:
            raise ValueError("P14 coverage binding schema invalid")
        raw_source = doc.get("source_file")
        raw_report = doc.get("coverage_report_file")
        if (not isinstance(raw_source, str) or not isinstance(raw_report, str)
                or Path(raw_source).is_absolute() or Path(raw_report).is_absolute()):
            raise ValueError("P14 coverage source/report path invalid")
        source = (root / raw_source).resolve()
        report = (root / raw_report).resolve()
        if (not source.is_relative_to(root.resolve()) or not report.is_relative_to(root.resolve())
                or not source.is_file() or not report.is_file()
                or source.is_symlink() or report.is_symlink()):
            raise ValueError("P14 coverage evidence path is unsafe or missing")
        if sha256_file(report) != doc.get("coverage_report_sha256"):
            raise ValueError("P14 coverage historical report hash mismatch")
        old_hash = doc.get("source_sha256")
        live_hash = sha256_source_file(source)
        if old_hash == live_hash:
            # A current source must still pass the ORIGINAL 100% P14 gate.
            audit_coverage_binding(root, path)
        observed.append({
            "binding_file": path.relative_to(root).as_posix(),
            "historical_source_sha256": old_hash,
            "current_source_sha256": live_hash,
            "source_file": source.relative_to(root).as_posix(),
            "report_sha256_verified": True,
            "current_source_coverage_proven": old_hash == live_hash,
        })
    if not any(not row["current_source_coverage_proven"] for row in observed):
        raise RuntimeError("cannot classify a fully current P14 coverage set as stale")
    return observed