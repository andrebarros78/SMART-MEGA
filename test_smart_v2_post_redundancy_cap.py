"""Research-only corrected effective weight cap; productive engine remains pinned."""
import numpy as np
import smart_v2_engine as engine
from research.effective_cap_variant import walk_forward_capped


def test_research_variant_caps_effective_family_weight_without_modifying_baseline(monkeypatch):
    names = ('freq25', 'freq50', 'ewma10', 'ewma25')
    pre = {name: np.zeros((1, 60), dtype=float) for name in names}

    def controlled_penalty(scores):
        penalties = {name: (1.0 if name == 'freq25' else 0.15) for name in scores}
        return penalties, np.eye(len(scores), dtype=float)

    monkeypatch.setattr(engine, 'redundancy_penalty', controlled_penalty)
    draws = np.array([[1, 2, 3, 4, 5, 6]])
    contests = np.array([1])
    original = engine.walk_forward(draws, contests, start=0, pre=pre)
    original_share = original.final_weights['freq25'] / original.family_weights['freq']
    assert original_share > engine.EXPERT_CAP_WITHIN_FAMILY
    experimental = walk_forward_capped(draws, contests, start=0, pre=pre)
    freq_weight = experimental.family_weights['freq']
    assert freq_weight > 0
    assert max(experimental.final_weights[name] / freq_weight
               for name in ('freq25', 'freq50')) <= engine.EXPERT_CAP_WITHIN_FAMILY + 1e-12
    assert abs(sum(experimental.final_weights.values()) - 1.0) < 1e-12
