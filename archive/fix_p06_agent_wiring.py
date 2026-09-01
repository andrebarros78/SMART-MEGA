from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\smart_signal_agent.py')
s=p.read_text(encoding='utf-8-sig')
needle="from smart_contextual_meta_weights import DEFAULT_META_STRENGTH, contextual_meta_factors\n"
assert needle in s
s=s.replace(needle, needle+"from smart_rank_score_calibration import DEFAULT_CALIBRATION_STRENGTH, RankScoreCalibrator\n")
old="def __init__(self, start: int = 1000, eta: float = math.log(2), redundancy_threshold: float = DEFAULT_CORRELATION_THRESHOLD, meta_strength: float = DEFAULT_META_STRENGTH):"
new="def __init__(self, start: int = 1000, eta: float = math.log(2), redundancy_threshold: float = DEFAULT_CORRELATION_THRESHOLD, meta_strength: float = DEFAULT_META_STRENGTH, calibration_strength: float = DEFAULT_CALIBRATION_STRENGTH):"
assert old in s
s=s.replace(old,new)
s=s.replace("        self.meta_strength = float(meta_strength)\n        self._reset_states()", "        self.meta_strength = float(meta_strength)\n        self.calibration_strength = float(calibration_strength)\n        self._reset_states()")
s=s.replace("        self.rank_calibrator = RankScoreCalibrator()", "        self.rank_calibrator = RankScoreCalibrator(strength=self.calibration_strength)")
s=s.replace("'training_rows': self.training_rows, 'start_index': self.start, 'eta': self.eta, 'meta_strength': self.meta_strength,", "'training_rows': self.training_rows, 'start_index': self.start, 'eta': self.eta, 'meta_strength': self.meta_strength, 'calibration_strength': self.calibration_strength,")
s=s.replace("                'contextual_meta_weights': {'strength': self.meta_strength, 'weight_effect_enabled': bool(self.meta_strength > 0.0)},\n                'context_regime':", "                'contextual_meta_weights': {'strength': self.meta_strength, 'weight_effect_enabled': bool(self.meta_strength > 0.0)},\n                'rank_score_calibration': self.rank_calibrator.state(),\n                'context_regime':")
p.write_text(s,encoding='utf-8')
print('fixed')
