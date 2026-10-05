"""Verify the delivered GitHub main checkout with real read-only operator calls."""
from __future__ import annotations
import datetime, hashlib, json, subprocess, sys, time
from pathlib import Path

root = Path.cwd().resolve()
archive = root / "SMART_STATE_ARCHIVE" / "DEEP_REPAIR_20261005"
output = archive / "SMART_DELIVERY_VERIFICATION.json"

def git(*args):
    return subprocess.check_output(["git", *args], cwd=root, text=True, timeout=60).strip()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def remote_main():
    return git("-c", "credential.interactive=never", "ls-remote", "origin", "refs/heads/main").split()[0]

def snapshot():
    names = ["Mega-Sena.xlsx", "SMART_OPERATIONAL_LIFECYCLE.json", "SMART_NEXT_CYCLE_HOLD.json",
             "SMART_MISSION_STATUS.json", "SMART_SIGNAL_LEDGER.json", "SMART_SIGNAL_STATE.json"]
    return {name: sha(root / name) for name in names}

record = {"schema": "SMART_DELIVERY_VERIFICATION_V1", "status": "RUNNING",
          "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "verified_commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
          "remote_main_before": remote_main(), "production_operations": ["status", "preflight"],
          "generation_performed": False, "timings_seconds": {}}
before = snapshot()
failure = None
try:
    assert record["branch"] == "main"
    assert record["verified_commit"] == record["remote_main_before"]
    assert not git("status", "--porcelain")
    record["repository_clean_before_verification"] = True
    replies = {}
    for name, args in [("status", ["status"]), ("preflight", ["preflight", "--target", "3067"])]:
        started = time.perf_counter()
        process = subprocess.run([sys.executable, "-E", "-B", "-X", "utf8", "smart_operator.py", *args],
                                 cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=180)
        assert process.returncode == 0, (name, process.stderr)
        replies[name] = json.loads(process.stdout)
        record["timings_seconds"][name] = round(time.perf_counter() - started, 6)
        record[name + "_exit_code"] = process.returncode
        record[name + "_stderr"] = process.stderr
        print(name + ": " + str(replies[name].get("status")), flush=True)
    status, preflight = replies["status"], replies["preflight"]
    assert status["status"] == "OK"
    assert not status["reconciled_state"]["failed_checks"]
    assert status["active_operation"] is None
    assert preflight["status"] == "AWAITING_OPERATOR_AUTHORIZATION"
    assert preflight["phase"] == "OPERATOR_HOLD" and preflight["mutated_state"] is False
    certificate = status["product_certification"]
    assert certificate["status"] == "CONSTRUCTION_PROVEN"
    assert sha(root / "SMART_AUDIT_JUNIT_CURRENT.xml") == "d48f1365ba33bbdc06a5a517c9e8b29a5b54b1d90832e836de4f43a58ce61467"
    after = snapshot()
    assert before == after
    life = json.loads((root / "SMART_OPERATIONAL_LIFECYCLE.json").read_text(encoding="utf-8-sig"))
    assert life["state"] == "HOLD" and life["target_contest"] == 3067
    record.update({"status": "PASS", "operator_status": status["status"],
                   "startup_failed_checks": status["reconciled_state"]["failed_checks"],
                   "preflight_status": preflight["status"], "preflight_phase": preflight["phase"],
                   "mutated_state": False, "active_operation": None,
                   "lifecycle_state": life["state"], "target_contest": life["target_contest"],
                   "certification_sha256": certificate["sha256"],
                   "current_code_certification_validated_by_preflight": True,
                   "production_sha256_before": before, "production_sha256_after": after,
                   "production_hashes_unchanged": True,
                   "remote_main_after": remote_main()})
    assert record["remote_main_after"] == record["verified_commit"]
    assert not git("status", "--porcelain")
except Exception as exc:
    failure = exc
    record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
finally:
    record["completed_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)
if failure is not None:
    raise failure
