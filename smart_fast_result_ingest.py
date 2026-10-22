"""One-call, governed Mega-Sena result intake using existing native operators.

This is a thin orchestration layer, not another result authority.  It does not
change predictive weights, create forecasts, certify science, or publish Git
objects. The caller publishes only after evidence review in a protected PR.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any


def _hash_body(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


def _read_verified(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid hashed evidence: {path.name}")
    supplied = data.get("sha256")
    body = dict(data)
    body.pop("sha256", None)
    if not isinstance(supplied, str) or supplied != _hash_body(body):
        raise ValueError(f"evidence hash mismatch: {path.name}")
    return data


def _payload_under_root(root: Path, payload_file: str | Path) -> Path:
    path = Path(payload_file)
    if ".." in path.parts:
        raise ValueError("result batch must remain inside project")
    source = (root / path).absolute() if not path.is_absolute() else path
    if source.is_symlink():
        raise ValueError("result batch symlink is forbidden")
    source = source.resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError("result batch must remain inside project")
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("result batch exceeds bounded size")
    return source


def _native_handlers() -> dict[str, Any]:
    """Defer heavy operator/pandas imports until their step is actually needed."""
    def lifecycle(root):
        from smart_operational_lifecycle import load_lifecycle
        return load_lifecycle(root)

    def batch(source):
        from smart_missed_catchup import load_official_payload_batch
        return load_official_payload_batch(source)

    def register(root, target, source):
        from smart_operator import register_result_operation
        return register_result_operation(root, target, source)

    def complete(root, target):
        from smart_operator import complete_result_operation
        return complete_result_operation(root, target)

    def catch_up(root, target, source):
        from smart_operator import catch_up_missed_operation
        return catch_up_missed_operation(root, target, source)

    return {"lifecycle": lifecycle, "batch": batch, "register": register,
            "complete": complete, "catch_up": catch_up}


def _confirm_already_ingested(root: Path, target: int, numbers: list[int]) -> None:
    proof_path = root / f"SMART_MISSED_TARGET_RECOVERY_{target}.json"
    hold_path = root / "SMART_NEXT_CYCLE_HOLD.json"
    if not proof_path.is_file() or not hold_path.is_file():
        raise ValueError("completed result lacks recovery/hold proof")
    proof = _read_verified(proof_path)
    hold = _read_verified(hold_path)
    if (proof.get("target_contest") != target
            or proof.get("official_result") != numbers
            or proof.get("result_used_for_prediction") is not False
            or hold.get("next_target") != target + 1
            or hold.get("completed_contest") != target):
        raise ValueError("completed result conflicts with immutable authority")
    canonical = root / "Mega-Sena.xlsx"
    if (not canonical.is_file() or hashlib.sha256(canonical.read_bytes()).hexdigest()
            != hold.get("canonical_sha256_at_review")):
        raise ValueError("completed canonical dataset hash mismatch")


def _prepare_operator_input(root: Path, target: int, row: dict[str, Any],
                            source: Path, authority: dict[str, Any]) -> Path:
    """Create-only operator transcription when frozen target is the drawn contest."""
    name = root / f"SMART_OPERATOR_RESULT_INPUT_{target}.json"
    data = {
        "schema": "SMART_OPERATOR_RESULT_INPUT_1", "target_contest": target,
        "draw_date": row["dataApuracao"],
        "numbers": [int(n) for n in row["listaDezenas"]],
        "origin": "OPERATOR_TRANSCRIPTION_OF_CAPTURED_RESULT",
        "batch_file": source.name,
        "batch_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "raw_api_independently_verified": False,
    }
    if name.exists():
        if name.is_symlink() or json.loads(name.read_text(encoding="utf-8-sig")) != data:
            raise ValueError("existing operator input conflicts with result batch")
        return name
    with name.open("x", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return name


def ingest_result(root: str | Path, target: int, payload_file: str | Path,
                  *, dry_run: bool = False, handlers: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate once, settle older frozen epoch, and catch up without forecast.

    A missing former result or unexpected lifecycle fails closed before
    proceeding to the canonical append. Retry uses native resumable operations.
    """
    started = time.monotonic()
    root = Path(root).resolve()
    if type(target) is not int or target < 1:
        raise ValueError("target must be a positive integer")
    source = _payload_under_root(root, payload_file)
    fn = handlers if handlers is not None else _native_handlers()
    records, evidence = fn["batch"](source)
    if sorted(records) != [target]:
        raise ValueError("result batch target must match the one requested contest")
    row = records[target]
    numbers = sorted(int(n) for n in row["listaDezenas"])
    lifecycle = fn["lifecycle"](root)
    state = lifecycle.get("state")
    current = lifecycle.get("target_contest")
    completed = lifecycle.get("completed_contest")
    if type(current) is not int:
        raise ValueError("invalid operational lifecycle target")
    if state == "HOLD" and current == target + 1 and completed == target:
        _confirm_already_ingested(root, target, numbers)
        return {"status": "ALREADY_INGESTED", "target_contest": target,
                "next_target": target + 1, "prediction_authority_created": False,
                "elapsed_seconds": round(time.monotonic() - started, 3)}

    if state == "HOLD" and current == target and completed == target - 1:
        route = "CATCH_UP"
    elif state in {"FROZEN", "ADJUDICATED", "REVIEWED"} and current in {target, target - 1}:
        route = "COMPLETE_AND_CATCH_UP"
    else:
        raise ValueError(f"unsupported lifecycle for result {target}: {state}/{current}")

    result = {
        "status": "READY_TO_INGEST" if dry_run else "INGESTED_TO_HOLD",
        "target_contest": target,
        "next_target": target + 1,
        "route": route,
        "source_authority": evidence.get("authority"),
        "independent_api_verified": evidence.get("raw_api_independently_verified") is True,
        "prediction_authority_created": False,
        "generation_authority_created": False,
        "retroactive_generation_performed": False,
    }
    if dry_run:
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        return result

    if route == "COMPLETE_AND_CATCH_UP":
        if current == target and state == "FROZEN":
            input_path = _prepare_operator_input(root, target, row, source, evidence)
            fn["register"](root, target, input_path)
        previous = fn["complete"](root, current)
        if previous.get("status") not in {
            "POST_RESULT_OPERATIONALLY_COMPLETED", "POST_RESULT_REVIEWED_PENDING_ROLLOVER",
            "POST_RESULT_ALREADY_CLOSED",
        }:
            raise ValueError("previous result cannot be completed; ingestion stopped")

    recovered = fn["catch_up"](root, target, source)
    final = fn["lifecycle"](root)
    if (recovered.get("status") != "CAUGHT_UP_TO_HOLD"
            or recovered.get("prediction_authority_created") is not False
            or recovered.get("generation_authority_created") is not False
            or final.get("state") != "HOLD"
            or final.get("target_contest") != target + 1
            or final.get("completed_contest") != target):
        raise RuntimeError("ingestion end-state invalid; do not publish")
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Single-run audited result ingestion. No GitHub Actions.")
    parser.add_argument("--target", required=True, type=int)
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--apply", action="store_true", help="mutate local authorized checkout")
    opts = parser.parse_args()
    from smart_canonical_identity import canonical_root
    try:
        proof = ingest_result(canonical_root(), opts.target, opts.payload_file,
                              dry_run=not opts.apply)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": f"{type(exc).__name__}: {exc}",
                          "target_contest": opts.target, "no_automatic_retry": True},
                         ensure_ascii=False))
        return 1
    print(json.dumps(proof, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
