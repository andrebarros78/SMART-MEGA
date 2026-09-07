from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_agent_skill_orchestration import build_orchestration
from smart_prospective_authority_lock import DEFAULT_PATH as AUTHORITY_LOCK_PATH, build_lock, verify_lock, write_lock
from smart_regression_evidence import junit_summary, sha256_file
from smart_runtime_guard import audit as runtime_audit
from smart_total_integration_gate import write as write_total_integration
from smart_target_schedule import resolve_target_schedule

SCHEMA = "SMART_ENGINEERING_ACTIVATION_2"
DEFAULT_PATH = Path("SMART_FULL_ACTIVATION_EPOCH.json")
LEGACY_PRE_ACTIVATION = (
    "SMART_3054_CHAMPION_CHALLENGER_FREEZE.json",
    "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json",
    "SMART_3054_CHAMPION_CHALLENGER_FREEZE_PORTFOLIO.json",
    "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2_PORTFOLIO.json",
    "SMART_SIGNAL_LEDGER.json",
    "SMART_SIGNAL_STATE.json",
    "SMART_SIGNAL_STATE_3054_V2.json",
    "SMART_SIGNAL_EXPANSION_REGISTRY.json",
    "SMART_MODEL_REGISTRY.json",
    "SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json",
)


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _code_files(root: Path) -> list[Path]:
    files = sorted(set(root.glob("smart_*.py")) | set(root.glob("test_*.py")))
    for name in ("requirements.txt", "requirements.lock.txt", "smart_python.cmd", "pytest.ini", "SMART_DATA_CONTRACT.md"):
        p = root / name
        if p.is_file():
            files.append(p)
    return sorted(set(files))


def _code_fingerprint(root: Path) -> dict[str, Any]:
    rows = [{"path": p.name, "sha256": sha256_file(p)} for p in _code_files(root)]
    return {"file_count": len(rows), "files": rows, "sha256": _sha256_json(rows)}


def _all_gate_values_true(total: dict[str, Any]) -> bool:
    gates = total.get("gates")
    expected = {"G1_ROLE_EXECUTORS", "G2_CAPABILITY_BINDINGS", "G3_FILES", "G4_RUNTIME", "G5_INTEGRATION", "G6_E2E", "G7_RESILIENCE", "G8_SECURITY_STATE", "G9_SEMANTIC_TRUTH"}
    return isinstance(gates, dict) and set(gates) == expected and all(
        isinstance(group, dict) and group and all(value is True for value in group.values())
        for group in gates.values()
    )


def _target_draw_has_passed(schedule: dict[str, Any], *, now_utc: datetime | None = None) -> bool:
    raw = schedule.get("scheduled_datetime")
    if not isinstance(raw, str):
        raise ValueError("target schedule missing scheduled_datetime")
    scheduled = datetime.fromisoformat(raw)
    if scheduled.tzinfo is None:
        raise ValueError("target schedule must be timezone-aware")
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    if now.tzinfo is None:
        raise ValueError("activation clock must be timezone-aware")
    return now.astimezone(timezone.utc) >= scheduled.astimezone(timezone.utc)


def _archive_existing(root: Path, path: Path) -> str | None:
    if not path.exists():
        return None
    digest = sha256_file(path)
    archive = root / "SMART_STATE_ARCHIVE" / f"engineering_activation_{digest}.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        shutil.copy2(path, archive)
    if sha256_file(archive) != digest:
        raise RuntimeError("engineering activation archive hash mismatch")
    return digest


def verify_activation(
    path: str | Path,
    *,
    root: str | Path | None = None,
    require_current_code: bool = False,
) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        raise ValueError("invalid engineering activation schema")
    observed = obj.get("sha256")
    canonical = dict(obj)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or len(observed) != 64 or observed != _sha256_json(canonical):
        raise ValueError("engineering activation self-hash invalid")
    phase = obj.get("phase")
    if obj.get("status") != "FULL_ENGINEERING_ACTIVATION" or phase not in {"PRE_FREEZE", "PROSPECTIVE_LOCKED_SHADOW"}:
        raise ValueError("engineering activation is not active")
    if not all(obj.get("checks", {}).values()):
        raise ValueError("engineering activation checks are not all true")
    if phase == "PRE_FREEZE":
        if obj.get("current_freeze_authority") is not None or obj.get("current_learning_state_authority") is not None:
            raise ValueError("PRE_FREEZE activation cannot import prior freeze or learned-state authority")
        parallel = obj.get("parallel_locked_experiment")
        if parallel is not None:
            if not isinstance(parallel, dict) or parallel.get("eligible_to_prove_post_freeze_engineering_version") is not False:
                raise ValueError("parallel locked experiment authority semantics invalid")
            if obj.get("parallel_attempts_must_be_counted_separately") is not True:
                raise ValueError("parallel prospective attempts must be counted separately")
    if phase == "PROSPECTIVE_LOCKED_SHADOW":
        lock_ref = obj.get("prospective_authority_lock")
        if not isinstance(lock_ref, dict) or not isinstance(lock_ref.get("file"), str):
            raise ValueError("locked engineering activation missing prospective authority lock")
        project_root = Path(root).resolve() if root is not None else p.resolve().parent
        lock_path = project_root / lock_ref["file"]
        lock = verify_lock(lock_path, root=project_root)
        if lock.get("sha256") != lock_ref.get("sha256"):
            raise ValueError("engineering activation authority-lock hash mismatch")
        if obj.get("current_engineering_role") != "SHADOW_ONLY_FOR_LOCKED_TARGET":
            raise ValueError("locked engineering activation must remain shadow-only for locked target")
        auth = lock["experiment_authority"]
        if obj.get("target_draw_time_passed_at_activation") is not True:
            raise ValueError("locked shadow activation must be caused by a passed target draw time")
        if int(obj.get("first_possible_authoritative_target_for_current_engineering", -1)) != int(auth["target_contest"]) + 1:
            raise ValueError("locked shadow activation next authoritative target is invalid")
        if obj.get("current_engineering_freeze_generation_authority") != "BLOCKED_TARGET_DRAW_TIME_PASSED":
            raise ValueError("locked shadow activation must block same-target freeze generation")
    if require_current_code:
        project_root = Path(root).resolve() if root is not None else p.resolve().parent
        recorded = obj.get("code_fingerprint")
        if not isinstance(recorded, dict):
            raise ValueError("engineering activation code fingerprint missing")
        current = _code_fingerprint(project_root)
        if recorded != current:
            raise ValueError("engineering activation code fingerprint stale")
    return obj


def activate(
    root: str | Path = ".",
    out: str | Path = DEFAULT_PATH,
    *,
    supersede_existing: bool = False,
) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(out)
    if not out.is_absolute():
        out = root / out
    junit_path = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    if not junit_path.is_file():
        raise FileNotFoundError(junit_path)
    regression = junit_summary(junit_path)
    code_files = _code_files(root)
    latest_code_mtime = max(p.stat().st_mtime for p in code_files)
    regression_fresh = junit_path.stat().st_mtime >= latest_code_mtime

    lock = build_lock(root)
    if lock is not None:
        lock = write_lock(root)
        if lock is None:
            raise RuntimeError("prospective authority disappeared during activation")

    total = write_total_integration(root, root / "SMART_TOTAL_INTEGRATION_PRE_FREEZE_PROOF.json", phase="PRE_FREEZE")
    runtime = runtime_audit(root)
    orchestration = build_orchestration(root, phase="PRE_FREEZE")
    context = orchestration["active_context"]
    target_schedule = resolve_target_schedule(root, int(context["target_contest"]))
    target_draw_passed = _target_draw_has_passed(target_schedule)
    if target_draw_passed and lock is None:
        raise RuntimeError("engineering activation blocked: target draw time already passed and no locked prospective attempt exists to adjudicate")
    phase = "PROSPECTIVE_LOCKED_SHADOW" if target_draw_passed and lock is not None else "PRE_FREEZE"
    current_engineering_role = "SHADOW_ONLY_FOR_LOCKED_TARGET" if phase == "PROSPECTIVE_LOCKED_SHADOW" else "AUTHORITATIVE_PRE_FREEZE_CANDIDATE"
    first_possible_target = int(context["target_contest"]) + (1 if phase == "PROSPECTIVE_LOCKED_SHADOW" else 0)
    freeze_generation_authority = "BLOCKED_TARGET_DRAW_TIME_PASSED" if phase == "PROSPECTIVE_LOCKED_SHADOW" else "ELIGIBLE_AFTER_FREEZE_GENERATION"
    checks = {
        "full_regression_green": regression["status"] == "PASS" and regression["failures"] == 0 and regression["errors"] == 0,
        "full_regression_fresh_for_current_code": regression_fresh,
        "pre_freeze_total_integration_pass": total.get("status") == "PASS" and total.get("phase") == "PRE_FREEZE" and _all_gate_values_true(total),
        "runtime_guard_pass": runtime.get("status") == "PASS" and all(runtime.get("checks", {}).values()),
        "pre_freeze_orchestration_pass": orchestration.get("integration_status") == "PASS",
        "causal_target_is_cutoff_plus_one": int(context["target_contest"]) == int(context["cutoff_contest"]) + 1,
        "scientific_terminal_not_falsely_declared": orchestration.get("global_mission_state") == "MISSION_ACTIVE" and orchestration.get("terminal_6of6_proven") is False,
        "target_draw_time_authority_consistent": (phase == "PROSPECTIVE_LOCKED_SHADOW") == bool(target_draw_passed),
    }
    if lock is None:
        checks.update({
            "no_prior_freeze_authority": context.get("freeze_file") is None and context.get("freeze_sha256") is None,
            "no_prior_learned_state_authority": context.get("signal_state_file") is None and context.get("signal_state_sha256") is None,
        })
    else:
        auth = lock["experiment_authority"]
        freeze_path = root / auth["freeze_file"]
        state_path = root / auth["signal_state_file"]
        checks.update({
            "unresolved_prospective_freeze_preserved": freeze_path.is_file() and sha256_file(freeze_path) == auth["freeze_sha256"],
            "unresolved_signal_state_preserved": state_path.is_file() and sha256_file(state_path) == auth["signal_state_sha256"],
            "locked_prediction_preserved_as_parallel_attempt": lock["current_engineering_policy"]["role_for_locked_target"] == "PARALLEL_PRE_CURRENT_ENGINEERING_ATTEMPT_ONLY",
            "parallel_attempt_policy_pre_result_capable": lock["current_engineering_policy"]["may_generate_independent_current_epoch_prediction_same_target_before_result"] is True,
            "effective_parallel_attempt_authority_respects_draw_time": (not target_draw_passed) if phase == "PRE_FREEZE" else target_draw_passed,
            "parallel_attempts_counted_separately": lock["current_engineering_policy"]["parallel_attempts_must_be_counted_separately"] is True,
            "no_retroactive_generation_authority_transfer": lock["current_engineering_policy"]["may_claim_generation_of_locked_freeze"] is False,
            "scientific_adjudication_authority_retained": auth["eligible_for_scientific_adjudication"] is True,
            "current_pre_freeze_context_has_no_imported_freeze": context.get("freeze_file") is None and context.get("freeze_sha256") is None,
            "current_pre_freeze_context_has_no_imported_state": context.get("signal_state_file") is None and context.get("signal_state_sha256") is None,
        })
    if not all(checks.values()):
        raise RuntimeError(f"engineering activation blocked: {checks}")

    active_freeze_file = lock["experiment_authority"]["freeze_file"] if lock else None
    active_state_file = lock["experiment_authority"]["signal_state_file"] if lock else None
    legacy = []
    for name in LEGACY_PRE_ACTIVATION:
        p = root / name
        if lock is not None and name == active_freeze_file:
            authority = "PARALLEL_PRE_CURRENT_ENGINEERING_PROSPECTIVE_AUTHORITY"
        elif lock is not None and name == active_state_file:
            authority = "PARALLEL_PRE_CURRENT_ENGINEERING_STATE"
        elif lock is not None and name == "SMART_SIGNAL_LEDGER.json":
            authority = "PARALLEL_PRE_CURRENT_ENGINEERING_SEQUENCE_LEDGER"
        else:
            authority = "PRE_FULL_ACTIVATION_HISTORICAL_ONLY"
        legacy.append({
            "path": name,
            "present": p.is_file(),
            "sha256": sha256_file(p) if p.is_file() else None,
            "authority": authority,
        })
    code = _code_fingerprint(root)
    previous_sha = None
    if out.exists():
        if not supersede_existing:
            raise FileExistsError(f"refusing to overwrite immutable activation evidence: {out}")
        previous_sha = _archive_existing(root, out)
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "FULL_ENGINEERING_ACTIVATION",
        "project": "SMART-MEGA",
        "activated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "version_scope": "CURRENT_ENGINEERING_VERSION_CLOSED_FOR_FEATURE_ADDITION",
        "learning_epoch_required": True,
        "current_engineering_role": current_engineering_role,
        "current_freeze_authority": None,
        "current_learning_state_authority": None,
        "current_engineering_freeze_generation_authority": freeze_generation_authority,
        "pre_activation_outputs_may_not_prove_current_version": True,
        "locked_experiment_may_be_scientifically_adjudicated": bool(lock),
        "parallel_locked_experiment": (lock["experiment_authority"] if lock else None),
        "parallel_attempts_must_be_counted_separately": bool(lock),
        "first_possible_authoritative_target_for_current_engineering": first_possible_target,
        "target_schedule": target_schedule,
        "target_draw_time_passed_at_activation": target_draw_passed,
        "supersedes_activation_sha256": previous_sha,
        "regression": regression,
        "code_fingerprint": code,
        "engineering_pre_freeze_context": context,
        "pre_freeze_total_integration_sha256": total["sha256"],
        "runtime_guard": runtime,
        "prospective_authority_lock": ({"file": str(AUTHORITY_LOCK_PATH), "sha256": lock["sha256"]} if lock else None),
        "legacy_pre_activation_artifacts": legacy,
        "checks": checks,
    }
    doc["sha256"] = _sha256_json(doc)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def main() -> None:
    root = Path(__file__).resolve().parent
    doc = activate(root)
    print(json.dumps({
        "status": doc["status"],
        "phase": doc["phase"],
        "tests": doc["regression"]["tests"],
        "integration_sha256": doc["pre_freeze_total_integration_sha256"],
        "activation_sha256": doc["sha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
