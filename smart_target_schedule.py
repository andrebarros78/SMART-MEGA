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
PORTABLE_ARCHIVE = Path("portable_evidence/cronogramas_caixa")
PORTABLE_ARCHIVE_MANIFEST = Path("SMART_PORTABLE_CAIXA_CRONOGRAM_ARCHIVE_MANIFEST.json")
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



def _validate_portable_archive(root: Path, archive_path: Path) -> None:
    manifest_path = (root / PORTABLE_ARCHIVE_MANIFEST).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"portable CAIXA cronogram manifest missing: {manifest_path}")
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("portable CAIXA cronogram manifest unreadable") from exc
    if not isinstance(doc, dict) or doc.get("schema") != "SMART_PORTABLE_CAIXA_CRONOGRAM_ARCHIVE_1":
        raise ValueError("portable CAIXA cronogram manifest schema invalid")
    observed = doc.get("sha256")
    canonical = dict(doc)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or len(observed) != 64 or observed.lower() != _sha256_json(canonical):
        raise ValueError("portable CAIXA cronogram manifest self-hash invalid")
    items = doc.get("items")
    declared_count = doc.get("file_count")
    if isinstance(declared_count, bool) or not isinstance(declared_count, int) or declared_count <= 0:
        raise ValueError("portable CAIXA cronogram manifest file_count invalid")
    if not isinstance(items, list) or len(items) != declared_count:
        raise ValueError("portable CAIXA cronogram manifest item count mismatch")
    declared: dict[str, tuple[int, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("portable CAIXA cronogram manifest item invalid")
        name = item.get("file")
        size = item.get("bytes")
        digest = item.get("sha256")
        if not isinstance(name, str) or not re.fullmatch(r"\d{4}-\d{2}\.pdf", name):
            raise ValueError("portable CAIXA cronogram manifest filename invalid")
        if name in declared:
            raise ValueError("portable CAIXA cronogram manifest duplicate filename")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ValueError("portable CAIXA cronogram manifest size invalid")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("portable CAIXA cronogram manifest sha256 invalid")
        declared[name] = (size, digest.lower())
    actual_names = {f.name for f in archive_path.glob("*.pdf") if f.is_file()}
    if actual_names != set(declared):
        raise ValueError("portable CAIXA cronogram archive file set differs from manifest")
    for name, (size, digest) in declared.items():
        pdf = archive_path / name
        if not pdf.is_file() or pdf.stat().st_size != size or sha256_file(pdf).lower() != digest:
            raise ValueError(f"portable CAIXA cronogram evidence integrity failure: {name}")

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


def resolve_target_schedule(
    root: str | Path,
    target_contest: int,
    archive: str | Path = DEFAULT_ARCHIVE,
    time_policy: str | Path = DEFAULT_TIME_POLICY,
) -> dict[str, Any]:
    root = Path(root).resolve()
    requested_archive = Path(archive)
    archive_path = requested_archive
    if not archive_path.is_absolute():
        archive_path = (root / archive_path).resolve()
    portable_fallback = False
    if not archive_path.is_dir() and requested_archive == DEFAULT_ARCHIVE:
        portable_archive = (root / PORTABLE_ARCHIVE).resolve()
        if portable_archive.is_dir():
            archive_path = portable_archive
            portable_fallback = True
    if not archive_path.is_dir():
        raise FileNotFoundError(f"CAIXA cronogram archive missing: {archive_path}")
    if portable_fallback:
        _validate_portable_archive(root, archive_path)

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


__all__ = ["SCHEMA", "DEFAULT_ARCHIVE", "PORTABLE_ARCHIVE", "PORTABLE_ARCHIVE_MANIFEST", "DEFAULT_TIME_POLICY", "TIME_POLICY_SCHEMA", "TEMPORAL_GUARD_SCHEMA", "MIN_OPERATIONAL_FREEZE_LEAD_SECONDS", "assert_pre_draw_window", "extract_target_from_text", "load_draw_time_policy", "resolve_target_schedule", "sha256_file"]
