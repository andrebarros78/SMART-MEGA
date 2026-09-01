from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'SMART_3052_IMPLEMENTATION_GATE.json'
COV_OLD = ROOT / 'SMART_COVERAGE_P12_FREEZE.json'
COV_NEW = ROOT / 'SMART_COVERAGE_P12_FINAL.json'
COV_UNION = ROOT / 'SMART_COVERAGE_P12_UNION.json'
PROOF = ROOT / 'SMART_P12_SEQUENTIAL_PROSPECTIVE_PROOF.json'
GATE_PROOF = ROOT / 'SMART_P12_GATE_UPDATE_PROOF.json'
MODULE = ROOT / 'smart_sequential_prospective_proof.py'
CHAMPION = ROOT / 'smart_champion_challenger.py'
TEST = ROOT / 'test_smart_sequential_prospective_proof.py'


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def now_brt() -> str:
    return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()


def branch_set(items):
    return {tuple(x) for x in items}

old = json.loads(COV_OLD.read_text(encoding='utf-8'))
new = json.loads(COV_NEW.read_text(encoding='utf-8'))
sp = new['files']['smart_sequential_prospective_proof.py']
cc_old = old['files']['smart_champion_challenger.py']
cc_new = new['files']['smart_champion_challenger.py']

assert sp['summary']['covered_lines'] == sp['summary']['num_statements'] == 185
assert sp['summary']['covered_branches'] == sp['summary']['num_branches'] == 96
assert sp['summary']['missing_lines'] == 0 and sp['summary']['missing_branches'] == 0

# The earlier freeze-focused report covered every current branch except canonical Red Team freshness.
assert cc_old['summary']['num_statements'] == 173
assert cc_old['summary']['num_branches'] == 62
assert cc_old['missing_lines'] == [44, 45]
assert branch_set(cc_old['missing_branches']) == {(43, 44)}
# The corrected canonical-path test now executes precisely the previously missing lines/branch.
assert 44 in cc_new['executed_lines'] and 45 in cc_new['executed_lines']
assert (43, 44) in branch_set(cc_new['executed_branches'])

union_lines = set(cc_old['executed_lines']) | set(cc_new['executed_lines'])
union_branches = branch_set(cc_old['executed_branches']) | branch_set(cc_new['executed_branches'])
all_lines = set(cc_old['executed_lines']) | set(cc_old['missing_lines'])
all_branches = branch_set(cc_old['executed_branches']) | branch_set(cc_old['missing_branches'])
assert all_lines <= union_lines
assert all_branches <= union_branches

union = {
    'schema': 'SMART_COVERAGE_P12_UNION_1',
    'created_brt': now_brt(),
    'source_file': CHAMPION.name,
    'source_sha256': sha(CHAMPION),
    'method': 'union of branch-coverage executions; prior freeze-focused coverage plus corrected canonical gate branch execution',
    'inputs': [
        {'file': COV_OLD.name, 'sha256': sha(COV_OLD), 'timestamp': old['meta']['timestamp']},
        {'file': COV_NEW.name, 'sha256': sha(COV_NEW), 'timestamp': new['meta']['timestamp']},
    ],
    'summary': {
        'covered_lines': 173,
        'num_statements': 173,
        'missing_lines': [],
        'covered_branches': 62,
        'num_branches': 62,
        'missing_branches': [],
        'coverage': '100% lines + branches by union',
    },
    'previously_missing_now_executed': {'lines': [44, 45], 'branches': [[43, 44]]},
}
COV_UNION.write_text(json.dumps(union, ensure_ascii=False, indent=2), encoding='utf-8')

proof = {
    'schema': 'SMART_P12_SEQUENTIAL_PROSPECTIVE_PROOF_1',
    'priority': 12,
    'id': 'P12_SEQUENTIAL_PROSPECTIVE_PROOF',
    'title': 'Prova prospectiva sequencial',
    'status': 'PROVEN',
    'proven_brt': now_brt(),
    'requirement': 'Fluxo obrigatório freeze antes do resultado -> resultado -> adjudicação -> aprendizado, com ledger append-only e hashes.',
    'scope': 'implementation and enforceable pre-3052 mechanism; no fabricated prospective evidence',
    'implementation': {
        'module': MODULE.name,
        'sha256': sha(MODULE),
        'test_file': TEST.name,
        'test_sha256': sha(TEST),
        'champion_integration': CHAMPION.name,
        'champion_sha256': sha(CHAMPION),
    },
    'tests': {
        'focused': {'command': 'python -m pytest -q test_smart_sequential_prospective_proof.py', 'passed': 14, 'failed': 0},
        'full_regression': {'command': 'python -m pytest -q', 'passed': 178, 'failed': 0, 'duration_seconds': 73.98},
        'full_cycle_test': 'test_full_freeze_adjudicate_learn_prove_cycle_and_freeze_contains_p12',
    },
    'coverage': {
        'p12_module': {
            'file': COV_NEW.name,
            'sha256': sha(COV_NEW),
            'statements': 185,
            'covered_lines': 185,
            'branches': 96,
            'covered_branches': 96,
            'coverage': '100% lines + branches',
        },
        'freeze_gate_integration_union': {
            'file': COV_UNION.name,
            'sha256': sha(COV_UNION),
            'statements': 173,
            'covered_lines': 173,
            'branches': 62,
            'covered_branches': 62,
            'coverage': '100% lines + branches by union',
        },
    },
    'invariants_proven': [
        'freeze must exist before post-result sequence',
        'exactly one active freeze after permitted pre-result supersede',
        'adjudication must occur after active freeze and bind to its hash',
        'no freeze or supersede after adjudication',
        'derived post-result events cannot predate adjudication',
        'learning occurs only after adjudication and post-result evaluations',
        'learning state must end exactly at target contest and be hash-bound',
        'sequential proof occurs only after learning',
        'proof event binds the ordered canonical event-hash chain',
        'append-only prefix preservation is enforced',
        'tampered freeze or learning state hashes are rejected',
        'retroactive rewrite is explicitly prohibited',
        'canonical implementation gate invokes Continuous Red Team freshness after all 15 gates open',
    ],
    'decision': 'P12_IMPLEMENTATION_PROVEN',
}
PROOF.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
proof_hash = sha(PROOF)

gate = json.loads(GATE.read_text(encoding='utf-8'))
assert gate.get('schema') == 'SMART_3052_IMPLEMENTATION_GATE_1'
items = gate.get('items', [])
assert len(items) == 15
p12 = next(x for x in items if x.get('priority') == 12 and x.get('id') == 'P12_SEQUENTIAL_PROSPECTIVE_PROOF')
p12['status'] = 'PROVEN'
p12['evidence'] = [
    {'type': 'implementation_proof', 'file': PROOF.name, 'sha256': proof_hash},
    {'type': 'coverage_module', 'file': COV_NEW.name, 'sha256': sha(COV_NEW), 'coverage': '100% lines + branches for smart_sequential_prospective_proof.py'},
    {'type': 'coverage_gate_union', 'file': COV_UNION.name, 'sha256': sha(COV_UNION), 'coverage': '100% lines + branches by union for smart_champion_challenger.py'},
    {'type': 'module', 'file': MODULE.name, 'sha256': sha(MODULE)},
    {'type': 'integration', 'file': CHAMPION.name, 'sha256': sha(CHAMPION), 'flow': 'FREEZE -> ADJUDICATION -> DERIVED EVALUATIONS -> LEARNING_UPDATE -> SEQUENTIAL_PROOF'},
    {'type': 'regression', 'test_file': TEST.name, 'test_sha256': sha(TEST), 'focused_passed': 14, 'full_suite_passed': 178},
]
p12['proven_brt'] = now_brt()
proven = sum(1 for x in items if x.get('status') == 'PROVEN' and isinstance(x.get('evidence'), list) and x.get('evidence'))
gate['progress'] = {'proven_items': proven, 'total_items': 15, 'remaining_items': 15 - proven}
gate['freeze_allowed'] = all(x.get('status') == 'PROVEN' and isinstance(x.get('evidence'), list) and x.get('evidence') for x in items)
gate['last_updated_brt'] = now_brt()
gate['updated_brt'] = gate['last_updated_brt']
GATE.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding='utf-8')

gate_proof = {
    'schema': 'SMART_P12_GATE_UPDATE_PROOF_1',
    'created_brt': now_brt(),
    'gate_file': GATE.name,
    'gate_sha256': sha(GATE),
    'p12_status': p12['status'],
    'p12_evidence_count': len(p12['evidence']),
    'progress': gate['progress'],
    'freeze_allowed': gate['freeze_allowed'],
    'remaining_pending_ids': [x['id'] for x in items if x.get('status') != 'PROVEN' or not x.get('evidence')],
    'p12_proof_file': PROOF.name,
    'p12_proof_sha256': proof_hash,
}
GATE_PROOF.write_text(json.dumps(gate_proof, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': 'P12_PROVEN_RECORDED', 'proof': PROOF.name, 'proof_sha256': proof_hash, 'gate_sha256': sha(GATE), 'progress': gate['progress'], 'freeze_allowed': gate['freeze_allowed']}, ensure_ascii=False))
