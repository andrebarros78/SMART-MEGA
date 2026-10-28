"""Scoped research succession: preserve original F11/F12 while pinning fail-closed fine-tuning changes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from smart_f12_scientific_successor import evaluate as evaluate_f12
from smart_ai_fine_tuning import build_authority, SCHEMA as FINE_TUNING_SCHEMA

SCHEMA = "SMART_F12_SCIENTIFIC_SUCCESSOR_V2_SCOPE_1"
ARCHIVE = "SMART_F12_SCIENTIFIC_SUCCESSOR.json"
FINE_TUNING = "smart_ai_fine_tuning.py"
PINNED_F12_ARCHIVE_SHA256 = "149b8ac92c6f25855cc6035c8d107608663c4f8e557f292fae7682cf1315b50b"
PINNED_FINE_TUNING_LF_SHA256 = "97a095bc404dca9cffa21a9ebdb9f913d6021573c02e9d2de1068bcd4f42aa7a"
EXPECTED_OLD_F12_FAILED_CHECK = "all_other_predictive_sources_preserved_after_exact_guard_reversal"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(data: bytes) -> str:
    return sha256(data.replace(b"\r\n", b"\n"))


def _json_hash(report: dict) -> str:
    return sha256(json.dumps(report, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8"))


def _forged_promotion_rejected() -> bool:
    candidate = {"candidate_id": "challenger", "eta": 0.5,
                 "redundancy_threshold": 0.85, "meta_strength": 0.06}
    report = {"schema": FINE_TUNING_SCHEMA, "status": "PASS",
              "adjudication": {"effective_candidate_id": "challenger",
                               "promotion_authorized": True},
              "results": [{"candidate": candidate}]}
    try:
        build_authority(report)
    except ValueError:
        return True
    return False


def evaluate(root: str | Path) -> dict:
    root = Path(root).resolve()
    archived_raw = (root / ARCHIVE).read_bytes()
    archived = json.loads(archived_raw.decode("utf-8-sig"))
    predecessor = evaluate_f12(root)
    broken = [k for k, v in predecessor["checks"].items() if v is not True]
    changed = [k for k, v in predecessor["sources"].items()
               if v["approved_f11_source_preserved"] is not True]
    source_hash = _canonical_hash((root / FINE_TUNING).read_bytes())
    checks = {
        "original_f12_archive_unchanged":
            sha256(archived_raw) == PINNED_F12_ARCHIVE_SHA256,
        "original_f12_archive_self_hash_and_status_valid":
            archived.get("status") == "PASS"
            and archived.get("sha256") ==
                _json_hash({k: v for k, v in archived.items() if k != "sha256"}),
        "f12_original_fails_closed":
            predecessor["status"] == "FAIL"
            and broken == [EXPECTED_OLD_F12_FAILED_CHECK],
        "only_fine_tuning_deviates_from_f11_approved_sources":
            changed == [FINE_TUNING],
        "fine_tuning_successor_exactly_pinned":
            source_hash == PINNED_FINE_TUNING_LF_SHA256,
        "other_f12_historical_comparison_unchanged":
            archived["historical_comparison"] == predecessor["historical_comparison"],
        "other_f12_sources_preserved":
            all(v["approved_f11_source_preserved"] for k, v in predecessor["sources"].items()
                if k != FINE_TUNING),
        "independent_prospective_proof_not_claimed":
            predecessor["prospective_advantage_proven"] is False
            and predecessor["six_of_six_proven"] is False
            and archived["prospective_advantage_proven"] is False,
        "forged_promotion_rejected": _forged_promotion_rejected(),
    }
    report = {
        "schema": SCHEMA,
        "status": "PASS_SCOPE_ONLY" if all(checks.values()) else "FAIL",
        "prior_gate_live_status": predecessor["status"],
        "approved_successor_source_sha256": source_hash,
        "archived_f12_sha256": sha256(archived_raw),
        "checks": checks,
        "effective_model_promotion_authorized": False,
        "predictive_superiority_proven": False,
        "scope": "FAIL_CLOSED_FINE_TUNING_RESEARCH_SUCCESSOR_NO_F12_REWRITE",
        "note": "F12 must remain FAIL for the changed source. This separate exact-hash "
                "scope proof allows research evaluation only, not official promotion.",
    }
    report["sha256"] = _json_hash(report)
    return report


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", type=Path)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    result = evaluate(Path(__file__).resolve().parent)
    out = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        args.write.write_text(out, encoding="utf-8")
    if args.check:
        if not args.check.is_file() or args.check.read_text(encoding="utf-8") != out:
            print("SCOPED_SCIENTIFIC_SUCCESSOR_EVIDENCE_MISMATCH")
            return 1
    print(json.dumps({"status": result["status"], "checks": result["checks"]},
                     ensure_ascii=False))
    return 0 if result["status"] == "PASS_SCOPE_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
