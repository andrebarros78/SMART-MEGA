"""Independent preregistered cap-60 prospective audit, research-only.

Only a prior GitHub-committed registration + directly fetched official CAIXA
result can contribute to the prospective promotion gate. No production action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from smart_promotion_gate import assess_promotion_records

REGISTRATION_SCHEMA = "SMART_POST_CAP_PROSPECTIVE_REGISTRATION_1"
AUDIT_SCHEMA = "SMART_POST_CAP_PROSPECTIVE_AUDIT_1"
OFFICIAL_API = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/"
MIN_E_VALUE = 20.0  # 5% anytime-valid bound under the preregistered null


def canonical_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def strict_numbers(values: Any) -> list[int]:
    if (not isinstance(values, list) or len(values) != 6
            or any(type(x) is not int or not 1 <= x <= 60 for x in values)
            or len(set(values)) != 6):
        raise ValueError("exactly six distinct integer numbers 1..60 required")
    return sorted(values)


def _iso(text: Any) -> datetime:
    if not isinstance(text, str):
        raise ValueError("draw timestamp missing")
    date = datetime.fromisoformat(text)
    if date.tzinfo is None:
        raise ValueError("draw timestamp must have timezone")
    return date


def verify_registration(reg: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(reg, dict) or reg.get("schema") != REGISTRATION_SCHEMA:
        raise ValueError("registration schema mismatch")
    pin = reg.get("registration_sha256")
    unsigned = dict(reg)
    unsigned.pop("registration_sha256", None)
    if not isinstance(pin, str) or pin != canonical_sha256(unsigned):
        raise ValueError("registration self-hash mismatch")
    target = reg.get("target_contest")
    cutoff = reg.get("cutoff_contest")
    if type(target) is not int or type(cutoff) is not int or target <= 0 or cutoff != target - 1:
        raise ValueError("registration chronology invalid")
    if reg.get("status") != "REGISTERED_AWAITING_RESULT":
        raise ValueError("registration not pre-result")
    if _iso(reg.get("expected_draw_brasilia")).year < 2026:
        raise ValueError("invalid prospective target date")
    for key in ("baseline", "candidate"):
        source = reg.get(key)
        if not isinstance(source, dict):
            raise ValueError("missing model source")
        strict_numbers(source.get("numbers"))
        for field in ("source_commit", "source_file_sha256"):
            if not re.fullmatch(r"[a-f0-9]{40}" if field == "source_commit" else r"[a-f0-9]{64}",
                                str(source.get(field, ""))):
                raise ValueError("model source pin invalid")
    if not re.fullmatch(r"[a-f0-9]{64}", str(reg.get("source_dataset_sha256", ""))):
        raise ValueError("dataset pin invalid")
    controls = reg.get("controls")
    if (not isinstance(controls, dict) or controls.get("result_used") is not False
            or controls.get("actual_numbers") is not None
            or controls.get("adjudicated") is not False
            or controls.get("promote_to_main") is not False
            or controls.get("candidate_production_weight") != 0
            or controls.get("prediction_codes_frozen") is not True):
        raise ValueError("result leakage or production switch in registration")
    policy = reg.get("sequential_e_process")
    if (not isinstance(policy, dict) or policy.get("predeclared_factor") != "1 + (candidate_hits - baseline_hits)/12"
            or policy.get("initial_e_value") != 1
            or policy.get("minimum_e_value_for_promotion") != MIN_E_VALUE
            or policy.get("maximum_optional_stake_changes") != 0):
        raise ValueError("sequential policy not fixed before draw")
    sample = reg.get("sample_policy") or {}
    if (sample.get("min_contests") != 20
            or sample.get("existing_gate_e_value_at_least") != 10
            or sample.get("requires_adaptive_min_contests") is not True):
        raise ValueError("adaptive promotion contract mismatch")
    return reg


def parse_official_result(result: dict[str, Any], target: int) -> list[int]:
    if not isinstance(result, dict) or type(result.get("numero")) is not int:
        raise ValueError("official response missing contest number")
    if result["numero"] != target:
        raise ValueError("official contest is not registered target")
    if not isinstance(result.get("dataApuracao"), str):
        raise ValueError("official draw date missing")
    try:
        datetime.strptime(result["dataApuracao"], "%d/%m/%Y")
    except ValueError as exc:
        raise ValueError("official draw date invalid") from exc
    raw = result.get("listaDezenas")
    if not isinstance(raw, list):
        raise ValueError("official result lacks six dezenas")
    try:
        parsed = [int(x) if type(x) is str and re.fullmatch(r"\d{1,2}", x) else x
                  for x in raw]
    except Exception as exc:
        raise ValueError("official dezenas invalid") from exc
    return strict_numbers(parsed)


def fetch_caixa(target: int) -> dict[str, Any]:
    """Network evidence exists only after successful HTTPS fetch from CAIXA host."""
    url = OFFICIAL_API + str(target)
    if urlparse(url).hostname != "servicebus2.caixa.gov.br":
        raise ValueError("untrusted result provider")
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "SMART-MEGA-prospective-audit/1"})
    with urlopen(req, timeout=25) as response:
        actual_url = response.geturl()
        if urlparse(actual_url).scheme != "https" or urlparse(actual_url).hostname != "servicebus2.caixa.gov.br":
            raise ValueError("official result redirected to untrusted source")
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("official result oversized")
    result = json.loads(data.decode("utf-8-sig"))
    parse_official_result(result, target)
    return result



MIRROR_API = "https://loteriascaixa-api.herokuapp.com/api/megasena/"
MIRROR_ARCHIVE = "https://resultadomega.com.br/api/concursos.json"


def _get_json_url(url: str, expected_hostname: str, cap: int) -> Any:
    if urlparse(url).scheme != "https" or urlparse(url).hostname != expected_hostname:
        raise ValueError("untrusted mirror host")
    req = Request(url, headers={"Accept": "application/json",
                                "User-Agent": "SMART-MEGA-prospective-audit/1"})
    with urlopen(req, timeout=25) as response:
        u = urlparse(response.geturl())
        if u.scheme != "https" or u.hostname != expected_hostname:
            raise ValueError("mirror redirected off allowlist")
        body = response.read(cap + 1)
        if len(body) > cap:
            raise ValueError("mirror response oversized")
    return json.loads(body.decode("utf-8-sig"))


def fetch_mirror_consensus(target: int) -> dict[str, Any]:
    """Two different publishers; NEVER represents direct official CAIXA proof."""
    first = _get_json_url(MIRROR_API + str(target), "loteriascaixa-api.herokuapp.com", 200_000)
    second = _get_json_url(MIRROR_ARCHIVE, "resultadomega.com.br", 500_000)
    if type(first) is not dict or type(first.get("concurso")) is not int or first["concurso"] != target:
        raise ValueError("first mirror contest mismatch")
    a = strict_numbers([int(n) if isinstance(n, str) and re.fullmatch(r"\d{1,2}", n)
                        else n for n in first.get("dezenas", [])])
    try:
        d1 = datetime.strptime(first["data"], "%d/%m/%Y").date()
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("first mirror date invalid") from exc
    if not isinstance(second, list):
        raise ValueError("second mirror archive invalid")
    matches = [row for row in second if isinstance(row, list) and len(row) == 3
               and type(row[0]) is int and row[0] == target]
    if len(matches) != 1:
        raise ValueError("second mirror has no unique target")
    try:
        d2 = datetime.strptime(matches[0][1], "%Y-%m-%d").date()
        b = strict_numbers(matches[0][2])
    except (ValueError, TypeError) as exc:
        raise ValueError("second mirror data invalid") from exc
    if a != b or d1 != d2:
        raise ValueError("independent mirror result disagreement")
    return {
        "numero": target,
        "dataApuracao": d1.strftime("%d/%m/%Y"),
        "listaDezenas": [f"{n:02d}" for n in a],
        "evidence_kind": "TWO_MIRRORS_PROVISIONAL_NOT_OFFICIAL",
        "source_urls": [MIRROR_API + str(target), MIRROR_ARCHIVE],
        "first_publisher_sha256": canonical_sha256(first),
        "second_publisher_row_sha256": hashlib.sha256(
            json.dumps(matches[0], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }


def assess_series(registrations: list[dict[str, Any]],
                  official_results: list[dict[str, Any]], *,
                  fetched_directly_from_caixa: bool = False,
                  mirrors_crosschecked: bool = False) -> dict[str, Any]:
    if not registrations:
        return {"schema": AUDIT_SCHEMA, "status": "AWAITING_PROSPECTIVE_RESULTS",
                "n": 0, "eligible": False, "e_value": 1.0, "blockers": ["no_paired_official_results"]}
    targets = []
    for reg in registrations:
        verify_registration(reg)
        targets.append(reg["target_contest"])
    if targets != sorted(set(targets)) or any(b != a + 1 for a, b in zip(targets, targets[1:])):
        raise ValueError("registration targets duplicated, unordered or missing chronological contest")
    if len(official_results) > len(registrations):
        raise ValueError("more results than preregistrations")
    rows: list[dict[str, int]] = []
    delta: list[int] = []
    evalue = 1.0
    verified_observations = []
    for idx, response in enumerate(official_results):
        reg = registrations[idx]
        actual = parse_official_result(response, reg["target_contest"])
        expected_day = _iso(reg["expected_draw_brasilia"]).date()
        observed_day = datetime.strptime(response["dataApuracao"], "%d/%m/%Y").date()
        if observed_day != expected_day:
            raise ValueError("official draw date differs from preregistered date; manual audit required")
        bh = len(set(reg["baseline"]["numbers"]) & set(actual))
        ch = len(set(reg["candidate"]["numbers"]) & set(actual))
        d = ch - bh
        assert -6 <= d <= 6
        evalue *= 1.0 + d / 12.0
        rows.append({"champion_hits": bh, "challenger_hits": ch})
        delta.append(d)
        verified_observations.append({
            "target_contest": reg["target_contest"],
            "registration_sha256": reg["registration_sha256"],
            "baseline_hits": bh, "candidate_hits": ch, "delta": d,
            "official_response_sha256": canonical_sha256(response),
        })
    gate = assess_promotion_records(rows, evalue)
    eligible = bool(fetched_directly_from_caixa and gate["eligible"] and evalue >= MIN_E_VALUE)
    pending_targets = targets[len(rows):]
    blockers = list(gate["blockers"])
    if not fetched_directly_from_caixa:
        blockers.append("official_https_independence_not_verified")
    if evalue < MIN_E_VALUE:
        blockers.append("preregistered_95pct_e_process_below_20")
    if pending_targets:
        blockers.append("awaiting_next_chronological_draws")
    return {
        "schema": AUDIT_SCHEMA,
        "status": ("PROSPECTIVE_GATE_ELIGIBLE" if eligible else
                   "MIRROR_MATCH_PENDING_OFFICIAL" if mirrors_crosschecked and rows else
                   "PROSPECTIVE_NOT_PROVEN"),
        "eligible": eligible,
        "n": len(rows),
        "pairs_registered": len(registrations),
        "pending_targets": pending_targets,
        "baseline_hits": sum(r["champion_hits"] for r in rows),
        "candidate_hits": sum(r["challenger_hits"] for r in rows),
        "delta_total": sum(delta),
        "e_value": evalue,
        "predeclared_threshold": MIN_E_VALUE,
        "built_in_gate": gate,
        "observations": verified_observations,
        "blockers": sorted(set(blockers)),
        "official_provider": OFFICIAL_API if fetched_directly_from_caixa else None,
        "mirror_consensus_provisional": bool(mirrors_crosschecked and rows),
        "officially_verified_contests": len(rows) if fetched_directly_from_caixa else 0,
        "production_mutation": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("registration", nargs="+", type=Path)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--fetch-official", action="store_true")
    group.add_argument("--fetch-mirrors", action="store_true")
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    regs = [verify_registration(json.loads(path.read_text(encoding="utf-8-sig")))
            for path in a.registration]
    results = []
    if a.fetch_official or a.fetch_mirrors:
        for reg in regs:
            try:
                result = (fetch_caixa(reg["target_contest"]) if a.fetch_official
                          else fetch_mirror_consensus(reg["target_contest"]))
                results.append(result)
            except Exception as exc:
                # Never skip a missing target, accept a partial draw, or fake official verification.
                print(json.dumps({"status": "RESULT_NOT_VERIFIED", "target": reg["target_contest"],
                                  "detail": type(exc).__name__}), flush=True)
                break
    audit = assess_series(regs, results,
                          fetched_directly_from_caixa=bool(a.fetch_official and results),
                          mirrors_crosschecked=bool(a.fetch_mirrors and results))
    if a.out:
        if a.out.exists():
            raise FileExistsError("evaluation evidence is append-only; choose new path")
        a.out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
