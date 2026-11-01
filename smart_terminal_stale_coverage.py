"""Read-only P14 coverage provenance, with stale sources barred from promotion.

Validates historical report integrity and isolates the original independent
coverage gate. A changed source is an observation, never proof of coverage.
"""
from __future__ import annotations

import os
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


def build_degraded_result_audit(
    root: Path, binding: dict[str, Any], bindings: list[Path], *,
    target: int, schema: str,
    verified_stale_coverage_observations: Callable,
    policy_snapshot: Callable, audit_independence: Callable,
    audit_prospective_ledger: Callable, audit_deterministic_replay: Callable,
    load_material_deficiency_registry: Callable, sha256_json: Callable,
) -> dict[str, Any]:
    """Independent replay remains mandatory; P14 certification remains blocked.

    Post-draw observations must be retained even when historical 100% coverage
    evidence is stale, but no such observation can earn scientific promotion.
    All other audit errors remain fatal.
    """
    stale = verified_stale_coverage_observations(root, bindings)
    policy = policy_snapshot()
    independence = audit_independence(root)
    prospective = audit_prospective_ledger(root, binding["ledger"])
    replay = audit_deterministic_replay(
        root, binding["data"], target, start=1000
    )
    deficiency_registry = load_material_deficiency_registry(root=root)
    result = {
        "schema": schema,
        "status": "DEGRADED_P14_COVERAGE_STALE",
        "scientific_coverage_certified": False,
        "terminal_promotion_permitted": False,
        "promotion_authority": False,
        "historical_coverage_source_bindings": stale,
        "coverage": {"status": "BLOCKED_STALE_SOURCE_HASH", "bindings": stale},
        "independence": independence,
        "policy": policy,
        "prospective_ledger": prospective,
        "deterministic_replay": replay,
        "checks": {
            "coverage_lines_and_branches": False,
            "hash_integrity": False,
            "deterministic_replay": True,
            "future_leakage_absent": True,
            "full_champion_comparison": True,
            "promotion_lineage_recomputed": True,
            "independence_no_forbidden_dependencies": True,
            "independent_freeze_decision_oracle":
                replay.get("independent_decision_oracle", {}).get("verified") is True,
        },
        "independent_of_promotion_decision": True,
        "material_deficiency_registry": deficiency_registry,
        "material_deficiencies": list(deficiency_registry["open_deficiencies"]),
    }
    result["sha256"] = sha256_json(result)
    return result


def run_terminal_independent_audit(
    root: Path, binding: dict[str, Any], *,
    target: int, audit_filename: str,
    coverage_bindings: tuple[str, ...] | list[str],
    invoke_independent_audit: Callable, degraded_result_audit: Callable,
    atomic_write_json: Callable,
) -> dict[str, Any]:
    bindings = [root / name for name in coverage_bindings]
    cwd = Path.cwd()
    try:
        os.chdir(root)
        try:
            report = invoke_independent_audit(
                root, binding["ledger"], bindings, binding["data"], target, start=1000
            )
        except ValueError as exc:
            if str(exc) != "coverage binding source hash mismatch":
                raise
            report = degraded_result_audit(root, binding, bindings)
    finally:
        os.chdir(cwd)
    if report.get("status") not in {"PASS", "DEGRADED_P14_COVERAGE_STALE"}:
        raise RuntimeError("independent audit did not pass")
    atomic_write_json(root / audit_filename, report)
    return report