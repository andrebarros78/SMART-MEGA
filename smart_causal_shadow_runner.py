from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import freeze_next_research as champion_engine
import smart_v2_engine as engine
from smart_champion_challenger import source_cutoff_timestamp
from smart_data_quality_gate import enforce_draw_quality
from smart_independent_oracle import validate_prediction_snapshot
from smart_learning_activation_authority import load_activation_authority
from smart_learning_epoch_reset import ACTIVE_PATH, verify_active_epoch
from smart_procedural_actionability_gate import evaluate_freeze_window
from smart_signal_agent import SmartSignalAgent
from smart_target_schedule import resolve_target_schedule

SCHEMA = "SMART_CAUSAL_SHADOW_EXECUTION_1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"shadow path escapes project root: {value}") from exc
    return path


def run_causal_shadow(root: str | Path = ".", start: int = 1000, *, observed_at: str | None = None,
                      write_proof: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    active_path = root / ACTIVE_PATH
    active_before_sha = _sha256_file(active_path)
    active = verify_active_epoch(active_path)
    if active.get("status") != "RESET_READY":
        raise ValueError("causal shadow requires RESET_READY active epoch")

    paths = active["state_paths"]
    ledger_path = _resolve(root, str(paths["ledger"]))
    data_path = _resolve(root, str(active["data_file"]))
    activation_authority_path = _resolve(root, str(paths["activation_authority"]))
    ledger_before_sha = _sha256_file(ledger_path)

    target = int(active["target_contest"])
    cutoff = int(active["cutoff_contest"])
    draws, contests = engine.load_draws(data_path)
    if int(contests[-1]) != cutoff or cutoff != target - 1:
        raise ValueError("causal shadow cutoff/target mismatch")
    if int(contests[-1]) >= target:
        raise ValueError("causal shadow target result is present in data")
    if _sha256_file(data_path) != str(active["data_sha256"]):
        raise ValueError("causal shadow immutable data hash mismatch")

    quality = enforce_draw_quality(data_path, expected_max_contest=cutoff)
    schedule = resolve_target_schedule(root, target)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    freeze_window = evaluate_freeze_window(
        scheduled_datetime=str(schedule["scheduled_datetime"]),
        observed_at=observed,
    )
    if freeze_window.freeze_authority_allowed:
        raise ValueError("causal shadow is reserved for a closed freeze-authority window")

    source_ts = source_cutoff_timestamp(data_path)
    signal_ts = source_ts or observed
    signal_ts_kind = "source_draw_datetime" if source_ts else "shadow_generation_utc_source_draw_datetime_unavailable"
    champion = champion_engine.current_policy(draws, start=int(start))
    activation = load_activation_authority(activation_authority_path, target_contest=target, root=root)
    agent = SmartSignalAgent(
        start=int(start),
        marginal_strength=activation.marginal_strength,
        allow_meta_alternate_selection=activation.allow_meta_alternate_selection,
        activation_decision=activation.decision,
    )
    challenger, backtest = agent.predict_next(
        draws,
        contests,
        target_contest=target,
        cutoff_timestamp=signal_ts,
        cutoff_timestamp_kind=signal_ts_kind,
    )
    challenger_doc = challenger.as_dict()
    oracle = validate_prediction_snapshot(challenger_doc)
    if oracle.get("status") != "PASS" or oracle.get("verified") is not True:
        raise RuntimeError("causal shadow independent oracle verification failed")

    stable = {
        "target_contest": target,
        "cutoff_contest": cutoff,
        "data_sha256": _sha256_file(data_path),
        "start_index": int(start),
        "champion_top6": list(champion["top6"]),
        "challenger_top6": list(challenger_doc["top6"]),
        "governed_challenger_top6": list(challenger_doc["meta_governor"]["selected_top6"]),
        "governed_policy": challenger_doc["meta_governor"]["selected_policy"],
        "weights": challenger_doc["weights"],
        "ranking60": challenger_doc["ranking60"],
    }
    decision_sha = _sha256_json(stable)
    doc = {
        "schema": SCHEMA,
        "status": "PASS",
        "execution_mode": "CAUSAL_SHADOW_NO_FREEZE_AUTHORITY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": target,
        "cutoff_contest": cutoff,
        "schedule": schedule,
        "freeze_window": freeze_window.to_dict(),
        "data_file": str(data_path.relative_to(root)).replace("\\", "/"),
        "data_sha256": _sha256_file(data_path),
        "result_used": False,
        "target_result_present_in_data": False,
        "freeze_created": False,
        "prospective_authority": False,
        "ledger_mutation_allowed": False,
        "state_mutation_allowed": False,
        "champion_top6": stable["champion_top6"],
        "challenger_top6": stable["challenger_top6"],
        "governed_challenger_top6": stable["governed_challenger_top6"],
        "governed_policy": stable["governed_policy"],
        "decision_sha256": decision_sha,
        "independent_oracle": oracle,
        "data_quality_status": quality.status,
        "historical_backtest_summary": {k: v for k, v in backtest.items() if k != "rows"},
        "checks": {
            "causal_cutoff_exact": int(contests[-1]) == cutoff == target - 1,
            "target_result_absent": int(contests[-1]) < target,
            "freeze_window_closed": freeze_window.freeze_authority_allowed is False,
            "oracle_verified": oracle.get("verified") is True,
            "ledger_unchanged": _sha256_file(ledger_path) == ledger_before_sha,
            "active_epoch_unchanged": _sha256_file(active_path) == active_before_sha,
        },
    }
    if not all(doc["checks"].values()):
        raise RuntimeError(f"causal shadow invariant failure: {doc['checks']}")
    canonical = dict(doc)
    doc["sha256"] = _sha256_json(canonical)
    if write_proof:
        out = ledger_path.parent / f"SMART_{target}_CAUSAL_SHADOW_EXECUTION.json"
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        doc["proof_file"] = str(out.relative_to(root)).replace("\\", "/")
        doc["proof_file_sha256"] = _sha256_file(out)
    return doc


def verify_determinism(root: str | Path = ".", start: int = 1000, *, observed_at: str | None = None) -> dict[str, Any]:
    first = run_causal_shadow(root, start, observed_at=observed_at, write_proof=False)
    second = run_causal_shadow(root, start, observed_at=observed_at, write_proof=False)
    same = first["decision_sha256"] == second["decision_sha256"] and first["challenger_top6"] == second["challenger_top6"]
    if not same:
        raise RuntimeError("causal shadow decision is not deterministic")
    return {
        "status": "PASS",
        "decision_sha256": first["decision_sha256"],
        "challenger_top6": first["challenger_top6"],
        "champion_top6": first["champion_top6"],
        "runs": 2,
        "deterministic": True,
    }


if __name__ == "__main__":
    result = run_causal_shadow(Path(__file__).resolve().parent)
    print(json.dumps({
        "status": result["status"],
        "mode": result["execution_mode"],
        "target_contest": result["target_contest"],
        "champion_top6": result["champion_top6"],
        "challenger_top6": result["challenger_top6"],
        "decision_sha256": result["decision_sha256"],
        "prospective_authority": result["prospective_authority"],
    }, ensure_ascii=False, indent=2))
