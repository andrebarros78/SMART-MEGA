from __future__ import annotations

from pathlib import Path

ROOT=Path(r'C:\New Projet\SMART-MEGA')

# P13: validate hit-domain on every causal adjudication before lineage filtering.
p=ROOT/'smart_champion_challenger.py'; s=p.read_text(encoding='utf-8')
old="""        if not fr.get('frozen_before_result') or not fr.get('causal_cutoff'):\n            continue\n        fingerprint = _promotion_candidate_fingerprint(fr)\n"""
new="""        if not fr.get('frozen_before_result') or not fr.get('causal_cutoff'):\n            continue\n        raw_record = {'challenger_hits': ad.get('challenger_hits'), 'champion_hits': ad.get('champion_hits')}\n        assess_promotion_records([raw_record], 1.0)\n        fingerprint = _promotion_candidate_fingerprint(fr)\n"""
if old not in s: raise RuntimeError('P13 causal validation marker missing')
s=s.replace(old,new,1); p.write_text(s,encoding='utf-8')

# P14: inspect the actual runtime module; if a project-root copy exists it must match runtime.
p=ROOT/'smart_independent_audit.py'; s=p.read_text(encoding='utf-8')
old="""def audit_independence(root: Path) -> dict[str, Any]:\n    root = Path(root)\n    source = root / 'smart_independent_audit.py'\n    if not source.is_file():\n        raise ValueError('independent audit source missing')\n    tree = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))\n"""
new="""def audit_independence(root: Path) -> dict[str, Any]:\n    root = Path(root)\n    runtime_source = Path(__file__).resolve()\n    project_source = (root / 'smart_independent_audit.py').resolve()\n    if project_source.is_file():\n        if sha256_file(project_source) != sha256_file(runtime_source):\n            raise ValueError('independent audit project/runtime source mismatch')\n        source = project_source\n    else:\n        source = runtime_source\n    tree = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))\n"""
if old not in s: raise RuntimeError('P14 independence marker missing')
s=s.replace(old,new,1)
s=s.replace("        'lineage_recomputed_independently': True,\n    }", "        'lineage_recomputed_independently': True,\n        'lineage_pairs_recomputed': True,\n    }", 1)
p.write_text(s,encoding='utf-8')

# P15: eligible P13 must be lineage-bound. Validate global and lineage comparisons separately.
p=ROOT/'smart_evidence_only_promotion.py'; s=p.read_text(encoding='utf-8')
old="""    if int(p13['n']) < 0:\n        raise ValueError('P13 n must be non-negative')\n    return p13\n"""
new="""    if int(p13['n']) < 0:\n        raise ValueError('P13 n must be non-negative')\n    if eligible:\n        fingerprint = p13.get('candidate_fingerprint')\n        if not isinstance(fingerprint, str) or len(fingerprint) != 64:\n            raise ValueError('P13 eligible status must be bound to a 64-hex candidate fingerprint')\n        try:\n            int(fingerprint, 16)\n        except ValueError as exc:\n            raise ValueError('P13 eligible candidate fingerprint must be hexadecimal') from exc\n        if int(p13.get('lineage_pair_count', -1)) != int(p13['n']):\n            raise ValueError('P13 eligible lineage pair count must equal n')\n    return p13\n"""
if old not in s: raise RuntimeError('P15 P13 validation marker missing')
s=s.replace(old,new,1)
start=s.index("    comparison = ledger.get('promotion_lineage_comparison')")
end=s.index("    if 'material_deficiencies' not in audit:", start)
replacement="""    global_comparison = ledger.get('full_champion_comparison') if isinstance(ledger, dict) else None\n    if not isinstance(global_comparison, dict):\n        blockers.append('independent_audit_champion_comparison_missing')\n    elif global_comparison.get('all_pairs_recomputed') is not True:\n        blockers.append('independent_audit_not_all_pairs_recomputed')\n\n    comparison = ledger.get('promotion_lineage_comparison') if isinstance(ledger, dict) else None\n    if not isinstance(comparison, dict):\n        blockers.append('independent_audit_promotion_lineage_comparison_missing')\n        comparison = {}\n    else:\n        expected = {\n            'adjudicated_contests': int(p13['n']),\n            'champion_hits': int(p13['champion_hits']),\n            'challenger_hits': int(p13['challenger_hits']),\n            'advantage_hits': int(p13['advantage_hits']),\n            'cumulative_regret': int(p13['cumulative_regret']),\n        }\n        for field, value in expected.items():\n            if comparison.get(field) != value:\n                blockers.append(f'p13_p14_metric_mismatch_{field}')\n        if comparison.get('adjudicated_contests') != int(p13['n']):\n            blockers.append('p13_p14_pair_count_mismatch')\n        if comparison.get('candidate_fingerprint') != p13.get('candidate_fingerprint'):\n            blockers.append('p13_p14_lineage_fingerprint_mismatch')\n        if comparison.get('lineage_recomputed_independently') is not True or comparison.get('lineage_pairs_recomputed') is not True:\n            blockers.append('independent_audit_promotion_lineage_not_recomputed')\n        observed_lineage_e = comparison.get('e_value')\n        if not isinstance(observed_lineage_e, (int, float)) or isinstance(observed_lineage_e, bool) or not math.isfinite(float(observed_lineage_e)) or not math.isclose(float(observed_lineage_e), float(p13['e_value']), rel_tol=1e-12, abs_tol=1e-12):\n            blockers.append('p13_p14_lineage_e_value_mismatch')\n\n"""
s=s[:start]+replacement+s[end:]
p.write_text(s,encoding='utf-8')

# Tests: synthetic ledgers carry a valid stable lineage; P15 fixtures model the new audit contract.
p=ROOT/'test_smart_promotion_gate.py'; s=p.read_text(encoding='utf-8')
if 'import hashlib\n' not in s: s=s.replace('import json\n','import hashlib\nimport json\n',1)
old="""def _ledger(n: int, challenger: int, champion: int, e_value: float):\n    events = []\n    for i in range(n):\n        contest = 4000 + i\n        freeze_hash = f'freeze-{contest}'\n        events.append({\n            'event_type': 'FREEZE',\n            'target_contest': contest,\n            'freeze_sha256': freeze_hash,\n            'frozen_before_result': True,\n            'causal_cutoff': True,\n        })\n"""
new="""def _ledger(n: int, challenger: int, champion: int, e_value: float):\n    events = []\n    component_hashes = {name: f'{idx + 1:064x}' for idx, name in enumerate(cc.PROMOTION_LINEAGE_COMPONENTS)}\n    lineage = {'schema': cc.PROMOTION_LINEAGE_SCHEMA, 'component_hashes': component_hashes}\n    lineage['sha256'] = hashlib.sha256(json.dumps(lineage, sort_keys=True, separators=(',', ':')).encode()).hexdigest()\n    for i in range(n):\n        contest = 4000 + i\n        freeze_hash = f'freeze-{contest}'\n        events.append({\n            'event_type': 'FREEZE',\n            'target_contest': contest,\n            'freeze_sha256': freeze_hash,\n            'frozen_before_result': True,\n            'causal_cutoff': True,\n            'hashes': component_hashes,\n            'promotion_lineage': lineage,\n        })\n"""
if old not in s: raise RuntimeError('P13 test ledger marker missing')
s=s.replace(old,new,1); p.write_text(s,encoding='utf-8')

p=ROOT/'test_smart_evidence_only_promotion.py'; s=p.read_text(encoding='utf-8')
if 'import hashlib\n' not in s: s=s.replace('import copy\n','import copy\nimport hashlib\n',1)
old="""def _p13_eligible() -> dict:\n    return assess_promotion_records(\n        [{'challenger_hits': 4, 'champion_hits': 3} for _ in range(20)],\n        e_value=10.0,\n    )\n"""
new="""def _p13_eligible() -> dict:\n    status = assess_promotion_records(\n        [{'challenger_hits': 4, 'champion_hits': 3} for _ in range(20)],\n        e_value=10.0,\n    )\n    status['candidate_fingerprint'] = 'a' * 64\n    status['lineage_pair_count'] = int(status['n'])\n    return status\n"""
if old not in s: raise RuntimeError('P15 p13 helper marker missing')
s=s.replace(old,new,1)
old="""    comparison = {\n        'adjudicated_contests': int(p13_status['n']),\n        'champion_hits': int(p13_status['champion_hits']),\n        'challenger_hits': int(p13_status['challenger_hits']),\n        'advantage_hits': int(p13_status['advantage_hits']),\n        'cumulative_regret': int(p13_status['cumulative_regret']),\n        'all_pairs_recomputed': True,\n    }\n"""
new="""    comparison = {\n        'adjudicated_contests': int(p13_status['n']),\n        'champion_hits': int(p13_status['champion_hits']),\n        'challenger_hits': int(p13_status['challenger_hits']),\n        'advantage_hits': int(p13_status['advantage_hits']),\n        'cumulative_regret': int(p13_status['cumulative_regret']),\n        'all_pairs_recomputed': True,\n    }\n    lineage_comparison = {\n        **{k: comparison[k] for k in ('adjudicated_contests','champion_hits','challenger_hits','advantage_hits','cumulative_regret')},\n        'candidate_fingerprint': p13_status.get('candidate_fingerprint'),\n        'e_value': float(p13_status['e_value']),\n        'lineage_recomputed_independently': True,\n        'lineage_pairs_recomputed': True,\n    }\n"""
if old not in s: raise RuntimeError('P15 comparison helper marker missing')
s=s.replace(old,new,1)
s=s.replace("            'full_champion_comparison': comparison,\n", "            'full_champion_comparison': comparison,\n            'promotion_lineage_comparison': lineage_comparison,\n",1)
s=s.replace("        'independent_of_promotion_decision': True,\n        'material_deficiencies': [],", "        'independent_of_promotion_decision': True,\n        'independence': {'status':'PASS','independent':True,'static_import_scan':True,'forbidden_dependencies_found':[]},\n        'material_deficiencies': [],",1)
# Synthetic ledger used by cc.promotion_eligibility_status must also carry lineage.
old="""def _ledger(n: int = 20, challenger: int = 4, champion: int = 3, e_value: float = 10.0) -> dict:\n    events = []\n    for i in range(n):\n        contest = 5000 + i\n        h = f'{contest:064x}'[-64:]\n        events.append({\n            'event_type': 'FREEZE',\n            'target_contest': contest,\n            'freeze_sha256': h,\n            'frozen_before_result': True,\n            'causal_cutoff': True,\n        })\n"""
new="""def _ledger(n: int = 20, challenger: int = 4, champion: int = 3, e_value: float = 10.0) -> dict:\n    events = []\n    component_hashes = {name: f'{idx + 101:064x}' for idx, name in enumerate(cc.PROMOTION_LINEAGE_COMPONENTS)}\n    lineage = {'schema': cc.PROMOTION_LINEAGE_SCHEMA, 'component_hashes': component_hashes}\n    lineage['sha256'] = hashlib.sha256(json.dumps(lineage, sort_keys=True, separators=(',', ':')).encode()).hexdigest()\n    for i in range(n):\n        contest = 5000 + i\n        h = f'{contest:064x}'[-64:]\n        events.append({\n            'event_type': 'FREEZE',\n            'target_contest': contest,\n            'freeze_sha256': h,\n            'frozen_before_result': True,\n            'causal_cutoff': True,\n            'hashes': component_hashes,\n            'promotion_lineage': lineage,\n        })\n"""
if old not in s: raise RuntimeError('P15 ledger helper marker missing')
s=s.replace(old,new,1)
# Metric identity tests target lineage comparison, while global recomputation stays separately tested.
s=s.replace("audit['prospective_ledger']['full_champion_comparison'][field] += 1", "audit['prospective_ledger']['promotion_lineage_comparison'][field] += 1")
s=s.replace("audit = _audit(p13_status); audit['prospective_ledger']['pair_count'] += 1;", "audit = _audit(p13_status); audit['prospective_ledger']['promotion_lineage_comparison']['adjudicated_contests'] += 1;")
p.write_text(s,encoding='utf-8')

print('POST_HARDENING_CONTRACT_PATCH_OK')
