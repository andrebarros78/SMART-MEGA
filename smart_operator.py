from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from adjudicate_signal_challenger import adjudicate
from smart_agent_runtime import sha256_file
from smart_champion_challenger import load_ledger
from smart_full_process_pipeline import run_full_process
from smart_learning_epoch_reset import ACTIVE_PATH, SCHEMA as EPOCH_SCHEMA, write_active_epoch, verify_active_epoch
from smart_target_schedule import assert_pre_draw_window, resolve_target_schedule

SCHEMA = "SMART_OPERATOR_CONTRACT_V1"


def validate_target_sequence(contests: Iterable[int], target: int) -> dict[str, int]:
    values = [int(x) for x in contests]
    if isinstance(target, bool) or not isinstance(target, int) or target <= 1:
        raise ValueError("operator target must be a positive contest integer greater than 1")
    if not values:
        raise ValueError("canonical contest history is empty")
    if len(values) != len(set(values)):
        raise ValueError("canonical contest history contains duplicates")
    ordered = sorted(values)
    if ordered != list(range(ordered[0], ordered[-1] + 1)):
        raise ValueError("canonical contest history contains gaps")
    cutoff = int(target) - 1
    if ordered[-1] != cutoff:
        raise ValueError(f"operator target requires canonical history through contest {cutoff}; observed max={ordered[-1]}")
    if target in set(ordered):
        raise ValueError("operator target result is already present in canonical history")
    return {"target_contest": int(target), "cutoff_contest": cutoff, "history_max": ordered[-1]}


def validate_target_against_history(data_path: str | Path, target: int) -> dict[str, Any]:
    path = Path(data_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    frame = pd.read_excel(path)
    if "Concurso" not in frame.columns:
        raise ValueError("canonical history lacks Concurso column")
    contests = pd.to_numeric(frame["Concurso"], errors="raise").astype(int).tolist()
    result = validate_target_sequence(contests, int(target))
    result.update({"data_file": str(path), "data_sha256": sha256_file(path), "row_count": len(contests)})
    return result


def contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "product_completion_independent_of_operation": True,
        "operator_selects_target": True,
        "target_required_for_prepare_and_freeze": True,
        "supported_actions": ["status", "prepare", "freeze", "adjudicate"],
        "freeze_is_operational_not_construction_gate": True,
        "adjudication_is_operational_not_construction_gate": True,
        "arbitrary_future_target_supported_when_history_is_complete_through_target_minus_one": True,
        "fail_closed_on_history_gap_or_target_result_present": True,
        "scientific_terminal_claim_independent_of_product_completion": True,
    }


def _archive_active(root: Path, active_path: Path) -> str | None:
    if not active_path.exists():
        return None
    digest = sha256_file(active_path)
    archive = root / "SMART_STATE_ARCHIVE" / f"operator_active_epoch_{digest}.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        shutil.copy2(active_path, archive)
    if sha256_file(archive) != digest:
        raise RuntimeError("operator active-epoch archive hash mismatch")
    return digest


def prepare_operation(root: str | Path, target: int, *, supersede_existing: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    from smart_product_certification import DEFAULT_PATH as PRODUCT_CERT_PATH, verify_product_certification
    certification = verify_product_certification(root / PRODUCT_CERT_PATH, root=root, require_current_code=True)
    canonical = root / "Mega-Sena.xlsx"
    history = validate_target_against_history(canonical, int(target))
    schedule = resolve_target_schedule(root, int(target))
    temporal = assert_pre_draw_window(schedule)
    active_path = root / ACTIVE_PATH
    if active_path.exists() and not supersede_existing:
        raise FileExistsError("an operational epoch already exists; use --supersede only when the operator intentionally starts another target")
    previous_sha = _archive_active(root, active_path) if active_path.exists() else None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    epoch_id = f"operator-{int(target)}-{certification['sha256'][:12]}-{stamp}"
    epoch_dir = root / "runtime" / "learning_epochs" / epoch_id
    epoch_dir.mkdir(parents=True, exist_ok=False)
    snapshot = epoch_dir / f"Mega-Sena_cutoff_{int(target)-1}.xlsx"
    shutil.copy2(canonical, snapshot)
    if sha256_file(snapshot) != history["data_sha256"]:
        raise RuntimeError("operator immutable history snapshot hash mismatch")
    ledger_path = epoch_dir / "SMART_SIGNAL_LEDGER.json"
    fresh = load_ledger(epoch_dir / "__missing__.json")
    ledger_path.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state_path = epoch_dir / "SMART_SIGNAL_STATE.json"
    activation_authority = epoch_dir / "SMART_LEARNING_ACTIVATION_AUTHORITY.json"
    expansion_registry = epoch_dir / "SMART_SIGNAL_EXPANSION_REGISTRY.json"
    freeze_path = epoch_dir / f"SMART_{int(target)}_CHAMPION_CHALLENGER_FREEZE.json"
    def rel(path: Path) -> str:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    active = write_active_epoch(active_path, {
        "schema": EPOCH_SCHEMA,
        "status": "RESET_READY",
        "project": "SMART-MEGA",
        "epoch_id": epoch_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "product_certification_file": str(PRODUCT_CERT_PATH).replace("\\", "/"),
        "product_certification_sha256": certification["sha256"],
        "operator_selected_target": True,
        "state_paths": {"ledger": rel(ledger_path), "state": rel(state_path), "activation_authority": rel(activation_authority), "expansion_registry": rel(expansion_registry), "freeze": rel(freeze_path)},
        "data_file": rel(snapshot),
        "data_sha256": sha256_file(snapshot),
        "canonical_source_file": "Mega-Sena.xlsx",
        "canonical_source_sha256_at_prepare": history["data_sha256"],
        "immutable_history_snapshot": True,
        "cutoff_contest": int(target) - 1,
        "target_contest": int(target),
        "authority_mode": "OPERATOR_SELECTED_TARGET",
        "current_engineering_role": "PRODUCT_CERTIFIED_OPERATION",
        "first_possible_authoritative_target_for_current_engineering": int(target),
        "target_schedule": schedule,
        "temporal_guard": temporal,
        "result_used": False,
        "freeze_authority": None,
        "learning_state_authority": None,
        "supersedes_active_epoch_sha256": previous_sha,
    })
    return {"status": "READY_TO_FREEZE", "product_certification_sha256": certification["sha256"], "active_epoch": active, "history": history, "schedule": schedule}


def freeze_operation(root: str | Path, target: int) -> dict[str, Any]:
    root = Path(root).resolve()
    active = verify_active_epoch(root / ACTIVE_PATH)
    if active.get("operator_selected_target") is not True or int(active["target_contest"]) != int(target):
        raise ValueError("active operational epoch does not match operator-selected target")
    return run_full_process(root)


def adjudicate_operation(root: str | Path, target: int, result_data: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    active = verify_active_epoch(root / ACTIVE_PATH)
    if int(active["target_contest"]) != int(target):
        raise ValueError("active operational epoch does not match adjudication target")
    ledger_path = root / active["state_paths"]["ledger"]
    return adjudicate(Path(result_data), int(target), ledger_path)


def status(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    cert_path = root / "SMART_PRODUCT_CERTIFICATION.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8")) if cert_path.is_file() else None
    active_path = root / ACTIVE_PATH
    active = verify_active_epoch(active_path) if active_path.is_file() else None
    return {"product_certification": cert, "active_operation": active, "operator_contract": contract()}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="SMART-MEGA operator interface. Product construction is independent of contest operation.")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    p = sub.add_parser("prepare"); p.add_argument("--target", type=int, required=True); p.add_argument("--supersede", action="store_true")
    f = sub.add_parser("freeze"); f.add_argument("--target", type=int, required=True)
    a = sub.add_parser("adjudicate"); a.add_argument("--target", type=int, required=True); a.add_argument("--result-data", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    if args.action == "status": out = status(root)
    elif args.action == "prepare": out = prepare_operation(root, args.target, supersede_existing=args.supersede)
    elif args.action == "freeze": out = freeze_operation(root, args.target)
    else: out = adjudicate_operation(root, args.target, args.result_data)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
