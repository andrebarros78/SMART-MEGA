from __future__ import annotations



import hashlib

import json

import math

from dataclasses import dataclass

from datetime import datetime, timezone

from pathlib import Path

from typing import Any



import numpy as np



import smart_v2_engine as e

from smart_signal_quality import SignalQualityState

from smart_signal_weights import dynamic_weights

from smart_context_regime import ContextRegimeEngine

from smart_signal_marginal_utility import MarginalUtilityState, update_marginal_states

from smart_signal_redundancy_consensus import DEFAULT_CORRELATION_THRESHOLD, consensus_penalties

from smart_signal_interactions import InteractionTracker

from smart_contextual_meta_weights import DEFAULT_META_STRENGTH, contextual_meta_factors

from smart_rank_score_calibration import DEFAULT_CALIBRATION_STRENGTH, RankScoreCalibrator

from smart_multi_challengers import build_multi_challengers

from smart_meta_governor import MetaGovernor

from smart_bounded_online_learning import BoundedOnlineLearningGuard



AGENT_SCHEMA = 'SMART_SIGNAL_AGENT_9'

SIGNAL_NAMES = tuple([f'freq{w}' for w in e.FREQ_WINDOWS] + ['freq_global'] + [f'ewma{s}' for s in e.EWMA_SPANS])





def sha256_bytes(data: bytes) -> str:

    return hashlib.sha256(data).hexdigest()





def sha256_json(obj: Any) -> str:

    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

    return sha256_bytes(raw)





@dataclass

class SignalPrediction:

    target_contest: int

    cutoff_contest: int

    cutoff_timestamp: str | None

    cutoff_timestamp_kind: str

    top6: list[int]

    ranking60: list[int]

    aggregate_scores: dict[str, float]

    weights: dict[str, float]

    weight_components: dict[str, dict]

    quality_metrics: dict[str, dict]

    raw_signals: dict[str, dict]

    state_summary: dict[str, dict]

    context_state: dict[str, Any]

    redundancy_consensus: dict[str, Any]

    interaction_state: dict[str, Any]

    contextual_meta_weights: dict[str, Any]

    rank_score_calibration: dict[str, Any]

    multi_challengers: dict[str, Any]

    meta_governor: dict[str, Any]

    bounded_online_learning: dict[str, Any]



    def as_dict(self) -> dict[str, Any]:

        return {

            'schema': AGENT_SCHEMA,

            'target_contest': self.target_contest,

            'cutoff_contest': self.cutoff_contest,

            'cutoff_timestamp': self.cutoff_timestamp,

            'cutoff_timestamp_kind': self.cutoff_timestamp_kind,

            'causal_cutoff': True,

            'generated_utc': datetime.now(timezone.utc).isoformat(),

            'top6': self.top6,

            'ranking60': self.ranking60,

            'aggregate_scores': self.aggregate_scores,

            'weights': self.weights,

            'weight_components': self.weight_components,

            'quality_metrics': self.quality_metrics,

            'raw_signals': self.raw_signals,

            'river_state': self.state_summary,

            'context_regime': self.context_state,

            'redundancy_consensus': self.redundancy_consensus,

            'signal_interactions': self.interaction_state,

            'contextual_meta_weights': self.contextual_meta_weights,

            'rank_score_calibration': self.rank_score_calibration,

            'multi_challengers': self.multi_challengers,

            'meta_governor': self.meta_governor,

            'bounded_online_learning': self.bounded_online_learning,

            'utility_source': 'SMART champion two-level Hedge before redundancy penalty',

        }





def _apply_governor_decision(base_top6: list[int], governor: dict[str, Any]) -> tuple[list[int], str]:
    base = [int(x) for x in base_top6]
    if governor.get('alternate_authorized', False):
        selected = [int(x) for x in governor['selected_top6']]
        if len(selected) != 6 or len(set(selected)) != 6:
            raise ValueError('meta-governor selected_top6 must contain six unique numbers')
        return selected, f"meta_governor:{governor['selected_policy']}"
    return base, 'quality_dynamic_anchor'


class SmartSignalAgent:

    def __init__(self, start: int = 1000, eta: float = math.log(2), redundancy_threshold: float = DEFAULT_CORRELATION_THRESHOLD, meta_strength: float = DEFAULT_META_STRENGTH, calibration_strength: float = DEFAULT_CALIBRATION_STRENGTH, marginal_strength: float = 0.0, allow_meta_alternate_selection: bool = False):

        self.start = int(start)

        self.eta = float(eta)

        self.redundancy_threshold = float(redundancy_threshold)

        self.meta_strength = float(meta_strength)

        self.calibration_strength = float(calibration_strength)

        self.marginal_strength = float(marginal_strength)
        if not math.isfinite(self.marginal_strength) or not 0.0 <= self.marginal_strength <= 1.0:
            raise ValueError('marginal_strength must be in [0,1]')
        self.allow_meta_alternate_selection = bool(allow_meta_alternate_selection)

        self._reset_states()



    def _reset_states(self) -> None:

        self.states: dict[str, SignalQualityState] = {

            n: SignalQualityState(name=n, family=e.family_of(n)) for n in SIGNAL_NAMES

        }

        self.last_contest: int | None = None

        self.training_rows = 0

        self.context_engine = ContextRegimeEngine()

        self.marginal_states = {n: MarginalUtilityState(name=n) for n in SIGNAL_NAMES}

        self.interaction_tracker = InteractionTracker(SIGNAL_NAMES)

        self.rank_calibrator = RankScoreCalibrator(strength=self.calibration_strength)

        self.expert_learning_guard = BoundedOnlineLearningGuard(eta=self.eta, prior_observations=self.start)

        self.family_learning_guard = BoundedOnlineLearningGuard(eta=self.eta, prior_observations=self.start)

        self.meta_governor = MetaGovernor(allow_alternate_selection=self.allow_meta_alternate_selection)



    @staticmethod

    def _families(names) -> dict[str, str]:

        return {n: e.family_of(n) for n in names}



    @staticmethod

    def _raw_snapshot(sc: dict[str, np.ndarray], cutoff_contest: int, target_contest: int,

                      cutoff_timestamp: str | None, cutoff_timestamp_kind: str) -> dict[str, dict]:

        out = {}

        for name, values in sc.items():

            arr = np.asarray(values, dtype=float)

            payload = {

                'signal_id': name,

                'family': e.family_of(name),

                'cutoff_contest': int(cutoff_contest),

                'target_contest': int(target_contest),

                'cutoff_timestamp': cutoff_timestamp,

                'cutoff_timestamp_kind': cutoff_timestamp_kind,

                'causal': True,

                'values': {str(i + 1): float(arr[i]) for i in range(60)},

            }

            payload['values_sha256'] = sha256_json(payload['values'])

            out[name] = payload

        return out



    @staticmethod

    def _champion_policy_components(sc: dict[str, np.ndarray], elog: dict[str, float], flog: dict[str, float]):

        names = list(sc)

        fams = sorted(set(e.family_of(n) for n in names))

        penalties, _ = e.redundancy_penalty(sc)

        fw = e.regularize(e.softmax(flog), prior_mix=e.PRIOR_MIX, cap=e.FAMILY_CAP)

        base_utility = {}

        family_scores = {}

        for fam in fams:

            fn = [n for n in names if e.family_of(n) == fam]

            ew = e.regularize(e.softmax({n: elog[n] for n in fn}), prior_mix=e.PRIOR_MIX,

                              cap=e.EXPERT_CAP_WITHIN_FAMILY)

            for n in fn:

                base_utility[n] = fw[fam] * ew[n]

            adjusted = {n: ew[n] * penalties[n] for n in fn}

            z = sum(adjusted.values())

            adjusted = {n: v / z for n, v in adjusted.items()}

            family_scores[fam] = sum(adjusted[n] * sc[n] for n in fn)

        return penalties, base_utility, family_scores, fw



    def _predict_from_scores(self, sc: dict[str, np.ndarray], cutoff_contest: int, target_contest: int,

                             cutoff_timestamp: str | None = None, cutoff_timestamp_kind: str = 'unknown',

                             utility_base: dict[str, float] | None = None,

                             penalties: dict[str, float] | None = None,

                             redundancy_audit: dict[str, Any] | None = None,

                             audit_detail: bool = True) -> SignalPrediction:

        if penalties is None:

            penalties, redundancy_audit = consensus_penalties(sc, utility_base, self.redundancy_threshold)

        redundancy_audit = redundancy_audit or {}

        if utility_base is None:

            utility_base = {n: 1.0 / len(sc) for n in sc}

        metrics = {}

        for n in sc:

            m = self.states[n].metrics(penalties[n], freshness=1.0)

            m['recent_performance_utility'] = m['utility']

            m['utility'] = float(utility_base[n])

            m['utility_source'] = 'champion_two_level_hedge_pre_redundancy'

            m['signal_performance_context'] = float(m['context'])

            m['regime_context'] = self.context_engine.factor_for_signal(n)

            m['context'] = float(m['context']) * float(m['regime_context'])

            marginal = self.marginal_states[n].metrics()

            m['marginal_utility'] = marginal

            m['marginal_utility_mean_delta_hits'] = float(marginal['mean_delta_hits'])

            m['marginal_utility_confidence'] = float(marginal['confidence'])

            m['marginal_utility_shrunk'] = float(marginal['shrunk_mean_delta_hits'])

            m['marginal_utility_weight_effect_enabled'] = bool(self.marginal_strength > 0.0)
            marginal_factor = 1.0 + self.marginal_strength * math.tanh(float(marginal['shrunk_mean_delta_hits']))
            m['marginal_utility_factor'] = float(marginal_factor)
            m['context'] = float(m['context']) * float(marginal_factor)

            metrics[n] = m

        families = self._families(sc)

        meta_factors, meta_audit = contextual_meta_factors(

            sc, metrics, families, self.context_engine.metrics(), self.interaction_tracker.metrics(), self.meta_strength

        )

        for n in metrics:

            metrics[n]['context_before_meta'] = float(metrics[n]['context'])

            metrics[n]['contextual_meta_factor'] = float(meta_factors[n])

            metrics[n]['context'] = float(metrics[n]['context']) * float(meta_factors[n])

        weights, components = dynamic_weights(metrics, families)

        for n in components:

            components[n]['contextual_meta_factor'] = float(meta_factors[n])

        agg = np.zeros(60, dtype=float)

        for n in sc:

            agg += weights[n] * np.asarray(sc[n], dtype=float)

        top6, order = e.rank_top6(agg)

        ranking60 = e.NUMBERS[order].tolist()

        aggregate_scores = {str(i + 1): float(agg[i]) for i in range(60)}

        calibrated_probabilities, calibration_audit = self.rank_calibrator.predict(ranking60, aggregate_scores)

        calibration_audit['probabilities_by_number'] = calibrated_probabilities

        multi = build_multi_challengers(sc, weights, metrics, families, redundancy_audit, self.context_engine.metrics(), audit_detail=audit_detail)

        if multi['policies']['quality_dynamic']['top6'] != top6:

            raise RuntimeError('quality_dynamic policy must reproduce primary challenger')

        governor = self.meta_governor.select(multi)
        base_top6 = list(top6)
        top6, decision_source = _apply_governor_decision(base_top6, governor)
        governor['decision_top6_applied'] = list(top6)
        governor['decision_source'] = decision_source

        raw = self._raw_snapshot(sc, cutoff_contest, target_contest, cutoff_timestamp, cutoff_timestamp_kind) if audit_detail else {}

        state = {n: self.states[n].audit_state(penalties[n]) for n in sc} if audit_detail else {}

        return SignalPrediction(

            target_contest=int(target_contest), cutoff_contest=int(cutoff_contest),

            cutoff_timestamp=cutoff_timestamp, cutoff_timestamp_kind=cutoff_timestamp_kind,

            top6=top6, ranking60=ranking60,

            aggregate_scores=aggregate_scores, weights=weights,

            weight_components=components, quality_metrics=metrics, raw_signals=raw, state_summary=state,

            context_state=self.context_engine.metrics(), redundancy_consensus=redundancy_audit,

            interaction_state=self.interaction_tracker.metrics(), contextual_meta_weights=meta_audit,

            rank_score_calibration=calibration_audit, multi_challengers=multi, meta_governor=governor,

            bounded_online_learning={'schema':'SMART_BOUNDED_ONLINE_LEARNING_SNAPSHOT_1',

                                     'expert':self.expert_learning_guard.state(),

                                     'family':self.family_learning_guard.state(),

                                     'update_after_result_only':True},

        )



    def _learn_actual(self, sc: dict[str, np.ndarray], actual) -> dict[str, int]:

        actual_set = set(int(x) for x in actual)

        hits = {}

        for n, score in sc.items():

            top, _ = e.rank_top6(score)

            h = len(set(top) & actual_set)

            self.states[n].update(h)

            hits[n] = h

        self.training_rows += 1

        return hits



    def replay_history(self, draws: np.ndarray, contests: np.ndarray) -> dict[str, Any]:

        self._reset_states()

        if len(draws) != len(contests):

            raise ValueError('draws and contests length mismatch')

        if len(draws) <= self.start:

            raise ValueError('insufficient history for configured start')

        pre = e.precompute_scores(e.onehot(draws))

        names = [n for n in SIGNAL_NAMES if n in pre]

        if set(names) != set(SIGNAL_NAMES):

            raise ValueError(f'missing expected signals: {sorted(set(SIGNAL_NAMES) - set(names))}')

        fams = sorted(set(e.family_of(n) for n in names))

        elog = {n: 0.0 for n in names}

        flog = {f: 0.0 for f in fams}

        # Causal context prewarm: only historical draws before the OOS start are consumed.

        for t in range(self.start):

            self.context_engine.update(draws[t])

        total_challenger_hits = 0

        rows = []

        for t in range(self.start, len(draws)):

            sc = {n: pre[n][t] for n in names}

            champion_penalties, utility_base, family_scores, _ = self._champion_policy_components(sc, elog, flog)

            p03_penalties, p03_audit = consensus_penalties(sc, utility_base, self.redundancy_threshold)

            pred = self._predict_from_scores(sc, int(contests[t - 1]), int(contests[t]),

                                             utility_base=utility_base, penalties=p03_penalties, redundancy_audit=p03_audit, audit_detail=False)

            actual = set(draws[t])

            challenger_hits = len(set(pred.top6) & actual)

            marginal_update = update_marginal_states(self.marginal_states, sc, pred.weights, draws[t])

            interaction_update = self.interaction_tracker.update(sc, pred.weights, draws[t])

            calibration_update = self.rank_calibrator.update(

                pred.ranking60, draws[t], pred.rank_score_calibration['probabilities_by_number']

            )

            multi_hits = {pid: len(set(row['top6']) & actual) for pid, row in pred.multi_challengers['policies'].items()}

            governor_update = self.meta_governor.update(multi_hits, pred.meta_governor['selected_policy'])

            expert_hits = self._learn_actual(sc, draws[t])

            elog, expert_learning_update = self.expert_learning_guard.update(elog, expert_hits)

            family_hits = {}

            for fam in fams:

                top, _ = e.rank_top6(family_scores[fam])

                h = len(set(top) & actual)

                family_hits[fam] = h

            flog, family_learning_update = self.family_learning_guard.update(flog, family_hits)

            self.context_engine.update(draws[t])

            total_challenger_hits += challenger_hits

            rows.append({'contest': int(contests[t]), 'cutoff_contest': int(contests[t - 1]),

                         'challenger_top6': pred.top6, 'challenger_hits': challenger_hits,

                         'expert_hits': expert_hits, 'family_hits': family_hits,

                         'weights_before_result': pred.weights,

                         'meta_strength_before_result': self.meta_strength,

                         'meta_factor_min_before_result': float(pred.contextual_meta_weights['factor_min']),

                         'meta_factor_max_before_result': float(pred.contextual_meta_weights['factor_max']),

                         'meta_family_divergence_before_result': float(pred.contextual_meta_weights['family_divergence']),

                         'meta_regime_intensity_before_result': float(pred.contextual_meta_weights['regime_intensity']),

                         'pair_interactions_after_result': {k:int(v['interaction_delta_hits']) for k,v in interaction_update['pair_interactions'].items()},

                         'ranking60_before_result': pred.ranking60,

                         'rank_calibration_before_result': pred.rank_score_calibration,

                         'rank_calibration_brier_after_result': calibration_update,

                         'multi_challenger_top6_before_result': {pid:list(row['top6']) for pid,row in pred.multi_challengers['policies'].items()},

                         'multi_challenger_hits_after_result': multi_hits,

                         'meta_governor_before_result': pred.meta_governor,

                         'meta_governor_update_after_result': governor_update,

                         'bounded_expert_learning_after_result': expert_learning_update,

                         'bounded_family_learning_after_result': family_learning_update,

                         'marginal_delta_hits_after_result': {

                             n: (None if not item['available'] else int(item['delta_hits']))

                             for n, item in marginal_update['per_signal'].items()

                         }})

        self.last_contest = int(contests[-1])

        self._elog = elog

        self._flog = flog

        self._pre = pre

        return {'rows': rows, 'total_hits': int(total_challenger_hits), 'meta_strength': self.meta_strength,

                'mean_hits': float(total_challenger_hits / len(rows)),

                'uniform_expected_hits': float(len(rows) * e.UNIFORM_EXPECTED_HITS),

                'excess_hits': float(total_challenger_hits - len(rows) * e.UNIFORM_EXPECTED_HITS)}



    def predict_next(self, draws: np.ndarray, contests: np.ndarray, target_contest: int | None = None,

                     cutoff_timestamp: str | None = None,

                     cutoff_timestamp_kind: str = 'unknown') -> tuple[SignalPrediction, dict[str, Any]]:

        backtest = self.replay_history(draws, contests)

        target = int(target_contest if target_contest is not None else int(contests[-1]) + 1)

        if target <= int(contests[-1]):

            raise ValueError('target must be strictly after cutoff contest')

        sc = {n: self._pre[n][len(draws)] for n in SIGNAL_NAMES}

        champion_penalties, utility_base, _, _ = self._champion_policy_components(sc, self._elog, self._flog)

        p03_penalties, p03_audit = consensus_penalties(sc, utility_base, self.redundancy_threshold)

        prediction = self._predict_from_scores(sc, int(contests[-1]), target, cutoff_timestamp,

                                               cutoff_timestamp_kind, utility_base, p03_penalties, p03_audit)

        return prediction, backtest



    def state_document(self, data_sha256: str | None = None) -> dict[str, Any]:

        return {'schema': 'SMART_SIGNAL_STATE_9', 'agent_schema': AGENT_SCHEMA, 'last_contest': self.last_contest,

                'training_rows': self.training_rows, 'start_index': self.start, 'eta': self.eta, 'meta_strength': self.meta_strength, 'calibration_strength': self.calibration_strength,

                'data_sha256': data_sha256, 'river_version_required': '0.26.1',

                'redundancy_consensus_threshold': self.redundancy_threshold,

                'rebuild_policy': 'deterministic causal replay from canonical Mega-Sena history',

                'utility_alignment': 'inherits SMART champion two-level Hedge before applying quality/confidence/context/redundancy',

                'signals': {n: self.states[n].audit_state() for n in SIGNAL_NAMES},

                'marginal_utility': {n: self.marginal_states[n].metrics() for n in SIGNAL_NAMES},

                'signal_interactions': self.interaction_tracker.metrics(),

                'contextual_meta_weights': {'strength': self.meta_strength, 'weight_effect_enabled': bool(self.meta_strength > 0.0)},
                'marginal_utility_weighting': {'strength': self.marginal_strength, 'weight_effect_enabled': bool(self.marginal_strength > 0.0)},

                'rank_score_calibration': self.rank_calibrator.state(),

                'context_regime': self.context_engine.metrics(),

                'multi_challengers': {'schema':'SMART_MULTI_CHALLENGERS_1','policy_count':5,'shadow_only':True,'selection_deferred_to_p08':False},

                'meta_governor': self.meta_governor.state(),

                'bounded_online_learning': {'schema':'SMART_BOUNDED_ONLINE_LEARNING_SNAPSHOT_1',

                                            'expert':self.expert_learning_guard.state(),

                                            'family':self.family_learning_guard.state(),

                                            'update_after_result_only':True}}





def write_state(path: Path, state: dict[str, Any]) -> str:

    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    return hashlib.sha256(path.read_bytes()).hexdigest()
