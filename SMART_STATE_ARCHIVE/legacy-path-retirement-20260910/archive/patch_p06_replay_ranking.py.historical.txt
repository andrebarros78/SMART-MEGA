from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\smart_signal_agent.py')
s=p.read_text(encoding='utf-8-sig')
needle="                         'rank_calibration_before_result': pred.rank_score_calibration,\n"
assert needle in s
s=s.replace(needle,"                         'ranking60_before_result': pred.ranking60,\n                         'rank_calibration_before_result': pred.rank_score_calibration,\n")
p.write_text(s,encoding='utf-8')
print('patched')
