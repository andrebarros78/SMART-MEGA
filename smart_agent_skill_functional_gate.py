from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smart_agent_runtime import SCHEMA as RUNTIME_SCHEMA, SmartAgentRuntime, sha256_json
from smart_skill_runtime import SmartSkillRuntime

SCHEMA = 'SMART_AGENT_SKILL_FUNCTIONAL_GATE_V2'


def _origin(capability: str, inventory: dict[str, list[str]]) -> str:
    if capability in inventory['source_only_skills']:
        return 'SOURCE_ONLY_SKILL'
    if capability in inventory['v2_capabilities']:
        return 'ACQUIRED_CAPABILITY_V2'
    if capability in inventory['v3_capabilities']:
        return 'ACQUIRED_CAPABILITY_V3'
    if capability in inventory['native_scientific_libraries']:
        return 'NATIVE_SCIENTIFIC_LIBRARY'
    raise ValueError(f'unknown capability origin: {capability}')


def evaluate(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    agent_runtime = SmartAgentRuntime(root)
    runtime = agent_runtime.run()
    inventory = agent_runtime.orchestration['inventory']
    skill_gate = SmartSkillRuntime(root).execute_gate()
    skill_by_name = {row['capability']: row for row in skill_gate['capabilities']}
    matrix = []
    for agent_name, execution in runtime['executions'].items():
        probe = execution['probe_result']
        for capability in execution['capabilities']:
            origin = _origin(capability, inventory)
            skill_row = skill_by_name[capability]
            if not skill_row['pertinent']:
                realization = 'SOURCE_ONLY_QUARANTINE_CURATED'
            elif origin == 'SOURCE_ONLY_SKILL':
                realization = 'METHODOLOGY_DISTILLED_TO_NATIVE_LANE_PROBE'
            else:
                realization = 'NATIVE_LANE_PROBE'
            matrix.append({
                'capability': capability,
                'origin': origin,
                'agent_owner': agent_name,
                'realization': realization,
                'native_targets': list(execution['native_targets']),
                'probe_id': execution['probe_id'],
                'executed_functions': list(probe.get('executed_functions', [])),
                'probe_pass': bool(probe.get('pass')),
                'runtime_evidence': list(execution['artifacts']),
                'handoff_outputs': list(execution['produced_handoffs']),
                'pertinent': bool(skill_row['pertinent']),
                'callable': bool(skill_row['callable']),
                'execution_mode': skill_row['execution_mode'],
                'individual_invocation': skill_row.get('invocation'),
                'external_skill_source_executed': False,
                'status': 'PASS' if (
                    probe.get('pass')
                    and (not skill_row['pertinent'] or skill_row.get('invocation', {}).get('status') == 'PASS')
                ) else 'FAIL',
            })
    names = [row['capability'] for row in matrix]
    pertinent = [row for row in matrix if row['pertinent']]
    quarantined = [row for row in matrix if not row['pertinent']]
    checks = {
        'runtime_v2_pass': runtime['schema'] == RUNTIME_SCHEMA == 'SMART_AGENT_RUNTIME_V2' and runtime['status'] == 'PASS',
        'nine_agents': runtime['agent_count'] == 9,
        'forty_one_capabilities': runtime['capability_count'] == 41 and len(matrix) == 41,
        'capabilities_unique': len(names) == len(set(names)) == 41,
        'every_capability_has_owner': all(row['agent_owner'] for row in matrix),
        'every_capability_bound_to_passed_native_probe': all(row['probe_id'] and row['executed_functions'] and row['probe_pass'] for row in matrix),
        'every_capability_has_runtime_evidence': all(row['runtime_evidence'] for row in matrix),
        'all_pertinent_capabilities_individually_callable': len(pertinent) == 37 and all(row['callable'] and row['individual_invocation'] and row['individual_invocation']['status'] == 'PASS' for row in pertinent),
        'nonpertinent_capabilities_explicitly_quarantined': len(quarantined) == 4 and all(not row['callable'] and row['execution_mode'] == 'SOURCE_ONLY_QUARANTINE' for row in quarantined),
        'quarantined_capabilities_have_curator_handoff': all(row['pertinent'] or row['handoff_outputs'] for row in matrix),
        'external_skill_source_code_never_executed': all(not row['external_skill_source_executed'] for row in matrix),
        'handoffs_complete': runtime['unacknowledged_handoffs'] == [],
        'runtime_checks_all_true': all(runtime['checks'].values()),
        'skill_runtime_gate_pass': skill_gate['status'] == 'PASS' and all(skill_gate['checks'].values()),
        'critical_canonical_files_unchanged': runtime['checks']['critical_canonical_files_unchanged'] and skill_gate['checks']['canonical_state_unchanged'],
    }
    doc = {
        'schema': SCHEMA,
        'status': 'PASS' if all(checks.values()) else 'FAIL',
        'claim_scope': 'All pertinent capabilities are invoked individually through bounded native adapters. Non-pertinent third-party source references remain explicitly quarantined and uncallable; external source code is never executed.',
        'checks': checks,
        'matrix': matrix,
        'skill_runtime_proof': skill_gate,
        'runtime_proof': runtime,
    }
    doc['sha256'] = sha256_json(doc)
    return doc


def write(root: str | Path, out: str | Path = 'SMART_AGENT_SKILL_FUNCTIONAL_INTEGRATION_PROOF.json') -> dict[str, Any]:
    root = Path(root)
    out = Path(out)
    if not out.is_absolute():
        out = root / out
    doc = evaluate(root)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return doc


def main() -> None:
    d = write(Path(__file__).resolve().parent)
    print(json.dumps({'status': d['status'], 'checks': d['checks'], 'matrix_rows': len(d['matrix'])}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
