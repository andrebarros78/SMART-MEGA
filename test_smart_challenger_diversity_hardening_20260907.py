from __future__ import annotations

import numpy as np

from smart_independent_oracle import validate_prediction_snapshot
from smart_signal_agent import (
    DIVERSITY_HARDENING_ACTIVATION_TARGET,
    HARDENED_ONLINE_MAX_ABS_STEP,
    HARDENED_REDUNDANCY_THRESHOLD,
    SmartSignalAgent,
    _contrastive_diversity_guard,
)


def _draws(seed: int = 907, n: int = 76):
    rng = np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(np.arange(1, 61), 6, replace=False)) for _ in range(n)], dtype=int)


def test_guard_is_inactive_through_locked_3055():
    primary = [1, 2, 3, 4, 5, 6]
    ranking = list(range(1, 61))
    out = _contrastive_diversity_guard(primary, ranking, primary, 3055)
    assert out['active'] is False
    assert out['applied'] is False
    assert out['final_top6'] == primary
    assert out['result_used'] is False


def test_guard_creates_minimal_contrast_from_3056_without_result_use():
    primary = [1, 2, 3, 4, 5, 6]
    ranking = list(range(1, 61))
    out = _contrastive_diversity_guard(primary, ranking, primary, DIVERSITY_HARDENING_ACTIVATION_TARGET)
    assert out['active'] is True and out['applied'] is False
    assert out['shadow_only'] is True and out['decision_effect'] is False
    assert out['final_top6'] == primary
    assert out['shadow_top6'] == [1, 2, 3, 4, 5, 7]
    assert out['novelty_before'] == 0 and out['shadow_novelty_after'] == 1
    assert out['removed_number'] == 6 and out['added_number'] == 7
    assert out['shadow_candidate_generated'] is True
    assert out['promotion_authority'] is False and out['result_used'] is False


def test_guard_preserves_already_distinct_challenger():
    primary = [1, 2, 3, 4, 5, 7]
    champion = [1, 2, 3, 4, 5, 6]
    out = _contrastive_diversity_guard(primary, list(range(1, 61)), champion, 3056)
    assert out['active'] is True and out['applied'] is False
    assert out['final_top6'] == primary
    assert out['shadow_top6'] == primary
    assert out['shadow_novelty_after'] == 1
    assert out['shadow_candidate_generated'] is False


def test_target_profile_hardens_redundancy_and_online_shock_only_from_3056():
    legacy = SmartSignalAgent(start=40)
    legacy._configure_target_profile(3055)
    assert legacy.architecture_profile == 'LEGACY_COMPATIBLE'
    assert legacy.redundancy_threshold > HARDENED_REDUNDANCY_THRESHOLD
    hardened = SmartSignalAgent(start=40)
    hardened._configure_target_profile(3056)
    assert hardened.architecture_profile == 'DIVERSITY_HARDENED_V1'
    assert hardened.redundancy_threshold == HARDENED_REDUNDANCY_THRESHOLD
    assert hardened.online_max_abs_step == HARDENED_ONLINE_MAX_ABS_STEP


def test_future_prediction_is_contrastive_and_independent_oracle_verifies_it():
    draws = _draws()
    contests = np.arange(2980, 2980 + len(draws))
    target = int(contests[-1]) + 1
    assert target >= 3056
    first_agent = SmartSignalAgent(start=40)
    primary, _ = first_agent.predict_next(draws, contests, target_contest=target)
    second_agent = SmartSignalAgent(start=40)
    guarded, _ = second_agent.predict_next(draws, contests, target_contest=target, champion_top6=primary.top6)
    guard = guarded.challenger_diversity_guard
    assert guard['active'] is True and guard['shadow_only'] is True
    assert guarded.top6 == primary.top6
    assert len(set(guard['shadow_top6']) - set(primary.top6)) >= 1
    assert guard['decision_effect'] is False and guard['promotion_authority'] is False
    audit = validate_prediction_snapshot(guarded.as_dict())
    assert audit['verified'] is True
    assert audit['final_top6'] == guarded.top6
    assert audit['decision_mode'] == 'quality_dynamic_anchor'
