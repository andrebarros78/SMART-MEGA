from __future__ import annotations

import math
import numpy as np

from smart_bounded_online_learning import (
    BoundedOnlineLearningGuard,
    DEFAULT_MAX_ABS_STEP,
    DEFAULT_WARMUP_MAX_ABS_STEP,
    DEFAULT_MAX_ABS_CENTERED_LOGIT,
)
from smart_signal_agent import SmartSignalAgent


def _draws(seed: int = 1010, n: int = 45) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(np.arange(1, 61), 6, replace=False)) for _ in range(n)], dtype=int)


def test_production_defaults_are_materially_bounded():
    assert DEFAULT_MAX_ABS_STEP == 2.5
    assert DEFAULT_WARMUP_MAX_ABS_STEP == 1.0
    assert DEFAULT_MAX_ABS_CENTERED_LOGIT == 100.0
    guard = BoundedOnlineLearningGuard(eta=math.log(2))
    assert guard.prior_observations == 0
    assert guard.evidence_scale() < 1.0
    _, audit = guard.update({'a': 0.0, 'b': 0.0}, {'a': 6, 'b': 0})
    assert audit['few_observation_protection'] is True
    assert audit['effective_step_cap'] == 1.0
    assert max(abs(v) for v in audit['applied_delta'].values()) <= 1.0 + 1e-15
    assert guard.clipped_update_count >= 1


def test_agent_uses_historical_maturity_but_keeps_fail_safe_step_cap():
    agent = SmartSignalAgent(start=20)
    assert agent.expert_learning_guard.prior_observations == 20
    assert agent.family_learning_guard.prior_observations == 20
    draws = _draws(n=28)
    contests = np.arange(1, len(draws) + 1)
    _, back = agent.predict_next(draws, contests, target_contest=29)
    first = back['rows'][0]
    assert first['bounded_expert_learning_after_result']['few_observation_protection'] is False
    assert first['bounded_family_learning_after_result']['few_observation_protection'] is False
    assert first['bounded_expert_learning_after_result']['effective_step_cap'] == 2.5
    assert agent.expert_learning_guard.warmup_update_count == 0
    assert agent.family_learning_guard.warmup_update_count == 0


def test_centered_spread_cap_is_active_and_recovery_remains_possible():
    guard = BoundedOnlineLearningGuard(eta=1.0)
    weights = {'a': 0.0, 'b': 0.0}
    for _ in range(40):
        weights, _ = guard.update(weights, {'a': 6, 'b': 0})
    assert max(abs(v) for v in weights.values()) <= DEFAULT_MAX_ABS_CENTERED_LOGIT + 1e-12
    low_b = weights['b']
    for _ in range(40):
        weights, _ = guard.update(weights, {'a': 0, 'b': 6})
    assert weights['b'] > low_b
    assert weights['b'] >= weights['a'] - 1e-12


def test_projection_preserves_zero_sum_and_cap_for_three_arm_asymmetry():
    guard = BoundedOnlineLearningGuard(
        eta=1.0,
        max_abs_step=1.0,
        warmup_max_abs_step=1.0,
        warmup_full_after=1,
        min_warmup_scale=1.0,
        max_abs_centered_logit=1.0,
    )
    out, audit = guard.update({'a': 10.0, 'b': 10.0, 'c': -20.0}, {'a': 1, 'b': 1, 'c': 1})
    assert audit['bounded_centering_projection'] is True
    assert audit['spread_clipped_ids']
    assert abs(sum(out.values())) <= 1e-10
    assert max(abs(v) for v in out.values()) <= 1.0 + 1e-12
    assert out['c'] >= -1.0 - 1e-12


def test_private_guard_inputs_and_remaining_configuration_guards():
    import smart_bounded_online_learning as bol
    import pytest
    with pytest.raises(ValueError, match='rewards cannot be empty'):
        bol._validate_hits({})
    with pytest.raises(ValueError, match='centered logits cannot be empty'):
        bol._project_centered_box({}, 1.0)
    with pytest.raises(ValueError, match='cap must be finite and positive'):
        bol._project_centered_box({'a': 0.0}, 0.0)
    with pytest.raises(ValueError, match='centered logits must be finite'):
        bol._project_centered_box({'a': float('nan')}, 1.0)
    with pytest.raises(ValueError, match='baseline_hits'):
        BoundedOnlineLearningGuard(eta=1.0, baseline_hits=7.0)
    with pytest.raises(ValueError, match='warmup_max_abs_step'):
        BoundedOnlineLearningGuard(eta=1.0, max_abs_step=1.0, warmup_max_abs_step=2.0)
    with pytest.raises(ValueError, match='prior_observations'):
        BoundedOnlineLearningGuard(eta=1.0, prior_observations=-1)


def test_projection_residual_correction_handles_both_residual_signs():
    import smart_bounded_online_learning as bol
    for values in (
        {'a': 10.0, 'b': 10.0, 'c': -20.0},
        {'a': -10.0, 'b': -10.0, 'c': 20.0},
    ):
        out, changed = bol._project_centered_box(values, 1.0)
        assert changed
        assert abs(sum(out.values())) <= 1e-10
        assert max(abs(v) for v in out.values()) <= 1.0 + 1e-12


