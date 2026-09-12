from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\smart_rank_score_calibration.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace("DEFAULT_CALIBRATION_STRENGTH = 1.0", "DEFAULT_CALIBRATION_STRENGTH = 0.0\nCALIBRATION_POLICY_ID = 'P06_NEUTRALIZED_AFTER_FINAL_HOLDOUT_20260830'")
old="""    def posterior_by_rank(self) -> np.ndarray:\n        alpha = self.hits_by_rank + self.prior_strength * UNIFORM_PROB\n        mass = self.trials_by_rank + self.prior_strength\n        raw = alpha / mass\n        iso = _pava_nonincreasing(raw, mass)\n        calibrated = UNIFORM_PROB + self.strength * (iso - UNIFORM_PROB)\n        return np.clip(calibrated, 0.0, 1.0)\n\n    def raw_posterior_by_rank(self) -> np.ndarray:\n"""
new="""    def isotonic_posterior_by_rank(self) -> np.ndarray:\n        raw = self.raw_posterior_by_rank()\n        mass = self.trials_by_rank + self.prior_strength\n        return _pava_nonincreasing(raw, mass)\n\n    def posterior_by_rank(self) -> np.ndarray:\n        iso = self.isotonic_posterior_by_rank()\n        calibrated = UNIFORM_PROB + self.strength * (iso - UNIFORM_PROB)\n        return np.clip(calibrated, 0.0, 1.0)\n\n    def raw_posterior_by_rank(self) -> np.ndarray:\n"""
assert old in s
s=s.replace(old,new)
s=s.replace("        calibrated = self.posterior_by_rank()\n", "        isotonic = self.isotonic_posterior_by_rank()\n        calibrated = self.posterior_by_rank()\n",1)
s=s.replace("            'raw_posterior_by_rank': [float(x) for x in raw],\n            'calibrated_probability_by_rank':", "            'raw_posterior_by_rank': [float(x) for x in raw],\n            'isotonic_probability_by_rank': [float(x) for x in isotonic],\n            'calibrated_probability_by_rank':",1)
s=s.replace("            'neutralized': bool(self.strength <= EPS or spread <= EPS),\n", "            'neutralized': bool(self.strength <= EPS or spread <= EPS),\n            'calibration_mode': 'NEUTRALIZED' if self.strength <= EPS else 'SHRUNK_ISOTONIC',\n            'policy_id': CALIBRATION_POLICY_ID,\n",1)
# state() second occurrence
needle="        raw = self.raw_posterior_by_rank(); calibrated = self.posterior_by_rank()\n"
assert needle in s
s=s.replace(needle,"        raw = self.raw_posterior_by_rank(); isotonic = self.isotonic_posterior_by_rank(); calibrated = self.posterior_by_rank()\n")
# replace within state after schema fields
idx=s.index("    def state(self)")
sub=s[idx:]
sub=sub.replace("            'raw_posterior_by_rank': [float(x) for x in raw],\n            'calibrated_probability_by_rank':", "            'raw_posterior_by_rank': [float(x) for x in raw],\n            'isotonic_probability_by_rank': [float(x) for x in isotonic],\n            'calibrated_probability_by_rank':",1)
sub=sub.replace("            'strength': float(self.strength),\n", "            'strength': float(self.strength),\n            'calibration_mode': 'NEUTRALIZED' if self.strength <= EPS else 'SHRUNK_ISOTONIC',\n            'policy_id': CALIBRATION_POLICY_ID,\n",1)
s=s[:idx]+sub
p.write_text(s,encoding='utf-8')
print('neutralized')
