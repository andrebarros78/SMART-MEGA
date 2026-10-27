from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from pypdf import PdfReader

SCHEMA = "SMART_TARGET_SCHEDULE_AUTHORITY_3"
DEFAULT_ARCHIVE = Path("runtime/procedural_sources/cronogramas_caixa")
DEFAULT_TIME_POLICY = Path("SMART_MEGA_SENA_DRAW_TIME_POLICY.json")
TIME_POLICY_SCHEMA = "SMART_MEGA_SENA_DRAW_TIME_POLICY_1"
TEMPORAL_GUARD_SCHEMA = "SMART_PRE_DRAW_TEMPORAL_GUARD_1"
MIN_OPERATIONAL_FREEZE_LEAD_SECONDS = 60
_DATE_LINE = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s+([^\r\n]+)$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_draw_time_policy(root: str | Path, path: str | Path = DEFAULT_TIME_POLICY) -> tuple[dict[str, Any], Path]:
    root = Path(root).resolve()
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = (root / resolved).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Mega-Sena draw-time policy missing: {resolved}")
    obj = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema") != TIME_POLICY_SCHEMA or obj.get("status") != "ACTIVE":
        raise ValueError("Mega-Sena draw-time policy schema/status invalid")
    observed = obj.get("sha256")
    canonical = dict(obj); canonical.pop("sha256", None)
    if not isinstance(observed, str) or len(observed) != 64 or observed.lower() != _sha256_json(canonical):
        raise ValueError("Mega-Sena draw-time policy self-hash invalid")
    if obj.get("self_hash_required") is not True or obj.get("fail_closed_on_missing_weekday") is not True:
        raise ValueError("Mega-Sena draw-time policy fail-closed flags invalid")
    timezone_name = obj.get("timezone")
    if not isinstance(timezone_name, str):
        raise ValueError("Mega-Sena draw-time policy timezone missing")
    ZoneInfo(timezone_name)
    times = obj.get("weekday_times")
    if not isinstance(times, dict) or not times:
        raise ValueError("Mega-Sena draw-time policy weekday_times missing")
    effective = obj.get("effective_from")
    try:
        datetime.strptime(str(effective), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Mega-Sena draw-time policy effective_from invalid") from exc
    return obj, resolved


def assert_pre_draw_window(
    schedule: dict[str, Any],
    *,
    now: datetime | None = None,
    minimum_lead_seconds: int = MIN_OPERATIONAL_FREEZE_LEAD_SECONDS,
) -> dict[str, Any]:
    if not isinstance(schedule, dict) or schedule.get("schema") != SCHEMA:
        raise ValueError("target schedule authority invalid for temporal guard")
    if schedule.get("authority") == "OPERATOR_SELECTED_TARGET":
        if (schedule.get("operator_selected_target") is not True
                or schedule.get("result_used") is not False
                or schedule.get("scheduled_datetime") is not None
                or not isinstance(schedule.get("target_contest"), int)):
            raise ValueError("operator target authority is invalid")
        return {
            "schema": TEMPORAL_GUARD_SCHEMA, "status": "OPERATOR_UNVERIFIED_DRAW_TIME",
            "target_contest": int(schedule["target_contest"]),
            "checked_at_utc": (datetime.now(timezone.utc) if now is None else now).astimezone(timezone.utc).isoformat(),
            "scheduled_datetime": None, "seconds_until_draw": None,
            "minimum_lead_seconds": None, "before_scheduled_draw": False,
            "operator_selected": True, "result_used": False,
        }
    scheduled_raw = schedule.get("scheduled_datetime")
    if not isinstance(scheduled_raw, str):
        raise ValueError("target schedule lacks scheduled_datetime")
    try:
        scheduled = datetime.fromisoformat(scheduled_raw)
    except ValueError as exc:
        raise ValueError("target scheduled_datetime invalid") from exc
    if scheduled.tzinfo is None or scheduled.utcoffset() is None:
        raise ValueError("target scheduled_datetime must be timezone-aware")
    if isinstance(minimum_lead_seconds, bool) or not isinstance(minimum_lead_seconds, int) or minimum_lead_seconds < 0:
        raise ValueError("minimum freeze lead seconds must be a non-negative integer")
    observed = datetime.now(timezone.utc) if now is None else now
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("temporal guard now must be timezone-aware")
    observed_utc = observed.astimezone(timezone.utc)
    scheduled_utc = scheduled.astimezone(timezone.utc)
    seconds_until_draw = (scheduled_utc - observed_utc).total_seconds()
    if seconds_until_draw <= float(minimum_lead_seconds):
        raise ValueError(
            f"prospective freeze window closed or inside safety margin: "
            f"target={schedule.get('target_contest')} scheduled={scheduled.isoformat()} "
            f"seconds_until_draw={seconds_until_draw:.3f} required_lead={minimum_lead_seconds}"
        )
    return {
        "schema": TEMPORAL_GUARD_SCHEMA,
        "status": "PASS",
        "target_contest": int(schedule["target_contest"]),
        "checked_at_utc": observed_utc.isoformat(),
        "scheduled_datetime": scheduled.isoformat(),
        "seconds_until_draw": seconds_until_draw,
        "minimum_lead_seconds": int(minimum_lead_seconds),
        "before_scheduled_draw": True,
        "result_used": False,
    }


def extract_target_from_text(text: str, target_contest: int) -> dict[str, str]:
    target = str(int(target_contest))
    token = re.compile(rf"(?<!\d){re.escape(target)}(?!\d)")
    matches: list[dict[str, str]] = []
    for raw in str(text).splitlines():
        line = " ".join(raw.split())
        match = _DATE_LINE.match(line)
        if not match or not token.search(line):
            continue
        date_text = match.group(1)
        rest = match.group(2)
        weekday = rest.split()[0] if rest.split() else ""
        matches.append({"target_date": date_text, "weekday": weekday, "source_line": line})
    unique = {(row["target_date"], row["source_line"]): row for row in matches}
    if len(unique) != 1:
        raise ValueError(f"target contest {target_contest} must resolve to exactly one dated cronogram line; matches={len(unique)}")
    return next(iter(unique.values()))


def _previous_contest_date(root: Path, target_contest: int) -> datetime:
    data = root / "Mega-Sena.xlsx"
    if not data.is_file():
        raise FileNotFoundError("canonical Mega-Sena.xlsx is required to bind target schedule to modality sequence")
    frame = pd.read_excel(data)
    required = {"Concurso", "Data do Sorteio"}
    if not required.issubset(frame.columns):
        raise ValueError("canonical Mega-Sena.xlsx lacks Concurso/Data do Sorteio columns")
    contests = pd.to_numeric(frame["Concurso"], errors="raise").astype(int)
    previous = int(target_contest) - 1
    rows = frame.loc[contests == previous, "Data do Sorteio"]
    if len(rows) != 1:
        raise ValueError(f"canonical Mega-Sena previous contest {previous} must occur exactly once")
    value = pd.to_datetime(rows.iloc[0], dayfirst=True, errors="raise")
    return value.to_pydatetime().replace(tzinfo=None)


def _operator_selected_schedule(root: Path, target_contest: int) -> dict[str, Any] | None:
    """Explicit target instruction; no inferred draw date, time or external fetch."""
    target = int(target_contest)
    active_path = root / "SMART_ACTIVE_EPOCH.json"
    if active_path.is_file():
        from smart_learning_epoch_reset import verify_active_epoch
        active = verify_active_epoch(active_path)
        existing = active.get("target_schedule")
        if (int(active.get("target_contest", -1)) == target
                and active.get("operator_selected_target") is True
                and isinstance(existing, dict)
                and existing.get("authority") == "OPERATOR_SELECTED_TARGET"):
            return existing

    authority_path = root / "SMART_NEXT_CYCLE_AUTHORITY.json"
    if not authority_path.is_file():
        return None
    doc = json.loads(authority_path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict) or doc.get("schema") != "SMART_NEXT_CYCLE_AUTHORITY_1":
        raise ValueError("operator target authority invalid")
    observed = doc.get("sha256")
    canonical = dict(doc)
    canonical.pop("sha256", None)
    if observed != _sha256_json(canonical):
        raise ValueError("operator target authority self-hash mismatch")
    if (int(doc.get("target_contest", -1)) != target
            or doc.get("authorized_by") != "USER_EXPLICIT_APPLY_OR_GENERATE"
            or doc.get("status") not in {"AUTHORIZED", "RESERVED", "CONSUMED_FOR_PREPARE"}):
        return None
    return {
        "schema": SCHEMA, "target_contest": target, "previous_contest": target - 1,
        "target_date": None, "weekday": None, "scheduled_datetime": None,
        "scheduled_timezone": None, "source_file": authority_path.name,
        "source_sha256": observed, "source_count": 1,
        "authority": "OPERATOR_SELECTED_TARGET", "operator_selected_target": True,
        "draw_time_independently_verified": False, "schedule_consensus": False,
        "result_used": False,
    }



def _verified_caixa_previous_result_schedule(root: Path, target: int, time_policy: str | Path) -> dict[str, Any] | None:
    """Use a byte-pinned CAIXA previous-result receipt for a corrected next-draw date.

    The receipt is a separately captured HTTPS response, stored immutably with
    the repository. Only previous-draw fields are accepted; no target result
    is read. A malformed or contradictory receipt fails closed.
    """
    relative = Path("runtime/procedural_sources/caixa_api_previous") / f"{target - 1}.json"
    source = root / relative
    if not source.exists():
        return None
    if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(root):
        raise ValueError("CAIXA next contest receipt path is unsafe")
    raw = source.read_bytes()
    if not raw or len(raw) > 262144:
        raise ValueError("CAIXA next contest receipt size invalid")
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("CAIXA next contest receipt invalid JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("CAIXA next contest receipt must be object")
    if type(document.get("numero")) is not int or document["numero"] != target - 1:
        raise ValueError("CAIXA previous contest identity mismatch")
    if type(document.get("numeroConcursoProximo")) is not int or document["numeroConcursoProximo"] != target:
        raise ValueError("CAIXA next contest identity mismatch")
    previous = _previous_contest_date(root, target)
    try:
        reported_previous = datetime.strptime(document["dataApuracao"], "%d/%m/%Y")
        next_date = datetime.strptime(document["dataProximoConcurso"], "%d/%m/%Y")
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("CAIXA next contest dates invalid") from exc
    if reported_previous.date() != previous.date() or next_date <= previous:
        raise ValueError("CAIXA next contest date contradicts canonical history")
    balls = document.get("listaDezenas")
    try:
        numeric_balls = [int(n) for n in balls]
    except (ValueError, TypeError) as exc:
        raise ValueError("CAIXA previous contest balls invalid") from exc
    if len(numeric_balls) != 6 or len(set(numeric_balls)) != 6 or not all(1 <= n <= 60 for n in numeric_balls):
        raise ValueError("CAIXA previous contest balls invalid")
    policy, policy_path = load_draw_time_policy(root, time_policy)
    time_text = policy["weekday_times"].get(str(next_date.weekday()))
    if not isinstance(time_text, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time_text):
        raise ValueError("CAIXA verified next contest has no applicable draw-time policy")
    hour, minute = map(int, time_text.split(":"))
    scheduled = next_date.replace(hour=hour, minute=minute, tzinfo=ZoneInfo(policy["timezone"]))
    source_hash = sha256_file(source)
    return {
        "schema": SCHEMA, "target_contest": target, "previous_contest": target - 1,
        "previous_contest_date": previous.strftime("%d/%m/%Y"),
        "target_date": next_date.strftime("%d/%m/%Y"),
        "weekday": str(next_date.weekday()),
        "scheduled_datetime": scheduled.isoformat(),
        "scheduled_timezone": policy["timezone"],
        "draw_time_policy_file": policy_path.relative_to(root).as_posix(),
        "draw_time_policy_sha256": sha256_file(policy_path),
        "draw_time_policy_authority": policy["authority"],
        "source_file": relative.as_posix(), "source_sha256": source_hash,
        "source_count": 1, "sources": [{"file": relative.as_posix(), "sha256": source_hash}],
        "modality_binding": "MEGA_SENA_PREVIOUS_CONTEST_SEQUENCE",
        "schedule_consensus": False,
        "authority": "CAIXA_PREVIOUS_RESULT_API_RECEIPT",
        "result_used": False,
    }

def resolve_target_schedule(
    root: str | Path,
    target_contest: int,
    archive: str | Path = DEFAULT_ARCHIVE,
    time_policy: str | Path = DEFAULT_TIME_POLICY,
) -> dict[str, Any]:
    root = Path(root).resolve()
    verified = _verified_caixa_previous_result_schedule(root, int(target_contest), time_policy)
    if verified is not None:
        return verified
    operator = _operator_selected_schedule(root, int(target_contest))
    if operator is not None:
        return operator
    archive_path = Path(archive)
    if not archive_path.is_absolute():
        archive_path = (root / archive_path).resolve()
    if not archive_path.is_dir():
        raise FileNotFoundError(f"CAIXA cronogram archive missing: {archive_path}")

    previous_date = _previous_contest_date(root, int(target_contest))
    candidates: list[tuple[Path, dict[str, str], datetime]] = []
    rejected_before_cutoff: list[dict[str, str]] = []
    for pdf in sorted(archive_path.glob("*.pdf"), reverse=True):
        reader = PdfReader(str(pdf))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        try:
            row = extract_target_from_text(text, int(target_contest))
        except ValueError as exc:
            if "matches=0" in str(exc):
                continue
            raise
        row_date = datetime.strptime(row["target_date"], "%d/%m/%Y")
        if row_date <= previous_date:
            rejected_before_cutoff.append({
                "file": str(pdf.relative_to(root)).replace("\\", "/"),
                "target_date": row["target_date"],
                "reason": "NOT_AFTER_PREVIOUS_MEGA_SENA_CONTEST",
            })
            continue
        candidates.append((pdf, row, row_date))

    if not candidates:
        raise ValueError(f"target contest {target_contest} has no archived CAIXA cronogram occurrence after previous Mega-Sena contest date")

    nearest_date = min(row_date for _, _, row_date in candidates)
    nearest = [(pdf, row) for pdf, row, row_date in candidates if row_date == nearest_date]
    schedule_keys = {(row["target_date"], row["weekday"].casefold()) for _, row in nearest}
    if len(schedule_keys) != 1:
        details = [
            {
                "file": str(pdf.relative_to(root)).replace("\\", "/"),
                "target_date": row["target_date"],
                "weekday": row["weekday"],
            }
            for pdf, row in nearest
        ]
        raise ValueError(f"conflicting nearest CAIXA cronogram occurrences for target {target_contest}: {details}")

    policy, policy_path = load_draw_time_policy(root, time_policy)
    effective_from = datetime.strptime(str(policy["effective_from"]), "%Y-%m-%d")
    if nearest_date < effective_from:
        raise ValueError("target predates current Mega-Sena draw-time policy")
    weekday_key = str(nearest_date.weekday())
    time_text = policy["weekday_times"].get(weekday_key)
    if not isinstance(time_text, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time_text):
        raise ValueError(f"Mega-Sena draw time unavailable for weekday={weekday_key}")
    hour, minute = (int(x) for x in time_text.split(":"))
    scheduled = nearest_date.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=ZoneInfo(policy["timezone"]))

    pdf, row = nearest[0]
    sources = [
        {
            "file": str(source_pdf.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(source_pdf),
            "source_line": source_row["source_line"],
        }
        for source_pdf, source_row in nearest
    ]
    return {
        "schema": SCHEMA,
        "target_contest": int(target_contest),
        "previous_contest": int(target_contest) - 1,
        "previous_contest_date": previous_date.strftime("%d/%m/%Y"),
        "target_date": row["target_date"],
        "weekday": row["weekday"],
        "scheduled_datetime": scheduled.isoformat(),
        "scheduled_timezone": policy["timezone"],
        "draw_time_policy_file": str(policy_path.relative_to(root)).replace("\\", "/"),
        "draw_time_policy_sha256": sha256_file(policy_path),
        "draw_time_policy_authority": policy["authority"],
        "source_file": sources[0]["file"],
        "source_sha256": sources[0]["sha256"],
        "source_line": row["source_line"],
        "source_count": len(sources),
        "sources": sources,
        "rejected_occurrences_before_cutoff": rejected_before_cutoff,
        "modality_binding": "MEGA_SENA_PREVIOUS_CONTEST_SEQUENCE",
        "schedule_consensus": True,
        "authority": "CAIXA_ARCHIVED_CRONOGRAM_PDF",
        "result_used": False,
    }


__all__ = ["SCHEMA", "DEFAULT_ARCHIVE", "DEFAULT_TIME_POLICY", "TIME_POLICY_SCHEMA", "TEMPORAL_GUARD_SCHEMA", "MIN_OPERATIONAL_FREEZE_LEAD_SECONDS", "assert_pre_draw_window", "extract_target_from_text", "load_draw_time_policy", "resolve_target_schedule", "sha256_file"]
