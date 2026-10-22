"""Read-only comparison of immutable consecutive SMART-MEGA model freezes.

Never updates weights, generated cards, lifecycle, or scientific authority.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError(f"invalid JSON object: {path}")
    return obj


def _ranking_changes(first: list, second: list) -> dict:
    a, b = [int(n) for n in first], [int(n) for n in second]
    if len(a) != 60 or set(a) != set(range(1, 61)) or len(b) != 60 or set(b) != set(range(1, 61)):
        raise ValueError("incomplete ranking of the 60 numbers")
    positions = {n: i for i, n in enumerate(a)}
    moves = {n: abs(positions[n] - i) for i, n in enumerate(b)}
    return {
        "numbers_changing_rank": sum(v > 0 for v in moves.values()),
        "sum_absolute_rank_moves": sum(moves.values()),
        "maximum_rank_move": max(moves.values()),
        "top6_changed": sorted(a[:6]) != sorted(b[:6]),
    }


def _weight_changes(first: dict, second: dict) -> dict:
    a, b = {str(k): float(v) for k, v in first.items()}, {str(k): float(v) for k, v in second.items()}
    if set(a) != set(b):
        raise ValueError("cannot compare changing signal universes")
    diff = {k: abs(a[k] - b[k]) for k in sorted(a)}
    return {
        "signals": len(diff),
        "signals_changing_weight": sum(x > 1e-12 for x in diff.values()),
        "total_absolute_weight_change": sum(diff.values()),
        "largest_weight_change": max(diff.items(), key=lambda kv: kv[1]),
    }


def audit(root: Path) -> dict:
    root = Path(root).resolve()
    freezes = []
    for path in sorted((root / "runtime" / "learning_epochs").glob("operator-*/SMART_*_CHAMPION_CHALLENGER_FREEZE.json")):
        obj = _read(path)
        target = obj.get("target_contest")
        if type(target) is not int:
            continue
        primary = path.with_name(f"SMART_{target}_PRIMARY_CARD.json")
        if not primary.is_file():
            continue
        card = _read(primary)
        if card.get("freeze_sha256") != _sha(path):
            raise ValueError(f"primary card freeze linkage invalid for {target}")
        freezes.append((target, path, obj, card))
    freezes.sort(key=lambda record: record[0])
    if len(freezes) != len({r[0] for r in freezes}):
        raise ValueError("duplicate model freeze for one target")
    snapshots = []
    for target, path, obj, card in freezes:
        champion = obj["champion"]
        challenger = obj["challenger"]
        snapshots.append({
            "target": target,
            "cutoff": int(obj["cutoff_contest"]),
            "data_sha256": obj["data_sha256"],
            "champion_engine_sha256": obj["champion_engine_sha256"],
            "signal_agent_sha256": obj["signal_agent_sha256"],
            "champion": {"top6": [int(x) for x in champion["top6"]],
                         "ranking60": champion["ranking60"],
                         "expert_weights": champion["expert_weights"]},
            "challenger": {"top6": [int(x) for x in challenger["top6"]],
                           "ranking60": challenger["ranking60"],
                           "weights": challenger["weights"]},
            "primary_card": [int(x) for x in card["numbers"]],
            "freeze_file": str(path.relative_to(root)).replace("\\", "/"),
        })
    transitions = []
    for before, after in zip(snapshots, snapshots[1:]):
        gap = after["cutoff"] - before["cutoff"]
        transitions.append({
            "from_target": before["target"],
            "to_target": after["target"],
            "ingested_results_between_freezes": gap,
            "single_result_attributable": gap == 1,
            "source_dataset_changed": before["data_sha256"] != after["data_sha256"],
            "same_champion_engine": before["champion_engine_sha256"] == after["champion_engine_sha256"],
            "same_signal_agent": before["signal_agent_sha256"] == after["signal_agent_sha256"],
            "champion_weights": _weight_changes(before["champion"]["expert_weights"], after["champion"]["expert_weights"]),
            "challenger_weights": _weight_changes(before["challenger"]["weights"], after["challenger"]["weights"]),
            "champion_ranking": _ranking_changes(before["champion"]["ranking60"], after["champion"]["ranking60"]),
            "challenger_ranking": _ranking_changes(before["challenger"]["ranking60"], after["challenger"]["ranking60"]),
            "primary_card_changed": sorted(before["primary_card"]) != sorted(after["primary_card"]),
            "primary_card_numbers_before": sorted(before["primary_card"]),
            "primary_card_numbers_after": sorted(after["primary_card"]),
        })
    results = []
    for snap in snapshots:
        t = snap["target"]
        report_path = root / f"SMART_POST_RESULT_REPORT_{t}.json"
        if not report_path.is_file():
            continue
        report = _read(report_path)
        digest = report.pop("sha256", None)
        payload = json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if digest != hashlib.sha256(payload).hexdigest():
            raise ValueError(f"report self-hash invalid: {t}")
        freeze_file = root / snap["freeze_file"]
        valid_link = report.get("process_audit", {}).get("freeze_sha256") == _sha(freeze_file)
        if not valid_link:
            raise ValueError(f"report/freeze mismatch: {t}")
        actual = set(int(x) for x in report["official_result"])
        champion_hits = len(set(snap["champion"]["top6"]) & actual)
        challenger_hits = len(set(snap["challenger"]["top6"]) & actual)
        primary_hits = len(set(snap["primary_card"]) & actual)
        results.append({"target": t, "champion_hits": champion_hits,
                        "challenger_hits": challenger_hits, "primary_hits": primary_hits,
                        "challenger_minus_champion": challenger_hits - champion_hits,
                        "report_freeze_verified": True,
                        "independent_official_source_verified_by_this_audit": False})
    return {
        "schema": "SMART_LEARNING_IMPACT_AUDIT_1",
        "status": "OBSERVATION_ONLY",
        "snapshots": snapshots,
        "transitions": transitions,
        "prospective_frozen_result_comparison": results,
        "prospective_superiority_proven": False,
        "predictive_weight_authority": False,
        "freeze_authority": False,
        "mutates_state": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parent), sort_keys=True, ensure_ascii=False))
