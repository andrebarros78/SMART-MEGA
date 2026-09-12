from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
p=root/'adjudicate_signal_challenger.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("from smart_signal_interactions import SCHEMA as INTERACTION_SCHEMA, analyze_snapshot as analyze_interaction_snapshot\n", "from smart_signal_interactions import SCHEMA as INTERACTION_SCHEMA, analyze_snapshot as analyze_interaction_snapshot\nfrom smart_multi_challengers import POLICY_IDS as MULTI_POLICY_IDS, SCHEMA as MULTI_SCHEMA, sha256_json as multi_sha256_json\n")
insert='''\n\ndef _multi_challenger_events(ledger: dict, target: int) -> list[dict]:\n    return [ev for ev in ledger.get('events', []) if ev.get('event_type') == 'MULTI_CHALLENGERS' and int(ev.get('target_contest', -1)) == int(target)]\n\n\ndef _build_multi_challenger_event(fr: dict, actual: list[int], target: int) -> dict | None:\n    frozen = fr.get('snapshot', {}).get('multi_challengers')\n    if frozen is None:\n        return None\n    if frozen.get('schema') != MULTI_SCHEMA or list(frozen.get('policy_ids', [])) != list(MULTI_POLICY_IDS):\n        raise ValueError('invalid frozen multi-challenger snapshot')\n    policies = frozen.get('policies', {})\n    if set(policies) != set(MULTI_POLICY_IDS):\n        raise ValueError('frozen multi-challenger policies mismatch')\n    actual_set = set(int(x) for x in actual)\n    hits = {}\n    top6 = {}\n    policy_hashes = {}\n    for pid in MULTI_POLICY_IDS:\n        nums = [int(x) for x in policies[pid].get('top6', [])]\n        if len(nums) != 6 or len(set(nums)) != 6 or min(nums) < 1 or max(nums) > 60:\n            raise ValueError('invalid frozen multi-challenger top6')\n        top6[pid] = nums\n        hits[pid] = len(set(nums) & actual_set)\n        policy_hashes[pid] = str(policies[pid].get('sha256', ''))\n    analysis = {\n        'schema': 'SMART_MULTI_CHALLENGERS_ADJUDICATION_1',\n        'policy_ids': list(MULTI_POLICY_IDS),\n        'policy_top6': top6,\n        'policy_hits': hits,\n        'policy_hashes': policy_hashes,\n        'selection_performed': False,\n        'selection_deferred_to_p08': True,\n        'retroactive_selection_prohibited': True,\n    }\n    analysis['sha256'] = multi_sha256_json(analysis)\n    return {\n        'event_type': 'MULTI_CHALLENGERS',\n        'target_contest': int(target),\n        'created_utc': datetime.now(timezone.utc).isoformat(),\n        'freeze_sha256': fr['freeze_sha256'],\n        'multi_challenger_schema': MULTI_SCHEMA,\n        'multi_challenger_engine_file': 'smart_multi_challengers.py',\n        'multi_challenger_engine_sha256': sha256(Path('smart_multi_challengers.py')),\n        'multi_challenger_sha256': analysis['sha256'],\n        'analysis': analysis,\n        'retroactive_rewrite': False,\n        'policy_effect': 'NONE_P07_SHADOW_ONLY_SELECTION_DEFERRED_TO_P08',\n    }\n'''
marker='\ndef _interaction_events(ledger: dict, target: int) -> list[dict]:\n'
if marker not in s: raise SystemExit('interaction marker missing')
s=s.replace(marker,insert+marker)
s=s.replace("    if _interaction_events(ledger, target):\n        raise ValueError('interactions cannot predate adjudication')\n", "    if _interaction_events(ledger, target):\n        raise ValueError('interactions cannot predate adjudication')\n    if _multi_challenger_events(ledger, target):\n        raise ValueError('multi-challenger evaluation cannot predate adjudication')\n")
needle="    interaction_event = _build_interaction_event(fr, actual, target)\n    calibration_event = _build_rank_calibration_event(fr, actual, target)\n"
if needle not in s:
    needle="    interaction_event = _build_interaction_event(fr, actual, target)\n"
    if needle not in s: raise SystemExit('interaction build needle missing')
    rep=needle+"    multi_event = _build_multi_challenger_event(fr, actual, target)\n"
else:
    rep="    interaction_event = _build_interaction_event(fr, actual, target)\n    calibration_event = _build_rank_calibration_event(fr, actual, target)\n    multi_event = _build_multi_challenger_event(fr, actual, target)\n"
s=s.replace(needle,rep)
# append after interaction and optional calibration block by inserting before ledger write
needle2="    ledger['events'].append(interaction_event)\n"
if needle2 not in s: raise SystemExit('append interaction missing')
s=s.replace(needle2,needle2+"    if multi_event is not None:\n        ledger['events'].append(multi_event)\n")
# return add hash if possible
needle3="            'interaction_sha256': interaction_event['interaction_sha256'],\n"
if needle3 in s:
    s=s.replace(needle3,needle3+"            'multi_challenger_sha256': None if multi_event is None else multi_event['multi_challenger_sha256'],\n")
p.write_text(s,encoding='utf-8')

# architecture adjudication dependency
p=root/'test_smart_architecture_alignment.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("'smart_signal_interactions'} <= deps['adjudicate_signal_challenger.py']", "'smart_signal_interactions', 'smart_multi_challengers'} <= deps['adjudicate_signal_challenger.py']")
p.write_text(s,encoding='utf-8')
print('patched adjudication')