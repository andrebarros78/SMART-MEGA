"""Explicit, low-trust, two-source public Mega-Sena result capture.

This is NOT the CAIXA API, a cryptographic official attestation, a
scientific result corroboration, or an automatic model prediction.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

SCHEMA = "SMART_PUBLIC_CORROBORATED_RESULT_BATCH_1"
AUTHORITY = "TWO_PUBLIC_SOURCES_NOT_CAIXA_API_VERIFIED"
SOURCES = {
    "MEGASENA_DOT_COM": "https://www.megasena.com/resultados/{target}",
    "RESULTADOSDASLOTERIAS": "https://www.resultadosdasloterias.net/mega-sena/concurso/{target}",
}


def self_hash(doc: dict[str, Any]) -> str:
    body = {key: value for key, value in doc.items() if key != "sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _fetch(url: str) -> tuple[bytes, str]:
    with urlopen(Request(url, headers={"User-Agent": "SMART-MEGA/operational-public-corroboration",
                                      "Accept": "text/html"}), timeout=14) as resp:
        if resp.status != 200 or "text/html" not in resp.headers.get("Content-Type", "").lower():
            raise ValueError("public result provider did not return HTML")
        data = resp.read(512 * 1024 + 1)
        if len(data) > 512 * 1024:
            raise ValueError("public result provider payload too large")
        return data, resp.geturl()


def _parse(provider: str, raw: bytes, contest: int) -> tuple[str, list[int]]:
    if not raw or len(raw) > 512 * 1024:
        raise ValueError("public result HTML size invalid")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("public result HTML encoding invalid") from exc
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    if match is None:
        raise ValueError("public provider lacks a contest-specific title")
    from html import unescape
    title = unescape(match.group(1)).strip()
    info = re.search(r"Resultado da Mega[ -]Sena\s+(\d+)\s*[:\u2014-].*?(\d{2}/\d{2}/\d{4})",
                     title, flags=re.I | re.S)
    if info is None or int(info.group(1)) != contest:
        raise ValueError("public provider contest title mismatch")
    date_str = info.group(2)
    try:
        datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError as exc:
        raise ValueError("public provider date invalid") from exc
    if provider == "MEGASENA_DOT_COM":
        balls = re.findall(r'<li\s+class="ball"\s*>\s*(\d{1,2})\s*</li>', text, flags=re.I)
    elif provider == "RESULTADOSDASLOTERIAS":
        region = re.search(r'<div\s+class="balls[^"]*"\s+aria-label="Números sorteados"\s*>(.*?)</div>',
                           text, flags=re.I | re.S)
        if region is None:
            raise ValueError("public provider numbers container missing")
        balls = re.findall(r'<span\s+class="ball"\s*>\s*(\d{1,2})\s*</span>',
                           region.group(1), flags=re.I)
    else:
        raise ValueError("unknown public result provider")
    numbers = sorted(int(ball) for ball in balls)
    if len(numbers) != 6 or len(set(numbers)) != 6 or numbers[0] < 1 or numbers[-1] > 60:
        raise ValueError("public provider returned invalid six numbers")
    return date_str, numbers


def capture(target: int, *, fetcher: Callable[[str], tuple[bytes, str]] | None = None,
            clock: datetime | None = None) -> dict[str, Any]:
    if type(target) is not int or target < 1:
        raise ValueError("contest target invalid")
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("capture timestamp must have a timezone")
    read = fetcher or _fetch
    evidence = []
    observed = []
    for provider, template in SOURCES.items():
        url = template.format(target=target)
        raw, final_url = read(url)
        if final_url != url:
            raise ValueError("public provider unsafe redirect or wrong source URL")
        date, numbers = _parse(provider, raw, target)
        evidence.append({
            "provider": provider, "url": url,
            "html_sha256": hashlib.sha256(raw).hexdigest(),
            "http_response_body_captured": True,
            "draw_date": date, "numbers": numbers,
        })
        observed.append((date, numbers))
    if observed[0] != observed[1]:
        raise ValueError("public result providers disagree")
    date, numbers = observed[0]
    if datetime.strptime(date, "%d/%m/%Y").date() > now.astimezone(timezone.utc).date():
        raise ValueError("public result draw date is in future")
    record = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "raw_api_independently_verified": False,
        "scientific_certification_authorized": False,
        "predictive_weight_change_authorized": False,
        "capture_transport": "TWO_PUBLIC_WEB_SOURCES_CROSS_CHECK",
        "retrieved_at_utc": now.astimezone(timezone.utc).isoformat(),
        "providers": evidence,
        "results": [{
            "numero": target, "dataApuracao": date,
            "listaDezenas": [f"{num:02d}" for num in numbers],
            "source": "PUBLIC_CROSSCHECK_UNVERIFIED_OFFICIAL",
            "endpoint": None,
        }],
    }
    record["sha256"] = self_hash(record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect a NON-official two-source result batch")
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = capture(args.target)
    if args.output is not None:
        if args.output.is_symlink() or args.output.exists() or args.output.is_absolute() or ".." in args.output.parts:
            raise ValueError("public batch output must be new, project-relative and nonsymlink")
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
