"""Contract: signed full-suite Linux provenance is not GitHub Actions or a PC."""
from __future__ import annotations
import ast
import hashlib
import json
import re
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import patch

from smart_source_identity import sha256_source_bytes


def extracted(path: str, name: str, **symbols):
    source = Path(__file__).resolve().with_name(path).read_text()
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {"Path": Path, "PurePosixPath": PurePosixPath, "re": re, "uuid": uuid, "subprocess": subprocess,
          "hashlib": hashlib, "json": json, **symbols}
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, "exec"), ns)
    return ns[name]


class TestLinuxProvenance(unittest.TestCase):
    def test_explicit_linux_vps_provenance_is_retired(self):
        fn = extracted("smart_github_certify.py", "execution_provenance",
                       os=SimpleNamespace(environ={}),
                       socket=SimpleNamespace(gethostname=lambda: "wmcp-cloud-01"),
                       sys=SimpleNamespace(platform="linux"))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "remote", "add", "origin",
                            "https://github.com/andrebarros78/SMART-MEGA.git"],
                           cwd=root, check=True)
            uid = str(uuid.uuid4())
            with self.assertRaisesRegex(PermissionError, "retired"):
                fn(root, "a" * 40, uid, "wmcp-cloud-01",
                   executor_kind="LMCP_LINUX_VPS")

    def test_linux_vps_label_cannot_be_claimed_by_wrong_host(self):
        fn = extracted("smart_github_certify.py", "execution_provenance",
                       os=SimpleNamespace(environ={}),
                       socket=SimpleNamespace(gethostname=lambda: "other-host"),
                       sys=SimpleNamespace(platform="linux"))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "remote", "add", "origin",
                            "https://github.com/andrebarros78/SMART-MEGA.git"],
                           cwd=root, check=True)
            with self.assertRaises(PermissionError):
                fn(root, "a" * 40, str(uuid.uuid4()), "other-host",
                   executor_kind="LMCP_LINUX_VPS")

    def test_old_federated_pc_provenance_is_retired(self):
        fn = extracted("smart_github_certify.py", "execution_provenance",
                       os=SimpleNamespace(environ={}),
                       socket=SimpleNamespace(gethostname=lambda: "wmcp-cloud-01"),
                       sys=SimpleNamespace(platform="linux"))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "remote", "add", "origin",
                            "https://github.com/andrebarros78/SMART-MEGA.git"],
                           cwd=root, check=True)
            with self.assertRaisesRegex(PermissionError, "retired"):
                fn(root, "a" * 40, str(uuid.uuid4()), "wmcp-cloud-01",
                   executor_kind="FEDERATED_PC")

    def test_product_certifier_validates_exact_linux_execution(self):
        fn = extracted("smart_product_certification.py", "regression_source_binding",
                       sha256_file=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
                       sha256_source_bytes=sha256_source_bytes)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "remote", "add", "origin",
                            "https://github.com/andrebarros78/SMART-MEGA.git"],
                           cwd=root, check=True)
            (root / "smart_example.py").write_text("X=1\n")
            subprocess.run(["git", "add", "smart_example.py"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=ci@example.org",
                            "commit", "-qm", "baseline"], cwd=root, check=True)
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                    text=True, capture_output=True, check=True).stdout.strip()
            junit = root / "test.xml"
            junit.write_text('<testsuite tests="1" failures="0" errors="0"><testcase name="a"/></testsuite>')
            identity = {"kind": "LMCP_LINUX_VPS", "provider": "LMCP",
                        "execution_id": str(uuid.uuid4()), "hostname": "wmcp-cloud-01"}
            fp = {"sha256": "f" * 64, "files": [
                {"path": "smart_example.py",
                 "sha256": sha256_source_bytes((root / "smart_example.py").read_bytes())}]}
            authority = {
                "certified_source_commit": commit, "certified_ci_run_id": None,
                "certified_execution": identity,
                "certified_source_code_fingerprint_sha256": fp["sha256"],
                "certified_regression_junit_sha256": hashlib.sha256(junit.read_bytes()).hexdigest(),
            }
            (root / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority))
            ok = fn(root, junit, fp)
            self.assertEqual(ok["status"], "FAIL")
            self.assertFalse(ok["checks"]["execution_recorded"])
            identity["hostname"] = "PC-ESCOLA"
            (root / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority))
            denied = fn(root, junit, fp)
            self.assertEqual(denied["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
