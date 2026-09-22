from __future__ import annotations
from smart_canonical_identity import canonical_root

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from smart_champion_challenger import active_freeze, load_ledger
from smart_regression_evidence import sha256_file

SCHEMA = "SMART_PROSPECTIVE_AUTHORITY_LOCK_1"
DEFAULT_PATH = Path("SMART_PROSPECTIVE_AUTHORITY_LOCK.json")


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def _canonical_max_contest(path: Path) -> int:
    frame = pd.read_excel(path, usecols=["Concurso"])
    contests = pd.to_numeric(frame["Concurso"], errors="raise").astype(int)
    if contests.empty:
        raise ValueError("canonical dataset has no contests")
    return int(contests.max())


def resolve_unresolved_authority(root: str | Path = ".") -> dict[str, Any] | None:
    root = Path(root).resolve()
    ledger_path = root / "SMART_SIGNAL_LEDGER.json"
    if not ledger_path.is_file():
        return None
    ledger = load_ledger(ledger_path)
    freeze_targets = sorted({
        int(ev.get("target_contest", -1))
        for ev in ledger.get("events", [])
        if ev.get("event_type") == "FREEZE" and int(ev.get("target_contest", -1)) > 0
    })
    adjudicated = {
        int(ev.get("target_contest", -1))
        for ev in ledger.get("events", [])
        if ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) > 0
    }
    pending = [target for target in freeze_targets if target not in adjudicated]
    if not pending:
        return None
    if len(pending) != 1:
        raise ValueError(f"exactly one unresolved prospective target required, found {pending}")
    target = pending[0]
    event = active_freeze(ledger, target)
    if event is None:
        raise ValueError(f"no active freeze resolves for pending target {target}")
    freeze_file = str(event.get("freeze_file", ""))
    freeze_sha = str(event.get("freeze_sha256", ""))
    freeze_path = (root / freeze_file).resolve()
    if not freeze_path.is_file() or sha256_file(freeze_path) != freeze_sha:
        raise ValueError("active unresolved freeze file/hash mismatch")
    freeze = _read_json(freeze_path)
    cutoff = int(freeze.get("cutoff_contest", -1))
    if int(freeze.get("target_contest", -1)) != target or cutoff != target - 1:
        raise ValueError("active unresolved freeze target/cutoff mismatch")
    if freeze.get("frozen_before_result") is not True or freeze.get("causal_cutoff") is not True:
        raise ValueError("unresolved freeze is not causally frozen before result")
    top6 = freeze.get("governed_challenger_top6") or freeze.get("challenger", {}).get("top6") or freeze.get("champion", {}).get("top6")
    if not isinstance(top6, list) or len(top6) != 6 or len(set(map(int, top6))) != 6 or any(not 1 <= int(x) <= 60 for x in top6):
        raise ValueError("unresolved freeze Top-6 invalid")
    data_file = str(freeze.get("data_file", ""))
    data_sha = str(freeze.get("data_sha256", ""))
    data_path = (root / data_file).resolve()
    if not data_path.is_file() or sha256_file(data_path) != data_sha:
        raise ValueError("unresolved freeze data file/hash mismatch")
    state_file = str(freeze.get("signal_state_file", ""))
    state_sha = str(freeze.get("signal_state_sha256", ""))
    state_path = (root / state_file).resolve()
    if not state_path.is_file() or sha256_file(state_path) != state_sha:
        raise ValueError("unresolved freeze signal-state file/hash mismatch")
    canonical = root / "Mega-Sena.xlsx"
    canonical_max = _canonical_max_contest(canonical) if canonical.is_file() else cutoff
    if canonical_max > target:
        raise ValueError("canonical result store advanced beyond unresolved target without adjudication")
    return {
        "target_contest": target,
        "cutoff_contest": cutoff,
        "freeze_file": freeze_file,
        "freeze_sha256": freeze_sha,
        "freeze_top6": sorted(map(int, top6)),
        "frozen_utc": freeze.get("frozen_utc"),
        "frozen_before_result": True,
        "causal_cutoff": True,
        "data_file": data_file,
        "data_sha256": data_sha,
        "signal_state_file": state_file,
        "signal_state_sha256": state_sha,
        "ledger_file": ledger_path.name,
        "ledger_sha256": sha256_file(ledger_path),
        "canonical_result_store_max": canonical_max,
        "result_adjudicated": False,
    }


def build_lock(root: str | Path = ".") -> dict[str, Any] | None:
    authority = resolve_unresolved_authority(root)
    if authority is None:
        return None
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "LOCKED_UNRESOLVED_PROSPECTIVE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "project": "SMART-MEGA",
        "experiment_authority": {
            **authority,
            "authority_kind": "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE",
            "eligible_for_scientific_adjudication": True,
            "eligible_to_prove_post_freeze_engineering_version": False,
            "immutable_until_adjudication": True,
        },
        "current_engineering_policy": {
            "role_for_locked_target": "PARALLEL_PRE_CURRENT_ENGINEERING_ATTEMPT_ONLY",
            "may_mutate_locked_freeze": False,
            "may_claim_generation_of_locked_freeze": False,
            "may_learn_from_locked_target_before_adjudication": False,
            "may_generate_independent_current_epoch_prediction_same_target_before_result": True,
            "parallel_attempts_must_be_counted_separately": True,
            "first_possible_authoritative_target": authority["target_contest"],
        },
        "rules": {
            "engineering_changes_do_not_invalidate_unresolved_freeze": True,
            "freeze_origin_is_not_reassigned": True,
            "post_freeze_code_cannot_retroactively_claim_prediction": True,
            "parallel_current_prediction_does_not_replace_locked_prediction": True,
            "all_registered_attempts_must_be_counted": True,
            "only_adjudication_closes_locked_target": True,
        },
    }
    doc["sha256"] = _sha256_json(doc)
    return doc


def verify_lock(path: str | Path, *, root: str | Path | None = None) -> dict[str, Any]:
    path = Path(path)
    obj = _read_json(path)
    if obj.get("schema") != SCHEMA or obj.get("status") != "LOCKED_UNRESOLVED_PROSPECTIVE":
        raise ValueError("invalid prospective authority lock schema/status")
    observed = obj.get("sha256")
    canonical = dict(obj)
    canonical.pop("sha256", None)
    if observed != _sha256_json(canonical):
        raise ValueError("prospective authority lock self-hash invalid")
    if not all(obj.get("rules", {}).values()):
        raise ValueError("prospective authority lock rules invalid")
    if root is not None:
        live = resolve_unresolved_authority(root)
        auth = obj.get("experiment_authority", {})
        if live is None or any(live.get(k) != auth.get(k) for k in live):
            raise ValueError("prospective authority lock no longer matches live unresolved authority")
    return obj


CLOSURE_SCHEMA = "SMART_PROSPECTIVE_AUTHORITY_CLOSURE_1"


def adjudicated_lock_evidence(path: str | Path, *, root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    lock = verify_lock(path, root=None)
    auth = lock["experiment_authority"]
    target = int(auth["target_contest"])
    freeze_sha = str(auth["freeze_sha256"])
    ledger_path = root / str(auth.get("ledger_file") or "SMART_SIGNAL_LEDGER.json")
    ledger = load_ledger(ledger_path)
    matches = [
        ev for ev in ledger.get("events", [])
        if ev.get("event_type") == "ADJUDICATION"
        and int(ev.get("target_contest", -1)) == target
        and str(ev.get("freeze_sha256", "")) == freeze_sha
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one adjudication for locked target/freeze, found {len(matches)}")
    ev = matches[0]
    actual = sorted(map(int, ev.get("actual_numbers", [])))
    if len(actual) != 6 or len(set(actual)) != 6 or any(not 1 <= n <= 60 for n in actual):
        raise ValueError("locked target adjudication actual_numbers invalid")
    freeze_path = root / str(auth["freeze_file"])
    data_path = root / str(auth["data_file"])
    state_path = root / str(auth["signal_state_file"])
    if not freeze_path.is_file() or sha256_file(freeze_path) != freeze_sha:
        raise ValueError("locked freeze changed after adjudication")
    if not data_path.is_file() or sha256_file(data_path) != auth["data_sha256"]:
        raise ValueError("locked data changed after adjudication")
    if not state_path.is_file() or sha256_file(state_path) != auth["signal_state_sha256"]:
        raise ValueError("locked signal state changed after adjudication")
    return {
        "target_contest": target,
        "cutoff_contest": int(auth["cutoff_contest"]),
        "freeze_file": str(auth["freeze_file"]),
        "freeze_sha256": freeze_sha,
        "lock_sha256": str(lock["sha256"]),
        "adjudication_created_utc": ev.get("created_utc"),
        "actual_numbers": actual,
        "champion_hits": int(ev.get("champion_hits", -1)),
        "challenger_hits": int(ev.get("challenger_hits", -1)),
        "ledger_file": str(auth.get("ledger_file") or "SMART_SIGNAL_LEDGER.json"),
        "ledger_sha256_current": sha256_file(ledger_path),
    }


def close_adjudicated_lock(root: str | Path = ".", path: str | Path = DEFAULT_PATH) -> dict[str, Any] | None:
    root = Path(root).resolve()
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return None
    evidence = adjudicated_lock_evidence(path, root=root)
    lock = verify_lock(path, root=None)
    archive = root / "SMART_STATE_ARCHIVE" / f"prospective_authority_lock_{lock['sha256']}.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        shutil.copy2(path, archive)
    if sha256_file(archive) != lock["sha256"]:
        raise RuntimeError("prospective authority lock archive hash mismatch")
    closure_path = root / f"SMART_PROSPECTIVE_AUTHORITY_CLOSURE_{evidence['target_contest']}.json"
    closure: dict[str, Any] = {
        "schema": CLOSURE_SCHEMA,
        "status": "ADJUDICATED_CLOSED",
        "closed_utc": datetime.now(timezone.utc).isoformat(),
        "project": "SMART-MEGA",
        **evidence,
        "archived_lock_file": str(archive.relative_to(root)).replace("\\", "/"),
        "archived_lock_sha256": sha256_file(archive),
        "live_unresolved_lock_removed": True,
        "retroactive_rewrite": False,
    }
    closure["sha256"] = _sha256_json(closure)
    closure_path.write_text(json.dumps(closure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.unlink()
    return closure


def verify_closure(path: str | Path, *, root: str | Path | None = None) -> dict[str, Any]:
    path = Path(path)
    obj = _read_json(path)
    if obj.get("schema") != CLOSURE_SCHEMA or obj.get("status") != "ADJUDICATED_CLOSED":
        raise ValueError("invalid prospective authority closure schema/status")
    observed = obj.get("sha256")
    canonical = dict(obj)
    canonical.pop("sha256", None)
    if observed != _sha256_json(canonical):
        raise ValueError("prospective authority closure self-hash invalid")
    if obj.get("live_unresolved_lock_removed") is not True or obj.get("retroactive_rewrite") is not False:
        raise ValueError("prospective authority closure semantics invalid")
    if root is not None:
        project_root = Path(root).resolve()
        archive = project_root / str(obj["archived_lock_file"])
        if not archive.is_file() or sha256_file(archive) != obj["archived_lock_sha256"]:
            raise ValueError("prospective authority closure archive mismatch")
    return obj


def write_lock(root: str | Path = ".", out: str | Path = DEFAULT_PATH) -> dict[str, Any] | None:
    root = Path(root).resolve()
    doc = build_lock(root)
    if doc is None:
        return None
    out = Path(out)
    if not out.is_absolute():
        out = root / out
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    root = canonical_root()
    result = write_lock(root)
    print(json.dumps(result or {"status": "NO_UNRESOLVED_PROSPECTIVE_AUTHORITY"}, ensure_ascii=False, indent=2))
