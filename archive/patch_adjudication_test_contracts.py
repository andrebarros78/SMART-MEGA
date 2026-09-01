from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
# Production: bind global integrity policy too.
p=root/'adjudicate_signal_challenger.py'
s=p.read_text(encoding='utf-8')
s=s.replace("""        'independent_audit_policy', 'evidence_only_promotion_policy', 'promotion_lineage',\n""", """        'independent_audit_policy', 'evidence_only_promotion_policy', 'global_integrity_policy',\n        'promotion_lineage',\n""",1)
p.write_text(s,encoding='utf-8')

# Test helper: construct a minimally valid cryptographically linked freeze artifact.
t=root/'test_smart_coverage_governance.py'
x=t.read_text(encoding='utf-8')
start=x.index('def make_freeze_ledger(')
end=x.index('\n\ndef result_excel',start)
new="""def make_freeze_ledger(tmp_path: Path, target=10):\n    values = {str(i): float(i) / 60.0 for i in range(1, 61)}\n    values2 = {str(i): float(61-i) / 60.0 for i in range(1, 61)}\n    challenger_payload = {\n        'top6': [1,2,3,4,5,7],\n        'raw_signals': {'freq25': {'values': values}, 'freq50': {'values': values2}},\n        'weights': {'freq25': 0.6, 'freq50': 0.4},\n        'quality_metrics': {'freq25': {'quality': 1.0}, 'freq50': {'quality': 1.0}},\n    }\n    snapshot = {\n        'raw_signals': challenger_payload['raw_signals'],\n        'weights': challenger_payload['weights'],\n        'quality_metrics': challenger_payload['quality_metrics'],\n    }\n    freeze_file = tmp_path / f'freeze_{target}.json'\n    data_sha = 'd' * 64; engine_sha = 'e' * 64\n    frozen = {\n        'schema': 'SMART_CHAMPION_CHALLENGER_FREEZE_2', 'target_contest': target,\n        'cutoff_contest': target - 1, 'frozen_before_result': True, 'causal_cutoff': True,\n        'data_sha256': data_sha, 'engine_sha256': engine_sha,\n        'champion': {'top6': [1,2,3,4,5,6]}, 'challenger': challenger_payload,\n    }\n    freeze_file.write_text(json.dumps(frozen), encoding='utf-8')\n    h = cc.sha256(freeze_file)\n    event = {\n        'event_type': 'FREEZE', 'target_contest': target, 'cutoff_contest': target - 1,\n        'freeze_file': str(freeze_file), 'freeze_sha256': h, 'frozen_before_result': True,\n        'causal_cutoff': True, 'data_sha256': data_sha,\n        'champion_top6': [1,2,3,4,5,6], 'challenger_top6': [1,2,3,4,5,7],\n        'snapshot': snapshot, 'hashes': {'engine': engine_sha},\n    }\n    ledger = {'schema': cc.LEDGER_SCHEMA, 'events': [event]}\n    ledger_path = tmp_path / 'ledger.json'; cc.write_ledger(ledger_path, ledger)\n    return ledger_path, event\n"""
x=x[:start]+new+x[end:]
t.write_text(x,encoding='utf-8')
print('ADJUDICATION_TEST_CONTRACTS_OK')
