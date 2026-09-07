from pathlib import Path
p=Path('smart_agent_skill_orchestration.py')
s=p.read_text(encoding='utf-8')
old='''    state_paths = _resolve_state_paths(root)\n    ledger_path = state_paths["ledger"]\n    return {\n'''
new='''    if rollover_from_adjudicated_parallel:\n        ledger_path = root / "SMART_SIGNAL_LEDGER.json"\n    else:\n        state_paths = _resolve_state_paths(root)\n        ledger_path = state_paths["ledger"]\n    return {\n'''
if old not in s:
    raise SystemExit('target block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('PATCH_LEDGER_OK')
