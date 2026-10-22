from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from smart_operation_lock import OperationLock, OperationalLockError, read_lock_metadata


def test_operation_lock_acquire_release_metadata(tmp_path):
    lock = OperationLock(tmp_path, operation="TEST", target_contest=42)
    active = lock.acquire()
    assert active["status"] == "ACTIVE"
    assert active["operation"] == "TEST"
    assert active["target_contest"] == 42
    assert active["recovery"]["os_lock_is_authority"] is True
    released = lock.release()
    assert released["status"] == "RELEASED"
    metadata = read_lock_metadata(tmp_path)
    assert metadata["status"] == "RELEASED"
    assert metadata["_self_hash_valid"] is True


def test_operation_lock_is_exclusive_across_processes(tmp_path):
    script = r'''
import json, sys, time
from smart_operation_lock import OperationLock
root=sys.argv[1]
lock=OperationLock(root, operation="CHILD", target_contest=7)
lock.acquire()
print(json.dumps({"status":"LOCKED"}), flush=True)
time.sleep(30)
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent)
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        assert proc.stdout is not None
        line = proc.stdout.readline().strip()
        assert json.loads(line)["status"] == "LOCKED"
        contender = OperationLock(tmp_path, operation="PARENT", target_contest=7)
        with pytest.raises(OperationalLockError, match="operation lock is held"):
            contender.acquire()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.mark.parametrize("failure_stage", ["acquire_metadata", "release_metadata", "release_unlock"])
@pytest.mark.parametrize("exception_name", ["OSError", "KeyboardInterrupt"])
def test_operation_lock_releases_resource_after_failure(tmp_path, failure_stage, exception_name):
    """A retained traceback must not keep the next real operation locked out."""
    script = r'''
import json, sys
from unittest.mock import patch
import smart_operation_lock as locks
root, stage, exception_name = sys.argv[1:]
owner = locks.OperationLock(root, operation="FAILING_OPERATION", target_contest=7)
if stage != "acquire_metadata":
    owner.acquire()
failure = (OSError if exception_name == "OSError" else KeyboardInterrupt)("injected failure")
callback = "_release_os_lock" if stage == "release_unlock" else "_write_metadata"
retained_exception = None
with patch.object(locks, callback, side_effect=failure):
    try:
        owner.acquire() if stage == "acquire_metadata" else owner.release()
    except BaseException as exc:
        retained_exception = exc
assert retained_exception is failure, "the original failure must propagate"
assert owner._handle is None, "failed operations must relinquish their handle"
with locks.OperationLock(root, operation="RECOVERY", target_contest=7) as contender:
    assert contender.metadata["status"] == "ACTIVE"
    assert contender.metadata["recovery"]["os_lock_is_authority"] is True
    assert contender.metadata["recovery"]["stale_metadata_recovered"] is (stage == "release_metadata")
released = locks.read_lock_metadata(root)
assert released["status"] == "RELEASED" and released["_self_hash_valid"] is True
print(json.dumps({"stage": stage, "exception": exception_name, "recovered": True}))
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent)
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), failure_stage, exception_name],
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["recovered"] is True
