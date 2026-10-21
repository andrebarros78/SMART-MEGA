"""Negative and positive cases for repository-only execution authority."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from smart_github_native_policy import (
    ACTIVE_INSTRUCTIONS, REQUIRED_WORKFLOWS, PolicyViolation, verify,
)


class NativeOnlyContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for filename in ACTIVE_INSTRUCTIONS:
            (self.root / filename).write_text(
                "SMART_GITHUB_NATIVE_ONLY_20261021\n"
                "GitHub andrebarros78/SMART-MEGA main\n",
                encoding="utf-8",
            )
        (self.root / "smart_github_operator.py").write_text(
            "GITHUB_REPOSITORY GITHUB_REF GITHUB_EVENT_NAME refs/heads/main\n",
            encoding="utf-8",
        )
        for filename in REQUIRED_WORKFLOWS:
            path = self.root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - run: python smart_github_native_policy.py\n"
                "      - run: pip install -r requirements.lock.txt\n",
                encoding="utf-8",
            )

    def test_only_hosted_native_workflows_pass(self):
        result = verify(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["external_execution_allowed"])
        self.assertEqual(result["hosted_jobs"], 3)

    def test_explicit_old_federated_permission_is_rejected(self):
        path = self.root / "README.md"
        path.write_text(path.read_text() + "GitHub Actions ou executor federado autorizado\n")
        with self.assertRaisesRegex(PolicyViolation, "legacy external"):
            verify(self.root)

    def test_self_hosted_executor_is_rejected(self):
        path = self.root / REQUIRED_WORKFLOWS[0]
        path.write_text(path.read_text().replace("ubuntu-latest", "self-hosted"))
        with self.assertRaisesRegex(PolicyViolation, "non-GitHub-hosted"):
            verify(self.root)

    def test_lmcp_runner_dispatch_is_rejected(self):
        path = self.root / REQUIRED_WORKFLOWS[1]
        path.write_text(path.read_text() + "      - run: lmcp job start\n")
        with self.assertRaisesRegex(PolicyViolation, "external dispatch"):
            verify(self.root)

    def test_checker_cannot_be_bypassed_by_deleting_step(self):
        path = self.root / REQUIRED_WORKFLOWS[0]
        path.write_text(path.read_text().replace("      - run: python smart_github_native_policy.py\n", ""))
        with self.assertRaisesRegex(PolicyViolation, "every job"):
            verify(self.root)

    def test_checker_must_run_before_dependency_installation(self):
        path = self.root / REQUIRED_WORKFLOWS[0]
        path.write_text(path.read_text().replace(
            "      - run: python smart_github_native_policy.py\n"
            "      - run: pip install -r requirements.lock.txt\n",
            "      - run: pip install -r requirements.lock.txt\n"
            "      - run: python smart_github_native_policy.py\n",
        ))
        with self.assertRaisesRegex(PolicyViolation, "before native policy"):
            verify(self.root)

    def test_all_active_agent_entrypoints_require_marker(self):
        path = self.root / "AGENTS.md"
        path.write_text("andrebarros78/SMART-MEGA main\n")
        with self.assertRaisesRegex(PolicyViolation, "missing canonical marker"):
            verify(self.root)

    def test_external_runner_workflow_cannot_be_hidden(self):
        path = self.root / ".github/workflows/obsolete-vps.yml"
        path.write_text("jobs:\n  old:\n    runs-on: self-hosted\n")
        with self.assertRaisesRegex(PolicyViolation, "non-GitHub-hosted"):
            verify(self.root)

    def test_hostless_operator_loses_authority(self):
        path = self.root / "smart_github_operator.py"
        path.write_text("GITHUB_REF refs/heads/main\n")
        with self.assertRaisesRegex(PolicyViolation, "operator lost"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
