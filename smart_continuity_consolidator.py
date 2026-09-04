from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FREEZE_EXPECTED_SHA256="503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"
DATA_EXPECTED_SHA256="287afcdb89ba822c6e4acc848a80583a17653d646581d2a582cad3abc1947c60"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str,Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def git(root: Path,*args: str) -> str:
    return subprocess.check_output(['git',*args],cwd=root,text=True,encoding='utf-8',errors='replace').strip()


def build(root: Path) -> dict[str,Any]:
    freeze=root/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'
    data=root/'Mega-Sena_through_3053_v2.xlsx'
    mission=read_json(root/'SMART_MISSION_STATUS.json')
    orchestration=read_json(root/'SMART_AGENT_SKILL_ORCHESTRATION.json')
    powered=read_json(root/'SMART_FALSIFICATION_REPORT_POWERED.json')
    atlas1000_path=root/'SMART_RANDOMNESS_ATLAS_1000.json'
    atlas1000=read_json(atlas1000_path) if atlas1000_path.exists() else None
    manifest1000_path=root/'SMART_NULL_UNIVERSE_MANIFEST_1000.json'
    manifest1000=read_json(manifest1000_path) if manifest1000_path.exists() else None
    p1p2=read_json(root/'SMART_P1_P2_CARTOGRAPHY_PROOF.json')
    convergence=read_json(root/'SMART_MONTE_CARLO_CONVERGENCE_1000.json')
    freeze_sha=sha(freeze)
    data_sha=sha(data)
    checks={
        'freeze_3054_immutable': freeze_sha==FREEZE_EXPECTED_SHA256,
        'dataset_3053_bound': data_sha==DATA_EXPECTED_SHA256,
        'agent_skill_integration_pass': orchestration['integration_status']=='PASS',
        'agent_skill_no_terminal_authority': orchestration['terminal_6of6_proven'] is False,
        'powered_falsification_resolution_sufficient': powered['multiplicity']['resolution_sufficient'] is True,
        'powered_falsification_no_predictive_weight': powered['predictive_weight_authorized'] is False,
        'powered_controls_detected': powered['adversarial_sensitivity']['all_expected_directions_detected'] is True,
        'mission_active_not_false_proven': mission['status']=='MISSION_ACTIVE' and mission['terminal_6of6_proven'] is False,
        'atlas_1000_complete': bool(atlas1000 and atlas1000.get('replications')==1000),
        'manifest_1000_complete': bool(manifest1000 and manifest1000.get('replications')==1000),
        'canonical_p1p2_promoted_to_1000': int(p1p2.get('replications',0))==1000 and p1p2.get('p2_atlas_sha256')==sha(root/'SMART_RANDOMNESS_ATLAS.json'),
        'convergence_audit_bound_to_1000': int(convergence.get('final_replications',0))==1000 and convergence.get('final_atlas_sha256')==sha(atlas1000_path),
        'all_agents_bounded': all(not bool(agent.get('terminal_authority')) and not bool(agent.get('predictive_weight_authorized')) and not bool(agent.get('freeze_mutation_authorized')) for agent in orchestration.get('agents',{}).values()),
    }
    return {
        'schema':'SMART_CHAT_CONSOLIDATION_20260904_V1',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'merge the two 04/09/2026 continuity threads into one canonical execution state and continue from repository reality',
        'workspace':str(root),
        'branch':git(root,'branch','--show-current'),
        'head':git(root,'rev-parse','HEAD'),
        'head_short':git(root,'rev-parse','--short','HEAD'),
        'source_threads':{
            'thread_1':{
                'reported_regression':'436 passed / 0 failed',
                'reported_state':'MISSION_ACTIVE',
                'reported_monte_carlo':'1000-replication work described as active',
                'authority':'historical continuity input only',
            },
            'thread_2':{
                'reported_regression':'461 passed / 0 failed',
                'reported_state':'MISSION_ACTIVE',
                'reported_monte_carlo':'1000 brute-force attempt stopped due cost; optimization required',
                'reported_pending':'falsification-lab retest after NameError correction',
                'authority':'later continuity input, still subordinate to repository evidence',
            },
        },
        'conflicts_resolved':[
            'repository HEAD and current tests supersede both historical test counts',
            'commit 2edb996 already resolved the pending falsification-power test before this consolidation',
            'no Python writer was active when this mission resumed, so the earlier active-process warning was stale',
            'freeze authority remains the immutable v2 artifact, never a derived registry',
        ],
        'canonical_data':{
            'file':data.name,
            'cutoff':3053,
            'sha256':data_sha,
        },
        'prospective_freeze':{
            'file':freeze.name,
            'target_contest':3054,
            'top6':[10,11,27,30,35,38],
            'sha256':freeze_sha,
            'immutable':freeze_sha==FREEZE_EXPECTED_SHA256,
        },
        'agent_skill_integration':{
            'artifact':'SMART_AGENT_SKILL_ORCHESTRATION.json',
            'status':orchestration['integration_status'],
            'unique_capabilities_total':orchestration['inventory']['unique_capabilities_total'],
            'external_code_auto_execute':orchestration['policy']['external_code_auto_execute'],
            'predictive_authority':'NONE_DIRECT',
        },
        'powered_falsification':{
            'artifact':'SMART_FALSIFICATION_REPORT_POWERED.json',
            'replications':powered['replications'],
            'family_size':powered['multiplicity']['family_size'],
            'minimum_replications_for_resolution':powered['multiplicity']['minimum_replications_for_resolution'],
            'resolution_sufficient':powered['multiplicity']['resolution_sufficient'],
            'holm_rejections':powered['multiplicity']['rejected_comparisons'],
            'all_adversarial_expected_directions_detected':powered['adversarial_sensitivity']['all_expected_directions_detected'],
            'predictive_weight_authorized':powered['predictive_weight_authorized'],
            'scientific_conclusion':powered['scientific_conclusion'],
        },
        'monte_carlo_optimization':{
            'baseline_5_replications_seconds':14.122,
            'optimized_stage1_5_replications_seconds':6.308,
            'optimized_stage2_5_replications_seconds':4.367,
            'optimized_20_replications_seconds':12.371,
            'baseline_to_stage2_speedup':round(14.122/4.367,3),
            'baseline_to_stage2_reduction_percent':round((1-4.367/14.122)*100,2),
            'invariants':'U4 exact marginals; U5 prepared-fit equivalence; fast-stat projection equivalence; deterministic seeds covered by tests',
        },
        'monte_carlo_convergence':{
            'artifact':'SMART_MONTE_CARLO_CONVERGENCE_1000.json',
            'schema':convergence.get('schema'),
            'stability_summary':convergence.get('stability_summary'),
            'predictive_weight_authorized':convergence.get('predictive_weight_authorized'),
        },
        'null_atlas_1000':None if atlas1000 is None else {
            'atlas':'SMART_RANDOMNESS_ATLAS_1000.json',
            'manifest':'SMART_NULL_UNIVERSE_MANIFEST_1000.json',
            'replications':atlas1000.get('replications'),
            'cutoff':atlas1000.get('contest_max'),
            'atlas_sha256':sha(atlas1000_path),
            'manifest_sha256':sha(manifest1000_path),
        },
        'checks':checks,
        'consolidation_status':'PASS' if all(checks.values()) else 'INCOMPLETE',
        'mission_state':mission['status'],
        'terminal_6of6_proven':mission['terminal_6of6_proven'],
    }


def write(root: Path) -> dict[str,Any]:
    doc=build(root)
    out=root/'SMART_CHAT_CONSOLIDATION_20260904.json'
    out.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return doc


if __name__=='__main__':
    import sys
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
    doc=write(root)
    print(json.dumps({'consolidation_status':doc['consolidation_status'],'head_short':doc['head_short'],'atlas_1000_complete':doc['checks']['atlas_1000_complete'],'mission_state':doc['mission_state']},ensure_ascii=False))
