from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_evidence_only_promotion.py')
s=p.read_text(encoding='utf-8')
if 'import smart_global_integrity as gi' not in s:
    s=s.replace('import smart_evidence_only_promotion as p15\n', 'import smart_evidence_only_promotion as p15\nimport smart_global_integrity as gi\n',1)

start=s.index('def _gate(')
end=s.index('\n\ndef _audit',start)
new_gate="""def _gate(all_proven: bool = True, freeze_allowed: bool = True) -> dict:\n    items = []\n    ids = list(gi.EXPECTED_GATE_IDS)\n    for i, item_id in enumerate(ids, start=1):\n        proven = all_proven or i != 14\n        items.append({\n            'priority': i, 'id': item_id,\n            'status': 'PROVEN' if proven else 'TO_VERIFY_OR_IMPLEMENT',\n            'evidence': [{'file': f'proof-{i}.json', 'sha256': f'{i:064x}'[-64:]}] if proven else [],\n        })\n    proven_count = sum(1 for row in items if row['status'] == 'PROVEN')\n    return {\n        'schema': p15.IMPLEMENTATION_GATE_SCHEMA, 'target_contest': 3052,\n        'mandatory_before_freeze': True, 'freeze_allowed': freeze_allowed,\n        'completion_rule': 'ALL_15_ITEMS_STATUS_PROVEN_WITH_EVIDENCE',\n        'governance': {k: True for k in gi.REQUIRED_GATE_GOVERNANCE},\n        'items': items,\n        'progress': {'proven_items': proven_count, 'total_items': 15,\n                     'remaining_items': 15 - proven_count,\n                     'remaining_ids': [row['id'] for row in items if row['status'] != 'PROVEN']},\n    }\n\n\ndef _integrity() -> dict:\n    return {\n        'status': 'PASS', 'proof_file': gi.DEFAULT_PROOF_PATH.name, 'proof_file_sha256': 'f' * 64,\n        'critical_source_hashes_current': True, 'coverage_current': True,\n        'red_team_current': True, 'independent_audit_current': True,\n        'full_regression_current': True, 'material_deficiencies': [],\n    }\n"""
s=s[:start]+new_gate+s[end:]

s=s.replace("status = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status))", "status = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status), _integrity())")
s=s.replace("authorized = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), _audit())", "authorized = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), _audit(), _integrity())")
s=s.replace("assert policy['all_15_implementation_items_proven_required'] is True", "assert policy['all_15_implementation_items_proven_required'] is True\n    assert policy['current_global_integrity_proof_required'] is True")

# Add explicit global-integrity negative/positive contract test before gate tests.
marker='def test_gate_must_be_exactly_15_of_15_proven_and_freeze_allowed():'
insert="""def test_global_integrity_is_mandatory_for_authorization():\n    p13_status = _p13_eligible()\n    blocked = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status))\n    assert blocked['authorized'] is False\n    assert 'global_integrity_missing_or_unverified' in blocked['blockers']\n    assert blocked['global_integrity_verified'] is False\n    bad = _integrity(); bad['coverage_current'] = False\n    blocked = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status), bad)\n    assert 'global_integrity_current_evidence_incomplete' in blocked['blockers']\n    allowed = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status), _integrity())\n    assert allowed['authorized'] is True and allowed['global_integrity_verified'] is True\n\n\n"""
if marker not in s: raise SystemExit('gate test marker missing')
s=s.replace(marker,insert+marker,1)

# File-based test: inject monkeypatch and current verifier.
s=s.replace('def test_file_based_assessment_records_evidence_hashes_and_fails_closed_when_missing(tmp_path: Path):',
            'def test_file_based_assessment_records_evidence_hashes_and_fails_closed_when_missing(monkeypatch, tmp_path: Path):')
needle="""    gate_path = tmp_path / 'gate.json'; audit_path = tmp_path / 'audit.json'\n"""
repl="""    monkeypatch.setattr(gi, 'verify_global_integrity', lambda **kwargs: _integrity())\n    gate_path = tmp_path / 'gate.json'; audit_path = tmp_path / 'audit.json'\n"""
if needle not in s: raise SystemExit('file test marker missing')
s=s.replace(needle,repl,1)

# Champion integration allowed path gets verifier monkeypatch.
s=s.replace('def test_champion_challenger_separates_p13_eligibility_from_p15_authorization(tmp_path: Path):',
            'def test_champion_challenger_separates_p13_eligibility_from_p15_authorization(monkeypatch, tmp_path: Path):')
needle2="""    ledger = _ledger()\n"""
# Replace only occurrence after function by local slicing.
pos=s.index('def test_champion_challenger_separates_p13_eligibility_from_p15_authorization')
pos2=s.index(needle2,pos)
s=s[:pos2]+"    monkeypatch.setattr(gi, 'verify_global_integrity', lambda **kwargs: _integrity())\n"+s[pos2:]

p.write_text(s,encoding='utf-8')
print('P15_TESTS_GLOBAL_INTEGRITY_OK')
