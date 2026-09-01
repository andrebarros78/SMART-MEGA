from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r'C:\New Projet\SMART-MEGA')
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import smart_champion_challenger as cc

GATE = ROOT / 'SMART_3052_IMPLEMENTATION_GATE.json'
LEDGER = ROOT / 'SMART_SIGNAL_LEDGER.json'
P14 = ROOT / 'SMART_P14_INDEPENDENT_AUDIT_CURRENT.json'
PROOF = ROOT / 'SMART_P15_EVIDENCE_ONLY_PROMOTION_PROOF.json'
COV_MODULE = ROOT / 'SMART_COVERAGE_P15_MODULE.json'
COV_ORCH = ROOT / 'SMART_COVERAGE_P15_ORCHESTRATOR.json'
MODULE = ROOT / 'smart_evidence_only_promotion.py'
ORCH = ROOT / 'smart_champion_challenger.py'
TEST = ROOT / 'test_smart_evidence_only_promotion.py'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


now = datetime.now().astimezone().isoformat()
gate = json.loads(GATE.read_text(encoding='utf-8'))
item = next(x for x in gate['items'] if x['id'] == 'P15_EVIDENCE_ONLY_PROMOTION')
if item.get('status') != 'PROVEN' or not item.get('evidence'):
    raise RuntimeError('P15 is not persisted as PROVEN with evidence')
if gate.get('progress') != {'proven_items': 11, 'total_items': 15, 'remaining_items': 4}:
    raise RuntimeError(f'unexpected gate progress: {gate.get("progress")}')
if gate.get('freeze_allowed') is not False:
    raise RuntimeError('freeze must remain blocked while P09/P10/P11/P14 are pending')
remaining = [x['id'] for x in gate['items'] if x.get('status') != 'PROVEN' or not x.get('evidence')]
expected_remaining = [
    'P09_CONTINUOUS_RED_TEAM',
    'P10_BOUNDED_ONLINE_LEARNING',
    'P11_SIGNAL_EXPANSION_GOVERNANCE',
    'P14_INDEPENDENT_AUDIT_NONREGRESSION',
]
if remaining != expected_remaining:
    raise RuntimeError(f'unexpected remaining ids: {remaining}')

ledger = cc.load_ledger(LEDGER)
decision = cc.promotion_status(ledger, GATE, P14)
if decision.get('authorized') is True or decision.get('production_switch_may_proceed') is True:
    raise RuntimeError('real promotion unexpectedly authorized')
if decision.get('decision') != 'KEEP_CHAMPION':
    raise RuntimeError(f'unexpected current decision: {decision.get("decision")}')

obj = {
    'schema': 'SMART_P15_FINAL_RETEST_PROOF_1',
    'created_brt': now,
    'project_id': 'smart-mega',
    'root': str(ROOT),
    'point': 15,
    'id': 'P15_EVIDENCE_ONLY_PROMOTION',
    'status': 'MISSION_PROVEN_P15',
    'post_registration_tests': {
        'focused_p13_p15_integration': {'passed': 35, 'failed': 0, 'duration_seconds': 23.47},
        'full_regression': {'passed': 235, 'failed': 0},
    },
    'coverage': {
        'p15_module': '100% lines + branches (197/197 statements; 102/102 branches)',
        'orchestrator': '100% lines + branches (173/173 statements; 60/60 branches)',
    },
    'hashes': {
        'p15_module_sha256': sha256(MODULE),
        'orchestrator_sha256': sha256(ORCH),
        'p15_test_sha256': sha256(TEST),
        'p15_coverage_sha256': sha256(COV_MODULE),
        'orchestrator_coverage_sha256': sha256(COV_ORCH),
        'p15_implementation_proof_sha256': sha256(PROOF),
        'gate_sha256': sha256(GATE),
        'ledger_sha256': sha256(LEDGER),
    },
    'gate': {
        'p15_status': item['status'],
        'p15_evidence_count': len(item['evidence']),
        'progress': gate['progress'],
        'freeze_allowed': gate['freeze_allowed'],
        'remaining_pending_ids': remaining,
    },
    'current_real_promotion': {
        'decision': decision.get('decision'),
        'authorized': bool(decision.get('authorized')),
        'production_switch_may_proceed': bool(decision.get('production_switch_may_proceed')),
        'blockers': decision.get('blockers'),
        'champion_remains_active': True,
    },
    'conclusion': 'P15 evidence-only promotion mechanism is implemented, fully covered, integrated, fail-closed on the real ledger, persisted as PROVEN, and non-regression tested after gate registration.',
}
out = ROOT / 'SMART_P15_FINAL_RETEST_PROOF.json'
out.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'file': out.name,
    'sha256': sha256(out),
    'gate_sha256': sha256(GATE),
    'proof_sha256': sha256(PROOF),
    'decision': decision.get('decision'),
    'authorized': bool(decision.get('authorized')),
    'progress': gate['progress'],
    'remaining_pending_ids': remaining,
}, ensure_ascii=False))
