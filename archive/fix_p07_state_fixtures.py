from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
for name in ['test_smart_rank_score_calibration.py','test_smart_signal_marginal_utility.py']:
    p=root/name
    s=p.read_text(encoding='utf-8-sig').replace("SMART_SIGNAL_STATE_6","SMART_SIGNAL_STATE_7")
    p.write_text(s,encoding='utf-8')
print('updated fixtures')