"""Resume existing real SMART-MEGA operations until the next MODEL card.

Only one new orchestration surface. Every mutation uses existing guarded
operator functions. A historical draw is never labeled as a forecast.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class CycleHandlers:
    lifecycle: Callable[[Path], dict[str, Any]]
    previous_result: Callable[[Path, int], Any]
    read_batch: Callable[[str | Path], tuple[dict[int, dict], dict[str, Any]]]
    complete_result: Callable[[Path, int], dict[str, Any]]
    catch_up: Callable[[Path, int, str | Path | None], dict[str, Any]]
    generate: Callable[[Path, int], dict[str, Any]]
    read_card: Callable[[Path, int], dict[str, Any]]


def _verified_model_card(card: dict[str, Any], target: int) -> dict[str, Any]:
    if (not isinstance(card, dict)
            or card.get("status") != "FROZEN_MODEL_CARD_VERIFIED"
            or card.get("target_contest") != target
            or card.get("result_used_in_generation") is not False):
        raise RuntimeError("model card evidence has wrong target or prospective authority")
    numbers = card.get("numbers")
    if (not isinstance(numbers, list) or len(numbers) != 6
            or any(type(n) is not int or n < 1 or n > 60 for n in numbers)
            or len(set(numbers)) != 6):
        raise RuntimeError("model card has invalid numbers")
    return card


def complete_to_model_card(root: str | Path, target: int,
                           official_batch: str | Path | None,
                           handlers: CycleHandlers) -> dict[str, Any]:
    """Settle previous frozen draw, close missing results and freeze target.

    An explicit invocation carries operator generation intent, but DOES NOT
    grant model/certification authority: existing operations enforce those.
    Prepared stages are restartable; validations run before any mutation.
    """
    if type(target) is not int or target <= 1:
        raise ValueError("target must be a positive contest number")
    root = Path(root).resolve()
    lifecycle = handlers.lifecycle(root)
    current = lifecycle.get("target_contest")
    state = lifecycle.get("state")
    if type(current) is not int or current < 1:
        raise ValueError("operational lifecycle target invalid")
    if target < current:
        raise ValueError("retrospective generation forbidden")
    if current == target:
        if state == "FROZEN":
            return {"status": "MODEL_CARD_ALREADY_FROZEN", "target_contest": target,
                    "card": _verified_model_card(handlers.read_card(root, target), target),
                    "retroactive_generation": False}
        if state not in {"HOLD", "AUTHORIZED", "PREPARED"}:
            raise ValueError(f"cannot generate current target in lifecycle state {state}")
        handlers.generate(root, target)
        return {"status": "MODEL_CARD_GENERATED", "target_contest": target,
                "card": _verified_model_card(handlers.read_card(root, target), target),
                "retroactive_generation": False}

    if state not in {"FROZEN", "ADJUDICATED", "REVIEWED", "HOLD"}:
        raise ValueError(f"cannot advance incomplete lifecycle state {state}")
    if target == current + 1:
        if official_batch is not None:
            raise ValueError("official result batch not required for already known target")
        missing = ()
    else:
        if official_batch is None:
            raise ValueError("official batch required for missing completed contests")
        missing = tuple(range(current + 1, target))

    # Validate every required draw before mutating a prior lifecycle state.
    # Never silently fall back to network or a pseudorandom prediction.
    if state == "FROZEN":
        try:
            handlers.previous_result(root, current)
        except FileNotFoundError:
            return {"status": "WAITING_PREVIOUS_RESULT", "pending_contest": current,
                    "target_contest": target, "mutations_performed": False}
    if missing:
        payloads, evidence = handlers.read_batch(official_batch)
        if sorted(payloads) != list(missing):
            raise ValueError("official batch missing contests or not strictly contiguous")
        if not isinstance(evidence, dict) or evidence.get("targets") != list(missing):
            raise ValueError("official batch lacks validated source and exact target sequence")
        batch_authority = evidence.get("authority")
        if batch_authority == "CAIXA_PUBLIC_PORTAL_TRANSCRIPTION_NOT_API_VERIFIED":
            if evidence.get("raw_api_independently_verified") is not False or any(
                row.get("source") != "CAIXA_PORTAL_TRANSCRIPTION" for row in payloads.values()
            ):
                raise ValueError("portal transcription must remain non-API-verified")
        elif batch_authority == "TWO_PUBLIC_SOURCES_NOT_CAIXA_API_VERIFIED":
            if evidence.get("raw_api_independently_verified") is not False or any(
                row.get("source") != "PUBLIC_CROSSCHECK_UNVERIFIED_OFFICIAL" for row in payloads.values()
            ):
                raise ValueError("public corroboration must remain non-API-verified")
        elif batch_authority == "CAIXA_API_BATCH_CLAIM_UNVERIFIED_TRANSPORT":
            if (evidence.get("raw_api_independently_verified") is not False
                    or any(row.get("source") not in {None, "CAIXA_CONTEST_API"}
                           for row in payloads.values())):
                raise ValueError("local CAIXA API claim must remain non-API-verified")
        elif batch_authority == "CAIXA_LOTERIAS_OFFICIAL_API":
            raise ValueError("self-declared official API transport is not independent evidence")
        else:
            raise ValueError("official batch lacks validated source and exact target sequence")

    if state in {"FROZEN", "ADJUDICATED"}:
        completion = handlers.complete_result(root, current)
        if completion.get("status") == "WAITING_FOR_RESULT":
            return {"status": "WAITING_FOR_RESULT", "pending_contest": current,
                    "target_contest": target, "mutations_performed": False}
        if completion.get("status") not in {
            "POST_RESULT_OPERATIONALLY_COMPLETED",
            "POST_RESULT_REVIEWED_PENDING_ROLLOVER",
            "POST_RESULT_ALREADY_CLOSED",
        }:
            raise RuntimeError("prior result completion has not been proven")

    recovered = handlers.catch_up(root, target - 1, official_batch)
    if (not isinstance(recovered, dict)
            or recovered.get("status") != "CAUGHT_UP_TO_HOLD"
            or recovered.get("next_target") != target):
        raise RuntimeError("catch-up did not reach exact next target HOLD")
    advanced = handlers.lifecycle(root)
    if (advanced.get("state") != "HOLD"
            or advanced.get("target_contest") != target
            or advanced.get("completed_contest") != target - 1):
        raise RuntimeError("canonical lifecycle did not reach exact HOLD after catch-up")

    # Existing generation path validates fresh certification, verified history,
    # manual authority and PRE-DRAW cutoff. It must never be weakened here.
    handlers.generate(root, target)
    card = _verified_model_card(handlers.read_card(root, target), target)
    return {
        "status": "MODEL_CARD_GENERATED",
        "target_contest": target,
        "completed_contests": list(range(current, target)),
        "card": card,
        "retroactive_generation": False,
        "scientific_6of6_proven": False,
        "underlying_native_gates_preserved": True,
    }
