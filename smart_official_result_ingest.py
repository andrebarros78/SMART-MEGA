from __future__ import annotations
from smart_canonical_identity import canonical_root

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from smart_http_guard import read_limited_bytes
from smart_official_result_validation import validate_official_payload

API_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{contest}"
BALL_COLUMNS = tuple(f"Bola{i}" for i in range(1, 7))
SCHEMA = "SMART_OFFICIAL_RESULT_INGEST_1"
OFFICIAL_JSON_MAX_BYTES = 2 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_official_payload(target: int, timeout: float = 20.0) -> tuple[dict[str, Any], str]:
    url = API_URL.format(contest=int(target))
    response = requests.get(  # nosec B113 - explicit bounded timeout and bounded streamed read
        url,
        headers={"Accept": "application/json", "User-Agent": "SMART-MEGA/official-ingest"},
        timeout=float(timeout),
        stream=True,
    )
    response.raise_for_status()
    raw = read_limited_bytes(response, max_bytes=OFFICIAL_JSON_MAX_BYTES)
    payload = json.loads(raw.decode("utf-8-sig"))
    validate_official_payload(payload, target)
    return payload, url


def build_extended_frame(source: Path, target: int, official: dict[str, Any]) -> pd.DataFrame:
    source = Path(source)
    if not source.is_file():
        raise ValueError("source dataset is missing")
    frame = pd.read_excel(source)
    required = {"Concurso", "Data do Sorteio", *BALL_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"source dataset missing columns: {missing}")
    contests = [int(value) for value in frame["Concurso"].tolist()]
    if contests != sorted(contests) or len(contests) != len(set(contests)):
        raise ValueError("source contests must be unique and strictly ordered")
    if not contests or contests[-1] != int(target) - 1:
        raise ValueError("source dataset must end exactly at target-1")
    if int(target) in set(contests):
        raise ValueError("target already exists in source dataset")
    row = {column: None for column in frame.columns}
    row["Concurso"] = int(target)
    row["Data do Sorteio"] = official["draw_date"]
    for column, number in zip(BALL_COLUMNS, official["numbers"]):
        row[column] = int(number)
    extended = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
    if int(extended.iloc[-1]["Concurso"]) != int(target):
        raise RuntimeError("extended dataset target mismatch")
    return extended


def _atomic_excel_write(frame: pd.DataFrame, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing dataset: {output}")
    handle, temporary = tempfile.mkstemp(prefix=output.stem + ".", suffix=".tmp.xlsx", dir=output.parent)
    os.close(handle)
    temporary_path = Path(temporary)
    try:
        frame.to_excel(temporary_path, index=False)
        os.replace(temporary_path, output)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def ingest(source: Path, output: Path, proof: Path, target: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    source = Path(source)
    output = Path(output)
    proof = Path(proof)
    if proof.exists():
        raise FileExistsError(f"refusing to overwrite existing proof: {proof}")
    if payload is None:
        # A missing operator result cannot trigger an implicit network call.
        # Locate the immutable operator authority along the caller's own
        # project-local dataset ancestry (canonical or epoch snapshot).
        from smart_operator_result import fetch as operator_fetch
        source_parent = source.resolve().parent
        roots = (source_parent, *source_parent.parents)
        project_root = next(
            (candidate for candidate in roots
             if (candidate / f"SMART_OPERATOR_RESULT_{int(target)}.json").is_file()),
            None,
        )
        if project_root is None:
            raise ValueError("operator result required; automatic CAIXA ingestion disabled")
        payload, _ = operator_fetch(project_root, target)
    endpoint = None if payload.get("source") == "OPERATOR" else API_URL.format(contest=int(target))
    official = validate_official_payload(payload, target)
    source_sha = sha256_file(source)
    frame = build_extended_frame(source, target, official)
    _atomic_excel_write(frame, output)
    result = {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "official_endpoint": endpoint,
        "result_input_authority": "OPERATOR" if payload.get("source") == "OPERATOR" else "CAIXA_CONTEST_API",
        "source_independently_verified": payload.get("source") != "OPERATOR",
        "target_contest": int(target),
        "draw_date": official["draw_date_text"],
        "actual_numbers": official["numbers"],
        "source_file": source.name,
        "source_sha256": source_sha,
        "output_file": output.name,
        "output_sha256": sha256_file(output),
        "row_count": int(len(frame)),
        "cutoff_before_ingest": int(target) - 1,
        "official_payload_validated": True,
        "append_only_dataset": True,
        "future_information_used_for_prior_predictions": False,
    }
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result["sha256"] = hashlib.sha256(canonical).hexdigest()
    proof.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True, type=int)
    parser.add_argument("--out", required=True)
    parser.add_argument("--proof", required=True)
    args = parser.parse_args()
    result = ingest(Path(args.source), Path(args.out), Path(args.proof), args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    canonical_root()
    main()
