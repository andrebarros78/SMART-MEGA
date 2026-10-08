from __future__ import annotations

from copy import deepcopy

from smart_full_process_pipeline import _fine_tuning_consumed_by_challenger


def _fixture():
    sha = "a" * 64
    tuning = {"authority_sha256": sha, "data_sha256": "b" * 64,
              "target_contest": 3068, "cutoff_contest": 3067}
    authority = {"sha256": sha, "data_sha256": "b" * 64,
                 "target_contest": 3068, "cutoff_contest": 3067,
                 "future_result_used": False, "holdout_used_for_selection": False,
                 "effective_candidate": {"eta": 0.7, "redundancy_threshold": 0.8,
                                         "meta_strength": 0.06}}
    frozen = {"ai_hyperparameter_authority": authority,
              "promotion_lineage": {"ai_hyperparameter_authority_sha256": sha,
                                    "eta": 0.7, "redundancy_threshold": 0.8,
                                    "meta_strength": 0.06},
              "challenger": {"target_contest": 3068, "cutoff_contest": 3067,
                             "top6": [1, 2, 3, 4, 5, 6]}}
    return frozen, tuning


def test_top_level_authority_and_effective_agent_params_prove_consumption():
    frozen, tuning = _fixture()
    assert _fine_tuning_consumed_by_challenger(frozen, tuning) is True


def test_wrong_lineage_authority_is_rejected():
    frozen, tuning = _fixture()
    frozen["promotion_lineage"]["ai_hyperparameter_authority_sha256"] = "c" * 64
    assert not _fine_tuning_consumed_by_challenger(frozen, tuning)


def test_authority_declared_but_not_applied_is_rejected():
    frozen, tuning = _fixture()
    frozen["promotion_lineage"]["meta_strength"] = 0.12
    assert not _fine_tuning_consumed_by_challenger(frozen, tuning)


def test_missing_top_level_authority_is_rejected():
    frozen, tuning = _fixture()
    frozen.pop("ai_hyperparameter_authority")
    assert not _fine_tuning_consumed_by_challenger(frozen, tuning)


def test_noncausal_or_wrong_cutoff_authority_is_rejected():
    frozen, tuning = _fixture()
    frozen["ai_hyperparameter_authority"]["future_result_used"] = True
    assert not _fine_tuning_consumed_by_challenger(frozen, tuning)
    frozen, tuning = _fixture()
    frozen["challenger"]["cutoff_contest"] = 3066
    assert not _fine_tuning_consumed_by_challenger(frozen, tuning)
