from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\smart_signal_agent.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace("from smart_rank_score_calibration import DEFAULT_CALIBRATION_STRENGTH, RankScoreCalibrator\n", "from smart_rank_score_calibration import DEFAULT_CALIBRATION_STRENGTH, RankScoreCalibrator\nfrom smart_multi_challengers import build_multi_challengers\n")
s=s.replace("AGENT_SCHEMA = 'SMART_SIGNAL_AGENT_6'", "AGENT_SCHEMA = 'SMART_SIGNAL_AGENT_7'")
s=s.replace("    rank_score_calibration: dict[str, Any]\n", "    rank_score_calibration: dict[str, Any]\n    multi_challengers: dict[str, Any]\n")
s=s.replace("            'rank_score_calibration': self.rank_score_calibration,\n", "            'rank_score_calibration': self.rank_score_calibration,\n            'multi_challengers': self.multi_challengers,\n")
needle="        calibrated_probabilities, calibration_audit = self.rank_calibrator.predict(ranking60, aggregate_scores)\n        calibration_audit['probabilities_by_number'] = calibrated_probabilities\n"
rep=needle+"        multi = build_multi_challengers(sc, weights, metrics, families, redundancy_audit, self.context_engine.metrics())\n        if multi['policies']['quality_dynamic']['top6'] != top6:\n            raise RuntimeError('quality_dynamic policy must reproduce primary challenger')\n"
if needle not in s: raise SystemExit('prediction needle missing')
s=s.replace(needle,rep)
s=s.replace("            rank_score_calibration=calibration_audit,\n", "            rank_score_calibration=calibration_audit, multi_challengers=multi,\n")
needle2="            calibration_update = self.rank_calibrator.update(\n                pred.ranking60, draws[t], pred.rank_score_calibration['probabilities_by_number']\n            )\n"
rep2=needle2+"            multi_hits = {pid: len(set(row['top6']) & actual) for pid, row in pred.multi_challengers['policies'].items()}\n"
if needle2 not in s: raise SystemExit('replay needle missing')
s=s.replace(needle2,rep2)
s=s.replace("                         'rank_calibration_brier_after_result': calibration_update,\n", "                         'rank_calibration_brier_after_result': calibration_update,\n                         'multi_challenger_top6_before_result': {pid:list(row['top6']) for pid,row in pred.multi_challengers['policies'].items()},\n                         'multi_challenger_hits_after_result': multi_hits,\n")
s=s.replace("return {'schema': 'SMART_SIGNAL_STATE_6'", "return {'schema': 'SMART_SIGNAL_STATE_7'")
s=s.replace("                'context_regime': self.context_engine.metrics()}", "                'context_regime': self.context_engine.metrics(),\n                'multi_challengers': {'schema':'SMART_MULTI_CHALLENGERS_1','policy_count':5,'shadow_only':True,'selection_deferred_to_p08':True}}")
p.write_text(s,encoding='utf-8')
print('patched')