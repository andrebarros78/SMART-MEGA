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
