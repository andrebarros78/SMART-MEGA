from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_canonical_identity import canonical_root
from smart_crash_safe_io import atomic_write_text
from smart_regression_evidence import junit_summary, sha256_file

SCHEMA = "SMART_CANONICAL_ROOT_V1"
DEFAULT_AUTHORITY = Path("SMART_CANONICAL_ROOT.json")
DEFAULT_JUNIT = Path("SMART_AUDIT_JUNIT_CURRENT.xml")


def _sha_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _git(root: Path, *args: str) -> str | None:
    completed = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _load_authority(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        raise ValueError("canonical root authority schema invalid")
    observed = obj.get("sha256")
    canonical = dict(obj); canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed != _sha_json(canonical):
        raise ValueError("canonical root authority self-hash invalid")
    return obj


def rebind(
    root: str | Path = ".",
    *,
    authority_path: str | Path = DEFAULT_AUTHORITY,
    junit_path: str | Path = DEFAULT_JUNIT,
    reason: str = "CURRENT_REGRESSION_PROMOTION",
) -> dict[str, Any]:
    root = Path(root).resolve()
    authority_path = Path(authority_path)
    if not authority_path.is_absolute():
        authority_path = root / authority_path
    junit_path = Path(junit_path)
    if not junit_path.is_absolute():
        junit_path = root / junit_path
    if not authority_path.is_file() or not junit_path.is_file():
        raise FileNotFoundError("canonical root authority and CURRENT JUnit are required")

    authority = _load_authority(authority_path)
    summary = junit_summary(junit_path)
    if summary.get("status") != "PASS" or int(summary.get("failures", -1)) != 0 or int(summary.get("errors", -1)) != 0:
        raise ValueError("CURRENT regression is not green; refusing canonical authority rebind")

    junit_sha = sha256_file(junit_path)
    updated = dict(authority)
    updated.pop("sha256", None)
    updated.update({
        "certified_regression_tests": int(summary["tests"]),
        "certified_regression_failures": int(summary["failures"]),
        "certified_regression_errors": int(summary["errors"]),
        "certified_regression_skipped": int(summary.get("skipped", 0)),
        "certified_regression_junit": junit_path.name,
        "certified_regression_junit_sha256": junit_sha,
        "certified_regression": {
            "junit_file": junit_path.name,
            "junit_sha256": junit_sha,
            "tests": int(summary["tests"]),
            "failures": int(summary["failures"]),
            "errors": int(summary["errors"]),
            "skipped": int(summary.get("skipped", 0)),
            "status": "PASS",
        },
        "authority_refreshed_at": datetime.now(timezone.utc).isoformat(),
        "authority_refresh_reason": str(reason),
    })
    branch = _git(root, "branch", "--show-current")
    head = _git(root, "rev-parse", "HEAD")
    if branch:
        updated["git_head"] = f"ref: refs/heads/{branch}"
    if head:
        updated["git_ref_sha"] = head
    updated["sha256"] = _sha_json(updated)

    temporary = authority_path.with_suffix(authority_path.suffix + ".tmp")
    atomic_write_text(temporary, json.dumps(updated, ensure_ascii=False, indent=2) + "\n")
    # Fail closed if the input authority changed while the new binding was built.
    latest = _load_authority(authority_path)
    if latest.get("sha256") != authority.get("sha256"):
        temporary.unlink(missing_ok=True)
        raise RuntimeError("canonical root authority changed during rebind")
    temporary.replace(authority_path)
    return {
        "status": "PASS",
        "authority_file": authority_path.name,
        "authority_sha256": updated["sha256"],
        "junit_file": junit_path.name,
        "junit_sha256": junit_sha,
        "tests": int(summary["tests"]),
        "failures": int(summary["failures"]),
        "errors": int(summary["errors"]),
        "skipped": int(summary.get("skipped", 0)),
        "reason": str(reason),
    }


def main() -> None:
    result = rebind(canonical_root())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
