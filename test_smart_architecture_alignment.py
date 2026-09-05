from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CORE = {
    'smart_v2_engine.py',
    'smart_v2_production.py',
    'freeze_next_research.py',
    'smart_signal_quality.py',
    'smart_signal_weights.py',
    'smart_context_regime.py',
    'smart_signal_agent.py',
    'smart_signal_attribution.py',
    'smart_signal_redundancy_consensus.py',
    'smart_signal_interactions.py',
    'smart_contextual_meta_weights.py',
    'smart_rank_score_calibration.py',
    'smart_multi_challengers.py',
    'smart_meta_governor.py',
    'smart_continuous_red_team.py',
    'smart_signal_expansion_governance.py',
    'smart_sequential_prospective_proof.py',
    'smart_promotion_gate.py',
    'smart_independent_audit.py',
    'smart_signal_marginal_utility.py',
    'smart_champion_challenger.py',
    'adjudicate_signal_challenger.py',
}


def _imports(filename: str) -> set[str]:
    tree = ast.parse((ROOT / filename).read_text(encoding='utf-8-sig'), filename=filename)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split('.')[0])
    return out


def test_all_core_modules_exist_and_parse():
    for filename in CORE:
        path = ROOT / filename
        assert path.is_file(), filename
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=filename)


def test_architecture_dependencies_are_layered_and_non_circular():
    deps = {name: _imports(name) for name in CORE}
    # Champion must remain independent of Challenger/Signal Intelligence.
    assert not ({'smart_signal_agent', 'smart_signal_quality', 'smart_signal_weights', 'smart_context_regime',
                 'smart_champion_challenger', 'adjudicate_signal_challenger'} & deps['smart_v2_engine.py'])
    assert not ({'smart_signal_agent', 'smart_signal_quality', 'smart_signal_weights', 'smart_context_regime',
                 'smart_champion_challenger', 'adjudicate_signal_challenger'} & deps['smart_v2_production.py'])
    # Leaf services cannot depend upward on orchestration.
    assert 'smart_signal_agent' not in deps['smart_signal_quality.py']
    assert 'smart_signal_agent' not in deps['smart_signal_weights.py']
    assert 'smart_signal_agent' not in deps['smart_context_regime.py']
    assert 'smart_champion_challenger' not in deps['smart_signal_agent.py']
    assert deps['smart_signal_attribution.py'] & {'smart_champion_challenger', 'smart_signal_agent', 'adjudicate_signal_challenger'} == set()
    assert 'smart_v2_engine' in deps['smart_signal_attribution.py']
    assert deps['smart_signal_interactions.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()
    assert deps['smart_contextual_meta_weights.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()
    # Red Team may consume the stack for testing, but production signal layers must not depend on Red Team.
    assert 'smart_continuous_red_team' not in deps['smart_signal_agent.py']
    assert 'smart_continuous_red_team' not in deps['smart_v2_engine.py']
    assert 'smart_signal_expansion_governance' not in deps['smart_signal_agent.py']
    assert 'smart_signal_expansion_governance' not in deps['smart_v2_engine.py']
    assert deps['smart_independent_audit.py'] & {'smart_champion_challenger','smart_promotion_gate','adjudicate_signal_challenger'} == set()
    assert deps['smart_promotion_gate.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()
    assert deps['smart_multi_challengers.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()
    assert deps['smart_signal_redundancy_consensus.py'] & {'smart_champion_challenger', 'smart_signal_agent', 'adjudicate_signal_challenger'} == set()
    assert 'smart_v2_engine' not in deps['smart_signal_redundancy_consensus.py']
    assert deps['smart_signal_marginal_utility.py'] & {'smart_champion_challenger', 'smart_signal_agent', 'adjudicate_signal_challenger'} == set()
    assert 'smart_v2_engine' in deps['smart_signal_marginal_utility.py']
    # Agent must compose all required signal-intelligence layers.
    assert {'smart_v2_engine', 'smart_signal_quality', 'smart_signal_weights', 'smart_context_regime', 'smart_signal_marginal_utility', 'smart_signal_redundancy_consensus', 'smart_signal_interactions', 'smart_contextual_meta_weights', 'smart_rank_score_calibration', 'smart_multi_challengers'} <= deps['smart_signal_agent.py']
    # Champion/Challenger orchestration may depend on Champion research policy + Agent, never production governor.
    assert {'smart_v2_engine', 'freeze_next_research', 'smart_signal_agent'} <= deps['smart_champion_challenger.py']
    assert 'smart_v2_production' not in deps['smart_champion_challenger.py']
    # Adjudication consumes frozen snapshots through governance, not live agent internals.
    assert {'smart_v2_engine', 'smart_champion_challenger', 'smart_signal_attribution', 'smart_signal_marginal_utility', 'smart_signal_interactions', 'smart_multi_challengers'} <= deps['adjudicate_signal_challenger.py']
    assert 'smart_signal_agent' not in deps['adjudicate_signal_challenger.py']

    local = {Path(x).stem for x in CORE}
    graph = {Path(k).stem: sorted(v & local) for k, v in deps.items()}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str):
        if node in visited:
            return
        assert node not in visiting, f'circular dependency at {node}'
        visiting.add(node)
        for nxt in graph.get(node, []):
            visit(nxt)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def test_freeze_hashes_every_behavioral_challenger_component():
    text = (ROOT / 'smart_champion_challenger.py').read_text(encoding='utf-8-sig')
    required = {
        "'engine': sha256(Path('smart_v2_engine.py'))",
        "'signal_agent': sha256(Path('smart_signal_agent.py'))",
        "'signal_quality': sha256(Path('smart_signal_quality.py'))",
        "'signal_weights': sha256(Path('smart_signal_weights.py'))",
        "'context_regime': sha256(Path('smart_context_regime.py'))",
        "'redundancy_consensus': sha256(Path('smart_signal_redundancy_consensus.py'))",
        "'marginal_utility': sha256(Path('smart_signal_marginal_utility.py'))",
        "'contextual_meta_weights': sha256(Path('smart_contextual_meta_weights.py'))",
        "'rank_score_calibration': sha256(Path('smart_rank_score_calibration.py'))",
        "'multi_challengers': sha256(Path('smart_multi_challengers.py'))",
        "'meta_governor': sha256(Path('smart_meta_governor.py'))",
        "'signal_interactions': sha256(Path('smart_signal_interactions.py'))",
        "'promotion_gate': sha256(Path('smart_promotion_gate.py'))",
        "'independent_audit': sha256(Path('smart_independent_audit.py'))",
    }
    for marker in required:
        assert marker in text
    assert "'context_regime_sha256': component_hashes['context_regime']" in text
    assert "'marginal_utility_sha256': component_hashes['marginal_utility']" in text
    assert "'contextual_meta_weights_sha256': component_hashes['contextual_meta_weights']" in text
    assert "'rank_score_calibration_sha256': component_hashes['rank_score_calibration']" in text
    assert "'multi_challengers_sha256': component_hashes['multi_challengers']" in text
    assert "'multi_challengers': freeze_obj['challenger']['multi_challengers']" in text
    assert "'contextual_meta_weights': freeze_obj['challenger']['contextual_meta_weights']" in text
    assert "'signal_interactions_sha256': component_hashes['signal_interactions']" in text
    assert "'signal_interactions': freeze_obj['challenger']['signal_interactions']" in text
    assert "'independent_audit_sha256': component_hashes['independent_audit']" in text
    assert "'independent_audit_policy': independent_audit_snapshot" in text


def test_profile_drift_is_causally_observed_and_penalizes_signal_context():
    quality = (ROOT / 'smart_signal_quality.py').read_text(encoding='utf-8-sig')
    agent = (ROOT / 'smart_signal_agent.py').read_text(encoding='utf-8-sig')
    assert "'profile_drift_penalty_enabled': True" in quality
    assert 'profile_drift_active = self.profile_drift_cooldown > 0' in quality
    assert 'self._observe_signal_profiles(sc)' in agent
    assert "m['regime_context'] = self.context_engine.factor_for_signal(n)" in agent
    assert "m['context'] = float(m['context']) * float(m['regime_context'])" in agent


def test_governance_rejects_out_of_order_ledger_before_sorting():
    text = (ROOT / 'smart_v2_production.py').read_text(encoding='utf-8-sig')
    assert "if contests != sorted(contests):" in text
    assert 'valid.sort()' not in text
    assert "legacy_production_authority_disabled'" in text
    assert "P15 evidence-only promotion is required" in text
