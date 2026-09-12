from pathlib import Path
ROOT=Path(r'C:\New Projet\SMART-MEGA')

p=ROOT/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
old="""    if gate_path.resolve() == PRE_3052_GATE_PATH.resolve():\n        from smart_continuous_red_team import verify_latest_report\n        verify_latest_report(root=gate_path.resolve().parent)\n    return obj\n"""
new="""    if gate_path.resolve() == PRE_3052_GATE_PATH.resolve():\n        from smart_continuous_red_team import verify_latest_report\n        verify_latest_report(root=gate_path.resolve().parent)\n        from smart_global_integrity import verify_global_integrity\n        verify_global_integrity(root=gate_path.resolve().parent, gate_path=gate_path.resolve())\n    return obj\n"""
if old not in s: raise SystemExit('gate integration marker missing')
s=s.replace(old,new,1)
s=s.replace("    require_pre_3052_gate(target)\n    draws, contests = e.load_draws(data)\n",
            "    implementation_gate = require_pre_3052_gate(target)\n    draws, contests = e.load_draws(data)\n",1)
s=s.replace("        'evidence_only_promotion': sha256(Path('smart_evidence_only_promotion.py')),\n",
            "        'evidence_only_promotion': sha256(Path('smart_evidence_only_promotion.py')),\n        'global_integrity': sha256(Path('smart_global_integrity.py')),\n",1)
s=s.replace("    evidence_only_promotion_snapshot = evidence_only_promotion_policy_snapshot()\n",
            "    evidence_only_promotion_snapshot = evidence_only_promotion_policy_snapshot()\n    from smart_global_integrity import policy_snapshot as global_integrity_policy_snapshot\n    global_integrity_snapshot = global_integrity_policy_snapshot()\n    global_integrity_ref = None if implementation_gate is None else implementation_gate.get('global_integrity')\n",1)
s=s.replace("        'evidence_only_promotion_sha256': component_hashes['evidence_only_promotion'],\n",
            "        'evidence_only_promotion_sha256': component_hashes['evidence_only_promotion'],\n        'global_integrity_sha256': component_hashes['global_integrity'],\n        'global_integrity_proof': global_integrity_ref,\n",1)
s=s.replace("        'evidence_only_promotion_policy': evidence_only_promotion_snapshot,\n        'promotion_lineage': promotion_lineage,\n",
            "        'evidence_only_promotion_policy': evidence_only_promotion_snapshot,\n        'global_integrity_policy': global_integrity_snapshot,\n        'promotion_lineage': promotion_lineage,\n",1)
s=s.replace("                     'evidence_only_promotion_policy': freeze_obj['evidence_only_promotion_policy'],\n                     'promotion_lineage': promotion_lineage},\n",
            "                     'evidence_only_promotion_policy': freeze_obj['evidence_only_promotion_policy'],\n                     'global_integrity_policy': freeze_obj['global_integrity_policy'],\n                     'global_integrity_proof': global_integrity_ref,\n                     'promotion_lineage': promotion_lineage},\n",1)
p.write_text(s,encoding='utf-8')

p=ROOT/'smart_continuous_red_team.py'
s=p.read_text(encoding='utf-8-sig')
needle="    'smart_evidence_only_promotion.py',\n    'smart_signal_agent.py',"
repl="    'smart_evidence_only_promotion.py',\n    'smart_global_integrity.py',\n    'smart_signal_agent.py',"
if needle not in s: raise SystemExit('P09 global integrity hash marker missing')
s=s.replace(needle,repl,1)
p.write_text(s,encoding='utf-8')
print('GLOBAL_INTEGRITY_INTEGRATION_OK')
