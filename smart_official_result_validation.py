"""Dependency-free validation shared by result registration and dataset ingestion."""
from __future__ import annotations

from datetime import datetime
from typing import Any

def _strict_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if str(value).strip().lstrip("0") not in {str(parsed), ""}:
        raise ValueError(f"{label} must be an integer")
    return parsed


def validate_official_payload(payload: Any, target: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("official payload must be an object")
    contest = _strict_int(payload.get("numero"), "official contest")
    if contest != int(target):
        raise ValueError("official contest does not match target")
    raw_numbers = payload.get("listaDezenas")
    if not isinstance(raw_numbers, list) or len(raw_numbers) != 6:
        raise ValueError("official result must contain exactly six numbers")
    numbers = sorted(_strict_int(value, "official number") for value in raw_numbers)
    if len(set(numbers)) != 6 or numbers[0] < 1 or numbers[-1] > 60:
        raise ValueError("official result must contain six unique numbers in [1,60]")
    raw_date = payload.get("dataApuracao")
    try:
        draw_date = datetime.strptime(str(raw_date), "%d/%m/%Y")
    except ValueError as exc:
        raise ValueError("official draw date must use DD/MM/YYYY") from exc
    return {
        "contest": contest,
        "draw_date": draw_date,
        "draw_date_text": draw_date.strftime("%d/%m/%Y"),
        "numbers": numbers,
        "accumulated": bool(payload.get("acumulado")),
    }

