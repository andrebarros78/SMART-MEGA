"""Read-only terminal result transforms, separate from orchestration and writes.

The caller supplies the active contest, official validator, and ball-column
contract so existing dynamic epoch semantics remain intact.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

import pandas as pd


def contest_max(path: Path) -> int:
    frame = pd.read_excel(path, usecols=["Concurso"])
    if frame.empty:
        raise ValueError("result store is empty")
    contests = frame["Concurso"].astype(int)
    if contests.duplicated().any():
        raise ValueError("result store contains duplicate contests")
    return int(contests.max())


def target_events(ledger: dict[str, Any], event_type: str, target: int) -> list[dict[str, Any]]:
    return [
        event for event in ledger.get("events", [])
        if event.get("event_type") == event_type and int(event.get("target_contest", -1)) == target
    ]


def normalize_primary(
    payload: dict[str, Any], target: int,
    validate_official_payload: Callable[[dict[str, Any], int], dict[str, Any]],
) -> dict[str, Any]:
    validated = validate_official_payload(payload, target)
    return {
        "target_contest": target,
        "draw_date": validated["draw_date_text"],
        "numbers": validated["numbers"],
    }


def payload_from_normalized(normalized: dict[str, Any], target: int) -> dict[str, Any]:
    return {
        "numero": target,
        "dataApuracao": normalized["draw_date"],
        "listaDezenas": [f"{int(number):02d}" for number in normalized["numbers"]],
        "acumulado": False,
    }


def consensus_rank(document: dict[str, Any]) -> int:
    return 2 if document.get("terminal_source_corroboration_authorized") is True else 1


def draw_map(path: Path, ball_columns: Sequence[str]) -> dict[int, tuple[int, ...]]:
    frame = pd.read_excel(path)
    required = {"Concurso", *ball_columns}
    if not required.issubset(frame.columns):
        raise ValueError("result store draw columns missing")
    result: dict[int, tuple[int, ...]] = {}
    for _, row in frame.iterrows():
        contest = int(row["Concurso"])
        numbers = tuple(sorted(int(row[column]) for column in ball_columns))
        if contest in result or len(set(numbers)) != 6:
            raise ValueError("invalid result store draw sequence")
        result[contest] = numbers
    return result


