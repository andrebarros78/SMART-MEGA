from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from smart_http_guard import read_limited_bytes
from smart_official_result_ingest import API_URL, BALL_COLUMNS, OFFICIAL_JSON_MAX_BYTES, validate_official_payload

DOWNLOAD_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/resultados/download?modalidade=Mega-Sena"
SCHEMA = "SMART_OFFICIAL_EVIDENCE_CONSENSUS_V1"
OFFICIAL_XLSX_MAX_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class SecondaryObservation:
    status: str
    max_contest: int
    numbers: tuple[int, ...] | None
    draw_date_text: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "max_contest": self.max_contest,
            "numbers": None if self.numbers is None else list(self.numbers),
            "draw_date_text": self.draw_date_text,
        }


def observe_download_frame(frame: pd.DataFrame, target: int) -> SecondaryObservation:
    required = {"Concurso", "Data do Sorteio", *BALL_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"official download missing columns: {missing}")
    contests = frame["Concurso"].astype(int)
    if contests.empty:
        raise ValueError("official download is empty")
    if contests.duplicated().any():
        raise ValueError("official download contains duplicate contests")
    max_contest = int(contests.max())
    rows = frame[contests == int(target)]
    if max_contest < int(target):
        if len(rows):
            raise ValueError("official download target/max inconsistency")
        return SecondaryObservation(
            status="STALE_BEFORE_TARGET",
            max_contest=max_contest,
            numbers=None,
            draw_date_text=None,
        )
    if len(rows) != 1:
        raise ValueError("official download reached target range but target is not unique")
    row = rows.iloc[0]
    numbers = tuple(sorted(int(row[column]) for column in BALL_COLUMNS))
    if len(set(numbers)) != 6 or numbers[0] < 1 or numbers[-1] > 60:
        raise ValueError("official download target row contains invalid numbers")
    raw_date = pd.to_datetime(row["Data do Sorteio"], dayfirst=True, errors="raise")
    return SecondaryObservation(
        status="TARGET_PRESENT",
        max_contest=max_contest,
        numbers=numbers,
        draw_date_text=raw_date.strftime("%d/%m/%Y"),
    )


def corroborate(
    primary_payload: dict[str, Any],
    target: int,
    secondary_frame: pd.DataFrame | None = None,
    secondary_error: str | None = None,
) -> dict[str, Any]:
    primary = validate_official_payload(primary_payload, target)
    if secondary_frame is not None and secondary_error is not None:
        raise ValueError("secondary frame and secondary error are mutually exclusive")

    secondary = None
    if secondary_frame is not None:
        secondary = observe_download_frame(secondary_frame, target)
        if secondary.status == "TARGET_PRESENT":
            if list(secondary.numbers or ()) != primary["numbers"]:
                raise ValueError("official CAIXA channels disagree on drawn numbers")
            if secondary.draw_date_text != primary["draw_date_text"]:
                raise ValueError("official CAIXA channels disagree on draw date")
            status = "DUAL_CAIXA_CHANNEL_CONSENSUS"
            corroborated = True
        else:
            status = "PRIMARY_CAIXA_API_VALID_SECONDARY_DOWNLOAD_STALE"
            corroborated = False
    else:
        status = "PRIMARY_CAIXA_API_VALID_SECONDARY_UNAVAILABLE"
        corroborated = False

    return {
        "schema": SCHEMA,
        "target_contest": int(target),
        "primary": {
            "channel": "CAIXA_CONTEST_API",
            "endpoint": API_URL.format(contest=int(target)),
            "numbers": primary["numbers"],
            "draw_date": primary["draw_date_text"],
            "validated": True,
        },
        "secondary": None if secondary is None else {
            "channel": "CAIXA_CONSOLIDATED_RESULTS_DOWNLOAD",
            "endpoint": DOWNLOAD_URL,
            **secondary.to_dict(),
        },
        "secondary_error": secondary_error,
        "status": status,
        "operational_adjudication_authorized": True,
        "dual_channel_corroborated": corroborated,
        "terminal_source_corroboration_authorized": corroborated,
        "independent_audit_still_required_for_terminal_6of6": True,
        "predictive_weight_authorized": False,
        "terminal_6of6_proven": False,
    }


def fetch_secondary_download(timeout: float = 25.0) -> pd.DataFrame:
    response = requests.get(  # nosec B113 - explicit bounded timeout and bounded streamed read
        DOWNLOAD_URL,
        headers={"Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "User-Agent": "SMART-MEGA/official-corroboration"},
        timeout=float(timeout),
        stream=True,
    )
    response.raise_for_status()
    raw = read_limited_bytes(response, max_bytes=OFFICIAL_XLSX_MAX_BYTES)
    return pd.read_excel(io.BytesIO(raw))


def fetch_consensus(target: int, timeout: float = 25.0) -> tuple[dict[str, Any], dict[str, Any]]:
    primary_response = requests.get(  # nosec B113 - explicit bounded timeout and bounded streamed read
        API_URL.format(contest=int(target)),
        headers={"Accept": "application/json", "User-Agent": "SMART-MEGA/official-corroboration"},
        timeout=float(timeout),
        stream=True,
    )
    primary_response.raise_for_status()
    primary_raw = read_limited_bytes(primary_response, max_bytes=OFFICIAL_JSON_MAX_BYTES)
    primary_payload = json.loads(primary_raw.decode("utf-8-sig"))
    try:
        secondary = fetch_secondary_download(timeout=timeout)
    except Exception as exc:
        result = corroborate(primary_payload, target, secondary_error=f"{type(exc).__name__}: {exc}")
    else:
        result = corroborate(primary_payload, target, secondary_frame=secondary)
    return primary_payload, result


def write_consensus(path: str | Path, document: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
