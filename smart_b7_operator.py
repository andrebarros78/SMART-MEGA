from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_b7_champion_probability import write as write_historical
from smart_b7_prospective_freeze import write as write_freeze
from smart_b7_predictive_edge import sha256_json
from smart_target_schedule import resolve_target_schedule

SCHEMA = "SMART_B7_OPERATOR_V1"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def version(root: str | Path) -> str:
    value = (Path(root) / "VERSION").read_text(encoding="utf-8-sig").strip()
    if not value:
        raise ValueError("VERSION is empty")
    return value


def verify_freeze(root: str | Path, freeze_path: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    path = Path(freeze_path)
    if not path.is_absolute():
        path = root / path
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    observed = document.get("sha256")
    canonical = dict(document); canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed != sha256_json(canonical):
        raise ValueError("B7 prospective freeze embedded hash mismatch")
    if document.get("result_used") is not False or document.get("frozen_before_result") is not True:
        raise ValueError("B7 prospective freeze causal flags invalid")
    target = int(document.get("target_contest", -1)); cutoff = int(document.get("cutoff_contest", -1))
    if target < 2 or cutoff != target - 1:
        raise ValueError("B7 prospective freeze target/cutoff invalid")
    schedule = document.get("schedule_authority")
    if not isinstance(schedule, dict) or int(schedule.get("target_contest", -1)) != target:
        raise ValueError("B7 prospective freeze schedule authority invalid")
    if str(schedule.get("target_date")) != str(document.get("target_date")):
        raise ValueError("B7 prospective freeze schedule date mismatch")
    schedule_source = root / str(schedule.get("source_file", ""))
    if not schedule_source.is_file() or sha256_file(schedule_source) != str(schedule.get("source_sha256")):
        raise ValueError("B7 schedule source missing or hash mismatch")
    time_policy = root / str(schedule.get("draw_time_policy_file", ""))
    if not time_policy.is_file() or sha256_file(time_policy) != str(schedule.get("draw_time_policy_sha256")):
        raise ValueError("B7 draw-time policy missing or hash mismatch")
    for label, filename, expected in (
        ("data", document.get("data_file"), document.get("data_sha256")),
        ("historical", document.get("historical_report_file"), document.get("historical_report_sha256")),
        ("engine", document.get("engine_file"), document.get("engine_sha256")),
        ("calibrator", document.get("calibrator_file"), document.get("calibrator_sha256")),
        ("freezer", document.get("freezer_file"), document.get("freezer_sha256")),
    ):
        ref = root / str(filename)
        if not ref.is_file() or sha256_file(ref) != str(expected):
            raise ValueError(f"B7 {label} reference missing or hash mismatch")
    frontier = document.get("frontier_shadow_reference")
    if frontier is not None:
        ref = root / str(frontier.get("file"))
        if not ref.is_file() or sha256_file(ref) != str(frontier.get("sha256")):
            raise ValueError("B7 frontier reference missing or hash mismatch")
    canonical_prob = document.get("canonical", {}).get("probabilities", {})
    shadow_prob = document.get("shadow_challenger", {}).get("probabilities", {})
    expected_keys = {str(i) for i in range(1, 61)}
    if set(canonical_prob) != expected_keys or set(shadow_prob) != expected_keys:
        raise ValueError("B7 probability maps must contain 1..60")
    if abs(sum(float(v) for v in canonical_prob.values()) - 6.0) > 1e-9:
        raise ValueError("B7 canonical probabilities must sum to six")
    if abs(sum(float(v) for v in shadow_prob.values()) - 6.0) > 1e-9:
        raise ValueError("B7 shadow probabilities must sum to six")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "version": version(root),
        "freeze_file": path.name,
        "freeze_sha256": sha256_file(path),
        "target_contest": target,
        "cutoff_contest": cutoff,
        "canonical_mode": document["canonical"]["mode"],
        "top6": document["canonical"]["top6"],
        "result_used": False,
        "references_verified": True,
    }


def status(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    freezes = sorted(root.glob("B7_*_PROSPECTIVE_FREEZE_FINAL.json"))
    latest = None if not freezes else verify_freeze(root, freezes[-1])
    return {
        "schema": SCHEMA,
        "version": version(root),
        "root": str(root),
        "mode": "PARALLEL_PROSPECTIVE_EVIDENCE_COLLECTION",
        "latest_verified_freeze": latest,
        "predictive_advantage_claimed": False,
    }


def historical_audit(root: str | Path, data: str | Path, out: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    return write_historical(root / data if not Path(data).is_absolute() else data,
                            root / out if not Path(out).is_absolute() else out)


def freeze(root: str | Path, data: str | Path, report: str | Path, out: str | Path,
           target: int, frontier: str | Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    schedule = resolve_target_schedule(root, int(target))
    return write_freeze(
        root / data if not Path(data).is_absolute() else data,
        root / report if not Path(report).is_absolute() else report,
        root / out if not Path(out).is_absolute() else out,
        int(target),
        str(schedule["target_date"]),
        None if frontier is None else (root / frontier if not Path(frontier).is_absolute() else frontier),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="SMART-MEGA B7 operator")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    a = sub.add_parser("historical-audit"); a.add_argument("--data", default="Mega-Sena.xlsx"); a.add_argument("--out", required=True)
    f = sub.add_parser("freeze"); f.add_argument("--data", default="Mega-Sena.xlsx"); f.add_argument("--report", required=True); f.add_argument("--out", required=True); f.add_argument("--target", type=int, required=True); f.add_argument("--frontier")
    v = sub.add_parser("verify"); v.add_argument("--freeze", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    if args.action == "status": result = status(root)
    elif args.action == "historical-audit": result = historical_audit(root, args.data, args.out)
    elif args.action == "freeze": result = freeze(root, args.data, args.report, args.out, args.target, args.frontier)
    else: result = verify_freeze(root, args.freeze)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
