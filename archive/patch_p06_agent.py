from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\smart_signal_agent.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace("from smart_contextual_meta_weights import contextual_meta_factors\n", "from smart_contextual_meta_weights import contextual_meta_factors\nfrom smart_rank_score_calibration import RankScoreCalibrator\n")
s=s.replace("AGENT_SCHEMA = 'SMART_SIGNAL_AGENT_5'", "AGENT_SCHEMA = 'SMART_SIGNAL_AGENT_6'")
s=s.replace("    contextual_meta_weights: dict[str, Any]\n", "    contextual_meta_weights: dict[str, Any]\n    rank_score_calibration: dict[str, Any]\n")
s=s.replace("            'contextual_meta_weights': self.contextual_meta_weights,\n", "            'contextual_meta_weights': self.contextual_meta_weights,\n            'rank_score_calibration': self.rank_score_calibration,\n")
s=s.replace("        self.interaction_tracker = InteractionTracker(SIGNAL_NAMES)\n", "        self.interaction_tracker = InteractionTracker(SIGNAL_NAMES)\n        self.rank_calibrator = RankScoreCalibrator()\n")
old="""        top6, order = e.rank_top6(agg)\n        raw = self._raw_snapshot(sc, cutoff_contest, target_contest, cutoff_timestamp, cutoff_timestamp_kind) if audit_detail else {}\n"""
new="""        top6, order = e.rank_top6(agg)\n        ranking60 = e.NUMBERS[order].tolist()\n        aggregate_scores = {str(i + 1): float(agg[i]) for i in range(60)}\n        calibrated_probabilities, calibration_audit = self.rank_calibrator.predict(ranking60, aggregate_scores)\n        calibration_audit['probabilities_by_number'] = calibrated_probabilities\n        raw = self._raw_snapshot(sc, cutoff_contest, target_contest, cutoff_timestamp, cutoff_timestamp_kind) if audit_detail else {}\n"""
assert old in s
s=s.replace(old,new)
old="""            top6=top6, ranking60=e.NUMBERS[order].tolist(),\n            aggregate_scores={str(i + 1): float(agg[i]) for i in range(60)}, weights=weights,\n"""
new="""            top6=top6, ranking60=ranking60,\n            aggregate_scores=aggregate_scores, weights=weights,\n"""
assert old in s
s=s.replace(old,new)
s=s.replace("            interaction_state=self.interaction_tracker.metrics(), contextual_meta_weights=meta_audit,\n", "            interaction_state=self.interaction_tracker.metrics(), contextual_meta_weights=meta_audit,\n            rank_score_calibration=calibration_audit,\n")
old="""            interaction_update = self.interaction_tracker.update(sc, pred.weights, draws[t])\n            expert_hits = self._learn_actual(sc, draws[t])\n"""
new="""            interaction_update = self.interaction_tracker.update(sc, pred.weights, draws[t])\n            calibration_update = self.rank_calibrator.update(\n                pred.ranking60, draws[t], pred.rank_score_calibration['probabilities_by_number']\n            )\n            expert_hits = self._learn_actual(sc, draws[t])\n"""
assert old in s
s=s.replace(old,new)
old="""                         'pair_interactions_after_result': {k:int(v['interaction_delta_hits']) for k,v in interaction_update['pair_interactions'].items()},\n                         'marginal_delta_hits_after_result': {\n"""
new="""                         'pair_interactions_after_result': {k:int(v['interaction_delta_hits']) for k,v in interaction_update['pair_interactions'].items()},\n                         'rank_calibration_before_result': pred.rank_score_calibration,\n                         'rank_calibration_brier_after_result': calibration_update,\n                         'marginal_delta_hits_after_result': {\n"""
assert old in s
s=s.replace(old,new)
s=s.replace("return {'schema': 'SMART_SIGNAL_STATE_5'", "return {'schema': 'SMART_SIGNAL_STATE_6'")
s=s.replace("                'contextual_meta_strength': self.meta_strength,\n", "                'contextual_meta_strength': self.meta_strength,\n                'rank_score_calibration': self.rank_calibrator.state(),\n")
p.write_text(s,encoding='utf-8')
print('patched',p)
