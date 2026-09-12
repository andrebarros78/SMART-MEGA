from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
p=root/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8')
old="""def active_freeze(ledger: dict[str, Any], target: int) -> dict[str, Any] | None:\n    freezes = freeze_events(ledger, target)\n    if not freezes:\n        return None\n    _validate_ledger_contract(ledger)\n"""
new="""def active_freeze(ledger: dict[str, Any], target: int) -> dict[str, Any] | None:\n    _validate_ledger_contract(ledger)\n    freezes = freeze_events(ledger, target)\n    if not freezes:\n        return None\n"""
if old not in s:
    raise SystemExit('active_freeze marker missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

p2=root/'smart_sequential_prospective_proof.py'
s2=p2.read_text(encoding='utf-8')
old2="""        'linear_supersede_chain_required': True,\n        'adjudication_unique_required': True,\n"""
new2="""        'linear_supersede_chain_required': True,\n        'supersede_must_immediately_link_new_freeze': True,\n        'adjudication_unique_required': True,\n"""
if old2 not in s2:
    raise SystemExit('P12 followup marker missing')
s2=s2.replace(old2,new2,1)
p2.write_text(s2,encoding='utf-8')
print('LEDGER_CONTRACT_FOLLOWUP_OK')
