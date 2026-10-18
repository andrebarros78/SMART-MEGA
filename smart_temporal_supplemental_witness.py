"""Read-only supplemental temporal evidence for SMART-MEGA target 3071.

It intentionally does NOT create or amend the pre-draw temporal guard and
never grants learning, history advancement or predictive promotion authority.
A GitHub PR creation timestamp is trustworthy as a PR event timestamp, not as
a timestamp on every current commit/file in that PR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA = "SMART_SUPPLEMENTAL_TEMPORAL_WITNESS_3071_1"
REG_COMMIT = "e7e896c192d5a0840196e2b6cd3d70ee763c2113"
REG_PATH = "release_evidence/PROSPECTIVE_CAP60/REGISTRATION_3071.json"
REPO = "andrebarros78/SMART-MEGA"
PR_NUMBER = 54
PR_API = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}"
PR_COMMITS_API = f"{PR_API}/commits?per_page=100"


def digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def parsed_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("GitHub endpoint redirected")


def fetch_github_json(url: str) -> Any:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.github.com" or parsed.username or parsed.password:
        raise ValueError("untrusted GitHub API endpoint")
    if url not in (PR_API, PR_COMMITS_API):
        raise ValueError("GitHub API resource outside allowlist")
    req = Request(url, headers={"Accept": "application/vnd.github+json",
                                "User-Agent": "SMART-MEGA-independent-temporal-research/1",
                                "X-GitHub-Api-Version": "2022-11-28"})
    with build_opener(_NoRedirects()).open(req, timeout=22) as response:
        if response.geturl() != url:
            raise ValueError("GitHub API endpoint changed")
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("GitHub API response exceeded limit")
    return json.loads(raw.decode("utf-8"))


def _git_registration(root: Path) -> dict[str, Any]:
    try:
        payload = subprocess.check_output(
            ["git", "show", f"{REG_COMMIT}:{REG_PATH}"], cwd=root, timeout=12)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("pinned preregistration Git object unavailable") from exc
    return json.loads(payload.decode("utf-8"))


def _valid_six(numbers: Any) -> bool:
    return (isinstance(numbers, list) and len(numbers) == 6
            and all(type(n) is int and 1 <= n <= 60 for n in numbers)
            and len(set(numbers)) == 6)


def evaluate(root: str | Path, pr: dict[str, Any], commits: list[dict[str, Any]]) -> dict[str, Any]:
    root = Path(root).resolve()
    reg = _git_registration(root)
    signed = {k: v for k, v in reg.items() if k != "registration_sha256"}
    if (reg.get("schema") != "SMART_POST_CAP_PROSPECTIVE_REGISTRATION_1"
            or reg.get("registration_sha256") != digest(signed)
            or reg.get("target_contest") != 3071 or reg.get("cutoff_contest") != 3070
            or reg.get("official_draw_time_verified_by_caixa") is not False
            or reg.get("controls", {}).get("result_used") is not False
            or reg.get("controls", {}).get("actual_numbers") is not None
            or reg.get("controls", {}).get("promote_to_main") is not False
            or not _valid_six(reg.get("baseline", {}).get("numbers"))
            or not _valid_six(reg.get("candidate", {}).get("numbers"))):
        raise ValueError("pinned preregistration invalid or has result leakage")

    freeze_relative = reg["source_freeze"]["path"]
    freeze = (root / freeze_relative).resolve()
    if not freeze.is_relative_to(root) or not freeze.is_file():
        raise ValueError("original frozen artifact missing or escaped repository")
    raw = freeze.read_bytes()
    git_blob = blob_sha1(raw)
    if git_blob != reg["source_freeze"]["github_blob_sha"]:
        raise ValueError("original freeze differs from preregistered Git blob")

    frozen = json.loads(raw.decode("utf-8-sig"))
    active = json.loads((root / "SMART_ACTIVE_EPOCH.json").read_text(encoding="utf-8-sig"))
    guard = active.get("temporal_guard", {})
    frozen_guard = frozen.get("temporal_guard", {})
    if (frozen.get("target_contest") != 3071 or frozen.get("cutoff_contest") != 3070
            or frozen.get("frozen_before_result") is not True
            or frozen.get("causal_cutoff") is not True
            or sorted(frozen["champion"]["top6"]) != sorted(reg["baseline"]["numbers"])
            or active.get("target_contest") != 3071
            or active.get("status") != "FROZEN"
            or active.get("freeze_authority", {}).get("sha256") != hashlib.sha256(raw).hexdigest()
            or active.get("target_schedule", {}).get("scheduled_datetime") is not None
            or guard.get("status") != "OPERATOR_UNVERIFIED_DRAW_TIME"
            or guard.get("before_scheduled_draw") is not False
            or guard.get("result_used") is not False
            or frozen_guard.get("status") != "OPERATOR_UNVERIFIED_DRAW_TIME"
            or frozen_guard.get("before_scheduled_draw") is not False):
        raise ValueError("original authority or pre-draw guard does not match archived evidence")
    if not isinstance(pr, dict) or pr.get("number") != PR_NUMBER:
        raise ValueError("wrong public pull request")
    if (pr.get("base", {}).get("repo", {}).get("full_name") != REPO
            or pr.get("head", {}).get("repo", {}).get("full_name") != REPO):
        raise ValueError("wrong GitHub repository")
    if type(commits) is not list or not (1 <= len(commits) < 100):
        raise ValueError("unbounded or paginated GitHub PR commit list")
    shas = [c.get("sha") for c in commits if isinstance(c, dict)]
    if len(shas) != len(commits) or any(not isinstance(s, str) or not re.fullmatch(r"[0-9a-f]{40}", s) for s in shas):
        raise ValueError("malformed GitHub PR commits")
    if len(set(shas)) != len(shas) or shas[0] != REG_COMMIT or shas[-1] != pr.get("head", {}).get("sha"):
        raise ValueError("GitHub PR Git-chain head/preregistration mismatch")
    for prev, entry in zip(shas, commits[1:]):
        parents = entry.get("parents", [])
        if not any(isinstance(p, dict) and p.get("sha") == prev for p in parents):
            raise ValueError("GitHub PR ancestry not a linear anchored history")
    created = parsed_timestamp(pr.get("created_at"))
    expected_draw = parsed_timestamp(reg.get("expected_draw_brasilia"))
    if created >= expected_draw:
        raise ValueError("GitHub PR was not created before registered draw")
    official_result = json.loads((root / "SMART_OPERATOR_RESULT_3071.json").read_text(encoding="utf-8-sig"))
    actual_date = datetime.strptime(official_result.get("draw_date", ""), "%d/%m/%Y").date()
    if actual_date != expected_draw.date() or not _valid_six(official_result.get("actual_numbers")):
        raise ValueError("registered date conflicts with outcome authority")
    if created.date() >= actual_date:
        raise ValueError("GitHub PR not demonstrably on a prior UTC calendar day")

    document = {
        "schema": SCHEMA,
        "status": "SUPPLEMENTAL_CHRONOLOGY_CORROBORATED_REVIEW_REQUIRED",
        "target_contest": 3071,
        "preregistered_commit": REG_COMMIT,
        "preregistered_registration_sha256": reg["registration_sha256"],
        "github_pull_request": f"https://github.com/{REPO}/pull/{PR_NUMBER}",
        "github_pr_created_at_utc": created.isoformat(),
        "github_pr_current_head": shas[-1],
        "github_pr_commits_observed": len(shas),
        "github_pr_prereg_commit_is_first": True,
        "original_freeze_git_blob_sha1": git_blob,
        "original_freeze_sha256": hashlib.sha256(raw).hexdigest(),
        "registered_draw_at_utc": expected_draw.isoformat(),
        "pre_draw_calendar_margin_days": (actual_date - created.date()).days,
        "uncertainty": {
            "github_pr_created_at_is_server_timestamp": True,
            "exact_initial_PR_head_at_creation_cryptographically_proven": False,
            "commit_authored_at_time_is_trusted_server_timestamp": False,
            "caixa_scheduled_draw_time_independently_verified": False,
            "signed_trusted_pre_draw_timestamp_for_exact_freeze": False,
            "independent_review_and_authority_signature_present": False,
        },
        "controls": {
            "original_frozen_temporal_guard_rewritten": False,
            "temporal_guard_pass": False,
            "allows_post_result_learning": False,
            "allows_history_advance": False,
            "allows_champion_promotion": False,
            "needs_authorized_security_review": True,
        },
        "next_required_gate": "Secure independent reviewer must assess exact-at-creation evidence and official calendar; typed approved recovery would require separate authorized code change and nonregression tests.",
    }
    document["sha256"] = digest(document)
    return document


def verify_record(record: dict[str, Any]) -> None:
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError("supplemental witness schema mismatch")
    plain = {k: v for k, v in record.items() if k != "sha256"}
    if record.get("sha256") != digest(plain):
        raise ValueError("supplemental witness self-hash mismatch")
    if record.get("status") != "SUPPLEMENTAL_CHRONOLOGY_CORROBORATED_REVIEW_REQUIRED":
        raise ValueError("supplemental witness invalid status")
    ctl = record.get("controls", {})
    if any(ctl.get(flag) is not False for flag in ("original_frozen_temporal_guard_rewritten",
              "temporal_guard_pass", "allows_post_result_learning", "allows_history_advance",
              "allows_champion_promotion")) or ctl.get("needs_authorized_security_review") is not True:
        raise ValueError("supplemental witness attempts unauthorized promotion")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--output", default=None)
    ap.add_argument("--connector-snapshot", default=None)
    args = ap.parse_args()
    if args.connector_snapshot:
        snap_path = (Path(args.root).resolve() / args.connector_snapshot).resolve()
        if not snap_path.is_relative_to(Path(args.root).resolve()) or not snap_path.is_file():
            raise ValueError("connector snapshot missing or outside repository")
        evidence = json.loads(snap_path.read_text(encoding="utf-8"))
        if (evidence.get("schema") != "SMART_GITHUB_CONNECTOR_PR54_POSTDRAW_SNAPSHOT_1"
                or evidence.get("source_type") != "github_authenticated_connector"
                or evidence.get("retrieved_after_draw") is not True
                or evidence.get("pr_api_url") != PR_API
                or evidence.get("commits_api_url") != PR_COMMITS_API):
            raise ValueError("connector snapshot source contract invalid")
        pr = evidence["pr"]
        commits = evidence["commits"]
        source = "GITHUB_CONNECTOR_POST_DRAW_SNAPSHOT_NOT_SIGNED"
        source_hash = hashlib.sha256(snap_path.read_bytes()).hexdigest()
    else:
        pr = fetch_github_json(PR_API)
        commits = fetch_github_json(PR_COMMITS_API)
        source = "GITHUB_API_LIVE_HTTPS"
        source_hash = None
    record = evaluate(args.root, pr, commits)
    # Provenance only; neither acquisition path can create a trustworthy
    # pre-result initial-head timestamp or grant learning authority.
    record["acquisition"] = {"source": source, "snapshot_sha256": source_hash,
                              "fetched_after_target_draw": True}
    record["sha256"] = digest({k: v for k, v in record.items() if k != "sha256"})
    verify_record(record)
    if args.output:
        path = (Path(args.root).resolve() / args.output).resolve()
        if not path.is_relative_to(Path(args.root).resolve()):
            raise ValueError("output escapes canonical root")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as fd:
            json.dump(record, fd, ensure_ascii=False, indent=2)
            fd.write("\n")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
