from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ['test_smart_multi_challengers.py','test_smart_rank_score_calibration.py','test_smart_signal_marginal_utility.py']:
 p=ROOT/name; s=p.read_text(encoding='utf-8'); s=s.replace("SMART_SIGNAL_STATE_7","SMART_SIGNAL_STATE_8"); p.write_text(s,encoding='utf-8')
print('updated p08 state fixtures')