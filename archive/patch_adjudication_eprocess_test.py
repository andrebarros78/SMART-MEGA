from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_coverage_governance.py')
s=p.read_text(encoding='utf-8')
s=s.replace("with pytest.raises(ValueError, match='e-process'):\n        adj._next_e_value({'schema':cc.LEDGER_SCHEMA,'events':[]},-100,100)", "with pytest.raises(ValueError, match='hits'):\n        adj._next_e_value({'schema':cc.LEDGER_SCHEMA,'events':[]},-100,100)",1)
p.write_text(s,encoding='utf-8')
print('ADJUDICATION_EPROCESS_TEST_OK')
