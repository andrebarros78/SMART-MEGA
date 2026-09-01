from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_promotion_gate.py')
s=p.read_text(encoding='utf-8')
old="freeze_hash = f'freeze-{contest}'"
new="freeze_hash = f'{contest:064x}'[-64:]"
if old not in s:
    raise SystemExit('freeze fixture marker missing')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
print('P13_HEX_FREEZE_FIXTURE_OK')
