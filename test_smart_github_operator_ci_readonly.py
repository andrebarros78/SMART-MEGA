"""TDD: canonical full regression must not confuse its JUnit candidate with an operator mutation."""
import unittest

from smart_github_operator import _allow_regression_candidate_readonly


class CandidateJUnitReadOnlyBoundary(unittest.TestCase):
    def test_show_card_may_read_while_unstaged_candidate_junit_is_temporarily_removed(self):
        self.assertTrue(_allow_regression_candidate_readonly(
            "show-card", " D SMART_AUDIT_JUNIT_CANDIDATE.xml\n", "1"
        ))

    def test_unstaged_candidate_rewrite_also_allowed(self):
        self.assertTrue(_allow_regression_candidate_readonly(
            "show-card", " M SMART_AUDIT_JUNIT_CANDIDATE.xml\n", "1"
        ))

    def test_environment_flag_alone_cannot_allow_other_dirty_files(self):
        self.assertFalse(_allow_regression_candidate_readonly(
            "show-card", " D SMART_AUDIT_JUNIT_CANDIDATE.xml\n M smart_operator.py\n", "1"
        ))

    def test_staged_candidate_update_not_allowed(self):
        self.assertFalse(_allow_regression_candidate_readonly(
            "show-card", "M  SMART_AUDIT_JUNIT_CANDIDATE.xml\n", "1"
        ))

    def test_write_operation_never_allowed(self):
        self.assertFalse(_allow_regression_candidate_readonly(
            "generate-card", " D SMART_AUDIT_JUNIT_CANDIDATE.xml\n", "1"
        ))

    def test_normal_readonly_outside_runner_not_allowed(self):
        self.assertFalse(_allow_regression_candidate_readonly(
            "show-card", " D SMART_AUDIT_JUNIT_CANDIDATE.xml\n", ""
        ))

    def test_untracked_artifact_not_allowed(self):
        self.assertFalse(_allow_regression_candidate_readonly(
            "show-card", "?? SMART_AUDIT_JUNIT_CANDIDATE.xml\n", "1"
        ))

    def test_path_suffix_attack_rejected(self):
        self.assertFalse(_allow_regression_candidate_readonly(
            "show-card", " D SMART_AUDIT_JUNIT_CANDIDATE.xml/../smart_operator.py\n", "1"
        ))


if __name__ == "__main__":
    unittest.main()
