from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_signal_marginal_utility.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace("assert state['schema']=='SMART_SIGNAL_STATE_5'", "assert state['schema']=='SMART_SIGNAL_STATE_6'")
p.write_text(s,encoding='utf-8')
print('fixture updated')
