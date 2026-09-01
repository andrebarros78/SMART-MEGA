from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_signal_agent.py')
s=p.read_text(encoding='utf-8')
s=s.replace('import json\nfrom pathlib import Path\n','import hashlib\nimport json\nfrom pathlib import Path\n')
s=s.replace("from smart_champion_challenger import freeze_champion_challenger, promotion_eligibility_status\n", "import smart_champion_challenger as cc\nfrom smart_champion_challenger import freeze_champion_challenger, promotion_eligibility_status\n")
old="""        ledger['events'].append({'event_type': 'FREEZE', 'target_contest': c, 'frozen_before_result': True,\n                                 'causal_cutoff': True, 'freeze_sha256': freeze_hash})\n"""
new="""        component_hashes = {name: ('a' * 64) for name in cc.PROMOTION_LINEAGE_COMPONENTS}\n        lineage = {\n            'schema': cc.PROMOTION_LINEAGE_SCHEMA,\n            'component_hashes': component_hashes,\n        }\n        lineage['sha256'] = hashlib.sha256(\n            json.dumps(lineage, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')\n        ).hexdigest()\n        ledger['events'].append({'event_type': 'FREEZE', 'target_contest': c, 'frozen_before_result': True,\n                                 'causal_cutoff': True, 'freeze_sha256': freeze_hash,\n                                 'hashes': component_hashes, 'promotion_lineage': lineage})\n"""
if old not in s:
    raise SystemExit('fixture marker missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('SIGNAL_AGENT_LINEAGE_FIXTURE_OK')
