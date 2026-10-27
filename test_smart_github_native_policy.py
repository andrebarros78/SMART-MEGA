"""No GitHub Actions; external governed execution; GitHub is canonical."""
import tempfile
import unittest
from pathlib import Path

from smart_github_native_policy import ACTIVE_INSTRUCTIONS, POLICY_ID, PolicyViolation, verify


class CanonicalGitHubExecutionPolicyTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        for name in ACTIVE_INSTRUCTIONS:
            (self.root / name).write_text(
                f"{POLICY_ID}\nandrebarros78/SMART-MEGA\nmain\n"
                "GitHub Actions PROIBIDO; executores externos autorizados para teste.\n",
                encoding="utf-8",
            )

    def test_external_execution_allowed_without_github_actions(self):
        r = verify(self.root)
        self.assertEqual(r["status"], "PASS")
        self.assertFalse(r["github_actions_authorized"])
        self.assertTrue(r["external_executors_authorized"])
        self.assertFalse(r["external_executor_permanent_dependency"])

    def test_legacy_actions_only_rule_denied(self):
        p = self.root / "README.md"
        p.write_text(p.read_text() + "Somente GitHub Actions em runners hospedados.\n")
        with self.assertRaisesRegex(PolicyViolation, "obsolete Actions-only"):
            verify(self.root)

    def test_live_workflow_denied(self):
        p = self.root / ".github/workflows/ci.yml"
        p.parent.mkdir(parents=True)
        p.write_text("on: push\n")
        with self.assertRaisesRegex(PolicyViolation, "GitHub Actions is prohibited"):
            verify(self.root)

    def test_nested_live_workflow_denied(self):
        p = self.root / ".github/workflows/nested/ci.yaml"
        p.parent.mkdir(parents=True)
        p.write_text("on: workflow_dispatch\n")
        with self.assertRaisesRegex(PolicyViolation, "GitHub Actions is prohibited"):
            verify(self.root)

    def test_archived_workflow_text_not_runnable(self):
        p = self.root / "docs/retired-github-actions/ci.yml.txt"
        p.parent.mkdir(parents=True)
        p.write_text("on: push\n")
        self.assertEqual(verify(self.root)["status"], "PASS")

    def test_policy_id_required_everywhere(self):
        p = self.root / "AGENTS.md"
        p.write_text("andrebarros78/SMART-MEGA\nmain\n")
        with self.assertRaisesRegex(PolicyViolation, "missing"):
            verify(self.root)

    def test_injected_github_origin_forbidden(self):
        p = self.root / "AI_START_HERE.md"
        p.write_text(POLICY_ID + "\nmain\n")
        with self.assertRaisesRegex(PolicyViolation, "missing"):
            verify(self.root)

    def test_symlink_workflows_denied(self):
        (self.root / "target").mkdir()
        d = self.root / ".github"
        d.mkdir()
        (d / "workflows").symlink_to(self.root / "target", target_is_directory=True)
        with self.assertRaisesRegex(PolicyViolation, "symlinked"):
            verify(self.root)


    def test_exact_obsolete_20261027_rules_are_rejected(self):
        for obsolete in (
            "Somente GitHub Actions com runners hospedados pelo GitHub podem executar testes e o produto.",
            "A execu\u00e7\u00e3o do produto ocorre exclusivamente em runners hospedados pelo GitHub",
            "PC Escola \u00e9 obrigat\u00f3rio para gerar cart\u00f5es",
            "PC Casa \u00e9 obrigat\u00f3rio para gerar cart\u00f5es",
        ):
            with self.subTest(obsolete=obsolete):
                p = self.root / "SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md"
                before = p.read_text(encoding="utf-8")
                try:
                    p.write_text(before + "\n" + obsolete + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(PolicyViolation, "obsolete|permanent"):
                        verify(self.root)
                finally:
                    p.write_text(before, encoding="utf-8")

    def test_actual_repository_policy_is_consistent(self):
        self.assertEqual(verify(Path(__file__).resolve().parent)["status"], "PASS")



if __name__ == "__main__":
    unittest.main()
