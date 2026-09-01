from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'smart_signal_agent.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('from smart_meta_governor import MetaGovernor\n','from smart_meta_governor import MetaGovernor\nfrom smart_bounded_online_learning import BoundedOnlineLearningGuard\n')
s=s.replace("AGENT_SCHEMA = 'SMART_SIGNAL_AGENT_8'","AGENT_SCHEMA = 'SMART_SIGNAL_AGENT_9'")
s=s.replace('    meta_governor: dict[str, Any]\n','    meta_governor: dict[str, Any]\n    bounded_online_learning: dict[str, Any]\n')
s=s.replace("            'meta_governor': self.meta_governor,\n            'utility_source'", "            'meta_governor': self.meta_governor,\n            'bounded_online_learning': self.bounded_online_learning,\n            'utility_source'")
s=s.replace('        self.rank_calibrator = RankScoreCalibrator(strength=self.calibration_strength)\n', '        self.rank_calibrator = RankScoreCalibrator(strength=self.calibration_strength)\n        self.expert_learning_guard = BoundedOnlineLearningGuard(eta=self.eta)\n        self.family_learning_guard = BoundedOnlineLearningGuard(eta=self.eta)\n')
s=s.replace('            rank_score_calibration=calibration_audit, multi_challengers=multi, meta_governor=governor,\n', "            rank_score_calibration=calibration_audit, multi_challengers=multi, meta_governor=governor,\n            bounded_online_learning={'schema':'SMART_BOUNDED_ONLINE_LEARNING_SNAPSHOT_1',\n                                     'expert':self.expert_learning_guard.state(),\n                                     'family':self.family_learning_guard.state(),\n                                     'update_after_result_only':True},\n")
old="""            expert_hits = self._learn_actual(sc, draws[t])
            for n in names:
                elog[n] += self.eta * (expert_hits[n] - e.UNIFORM_EXPECTED_HITS)
            family_hits = {}
            for fam in fams:
                top, _ = e.rank_top6(family_scores[fam])
                h = len(set(top) & actual)
                family_hits[fam] = h
                flog[fam] += self.eta * (h - e.UNIFORM_EXPECTED_HITS)
"""
new="""            expert_hits = self._learn_actual(sc, draws[t])
            elog, expert_learning_update = self.expert_learning_guard.update(elog, expert_hits)
            family_hits = {}
            for fam in fams:
                top, _ = e.rank_top6(family_scores[fam])
                h = len(set(top) & actual)
                family_hits[fam] = h
            flog, family_learning_update = self.family_learning_guard.update(flog, family_hits)
"""
if old not in s: raise SystemExit('learning update marker not found')
s=s.replace(old,new,1)
s=s.replace("                         'meta_governor_update_after_result': governor_update,\n", "                         'meta_governor_update_after_result': governor_update,\n                         'bounded_expert_learning_after_result': expert_learning_update,\n                         'bounded_family_learning_after_result': family_learning_update,\n")
s=s.replace("return {'schema': 'SMART_SIGNAL_STATE_8'", "return {'schema': 'SMART_SIGNAL_STATE_9'")
s=s.replace("                'meta_governor': self.meta_governor.state()}\n", "                'meta_governor': self.meta_governor.state(),\n                'bounded_online_learning': {'schema':'SMART_BOUNDED_ONLINE_LEARNING_SNAPSHOT_1',\n                                            'expert':self.expert_learning_guard.state(),\n                                            'family':self.family_learning_guard.state(),\n                                            'update_after_result_only':True}}\n")
p.write_text(s,encoding='utf-8')
print('patched agent P10')
