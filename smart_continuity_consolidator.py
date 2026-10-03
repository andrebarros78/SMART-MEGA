from __future__ import annotations

from smart_mission_status import load_mission_status

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import smart_agent_skill_functional_gate as agent_skill_gate
import smart_agent_skill_orchestration as agent_skill_orchestration
import smart_total_integration_gate as total_integration_gate
from smart_agent_runtime import sha256_json
from smart_current_epoch_contract import resolve as resolve_current_epoch

LEGACY_FREEZE_EXPECTED_SHA256="503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"
LEGACY_DATA_EXPECTED_SHA256="287afcdb89ba822c6e4acc848a80583a17653d646581d2a582cad3abc1947c60"
# Compatibility aliases: immutable hashes; authority is derived from active epoch.
FREEZE_EXPECTED_SHA256=LEGACY_FREEZE_EXPECTED_SHA256
DATA_EXPECTED_SHA256=LEGACY_DATA_EXPECTED_SHA256
WMCP_PROOF_SCHEMA="SMART_WMCP_EXECUTION_PROOF_V2"
WMCP_PROOF_MAX_AGE_SECONDS=300.0
WMCP_SUPERVISOR_MAX_HEARTBEAT_AGE_SECONDS=15.0
WMCP_WORKER_MAX_HEARTBEAT_AGE_SECONDS=20.0
WMCP_E2E_STDOUT="SMART_MEGA_WORKER_E2E_PROVEN_20260905_1704"
CANONICAL_WMCP_ROOT_TEXT=r"C:\New Projet\WMCP 3.1"
CANONICAL_WMCP_BROKER_ROOT_TEXT=r"C:\ProgramData\WMCP31\PrivilegedBroker"
CANONICAL_WMCP_ROOT=Path(CANONICAL_WMCP_ROOT_TEXT).resolve()
CANONICAL_WMCP_BROKER_ROOT=Path(CANONICAL_WMCP_BROKER_ROOT_TEXT).resolve()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str,Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _git_dir(root: Path) -> Path:
    marker=(Path(root).resolve()/'.git')
    if marker.is_dir():
        return marker
    if marker.is_file():
        raw=marker.read_text(encoding='utf-8-sig').strip()
        if not raw.lower().startswith('gitdir:'):
            raise RuntimeError('invalid .git indirection')
        target=Path(raw.split(':',1)[1].strip())
        if not target.is_absolute():
            target=(marker.parent/target).resolve()
        return target
    raise RuntimeError('git metadata unavailable')


def _git_ref_oid(git_dir: Path, ref: str) -> str:
    direct=git_dir/Path(ref)
    if direct.is_file():
        oid=direct.read_text(encoding='ascii',errors='strict').strip()
        if len(oid)>=40 and all(ch in '0123456789abcdefABCDEF' for ch in oid):
            return oid.lower()
    packed=git_dir/'packed-refs'
    if packed.is_file():
        for line in packed.read_text(encoding='utf-8',errors='replace').splitlines():
            if not line or line.startswith(('#','^')):
                continue
            parts=line.split(' ',1)
            if len(parts)==2 and parts[1].strip()==ref:
                oid=parts[0].strip()
                if len(oid)>=40 and all(ch in '0123456789abcdefABCDEF' for ch in oid):
                    return oid.lower()
    raise RuntimeError(f'git ref unavailable: {ref}')


def _git_head(root: Path) -> tuple[str | None,str]:
    git_dir=_git_dir(root)
    raw=(git_dir/'HEAD').read_text(encoding='utf-8-sig').strip()
    if raw.startswith('ref:'):
        ref=raw.split(':',1)[1].strip()
        return ref,_git_ref_oid(git_dir,ref)
    if len(raw)>=40 and all(ch in '0123456789abcdefABCDEF' for ch in raw):
        return None,raw.lower()
    raise RuntimeError('invalid git HEAD')


def git(root: Path,*args: str) -> str:
    ref,oid=_git_head(root)
    if args==('branch','--show-current'):
        return ref[len('refs/heads/'):] if ref and ref.startswith('refs/heads/') else ''
    if args==('rev-parse','HEAD'):
        return oid
    if args==('rev-parse','--short','HEAD'):
        return oid[:7]
    raise ValueError(f'unsupported portable git query: {args!r}')


def _source_identity(root: Path) -> dict[str, Any]:
    try:
        branch=git(root,'branch','--show-current')
        head=git(root,'rev-parse','HEAD')
        short=git(root,'rev-parse','--short','HEAD')
        return {
            'source':'GIT',
            'branch':branch,
            'head':head,
            'head_short':short,
            'release':None,
            'release_proof_sha256':None,
            'base_commit':None,
        }
    except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError):
        proof_specs=(
            ('R3_SCOPE_SEAL_SOURCE_PROOF.json','SMART-MEGA-v6.3.1-PORTABLE-SCOPE-SEAL-R3'),
            ('R2_ENGINEERING_PROOF.json','SMART-MEGA-v6.3.1-PORTABLE-RESTORE-R2'),
        )
        proof_path=None
        expected_release=None
        for filename, release_id in proof_specs:
            candidate=root/'release_evidence'/filename
            if candidate.is_file():
                proof_path=candidate
                expected_release=release_id
                break
        if proof_path is None:
            raise RuntimeError('source identity unavailable: neither Git metadata nor portable release proof is present')
        proof=read_json(proof_path)
        unsigned=dict(proof)
        declared=unsigned.pop('sha256',None)
        if declared!=sha256_json(unsigned):
            raise ValueError('portable release proof self-hash invalid')
        release=proof.get('release')
        base_commit=proof.get('base_commit')
        if release!=expected_release:
            raise ValueError('portable release proof release identifier invalid')
        if not isinstance(base_commit,str) or len(base_commit)!=40:
            raise ValueError('portable release proof base commit invalid')
        return {
            'source':'PORTABLE_RELEASE_PROOF',
            'branch':None,
            'head':None,
            'head_short':None,
            'release':release,
            'release_proof_sha256':sha(proof_path),
            'base_commit':base_commit,
        }

def _total_integration_valid(doc: dict[str,Any]) -> bool:
    unsigned=dict(doc)
    declared=unsigned.pop('sha256',None)
    gates=doc.get('gates',{})
    return (
        declared==sha256_json(unsigned)
        and doc.get('status')=='PASS'
        and doc.get('health')=='HEALTHY'
        and doc.get('schema')=='SMART_TOTAL_INTEGRATION_GATE_V2'
        and len(gates)==9
        and all(isinstance(g,dict) and g and all(v is True for v in g.values()) for g in gates.values())
    )


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value,str) or not value:
        return None
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(value: object, *, now: datetime | None=None) -> float | None:
    parsed=_parse_timestamp(value)
    if parsed is None:
        return None
    current=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return (current-parsed).total_seconds()


def _find_project(doc: dict[str,Any], project_id: str) -> dict[str,Any]:
    rows=doc.get('projects',[])
    if isinstance(rows,dict):
        rows=list(rows.values())
    if not isinstance(rows,list):
        return {}
    for row in rows:
        if isinstance(row,dict) and row.get('project_id')==project_id:
            return row
    return {}


def _powershell_json(script: str) -> dict[str,Any]:
    raw=subprocess.check_output(
        ['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=20,
    ).strip()
    return json.loads(raw) if raw else {}


def refresh_wmcp_execution_proof(
    root: Path,
    *,
    wmcp_root: Path | None=None,
    broker_root: Path | None=None,
) -> dict[str,Any]:
    wmcp=(wmcp_root or CANONICAL_WMCP_ROOT).resolve()
    broker=(broker_root or CANONICAL_WMCP_BROKER_ROOT).resolve()
    project_id='smart-mega'
    state_root=wmcp/'.orquestrador'/'projects'/project_id
    main_manifest_path=wmcp/'config'/'projects.json'
    broker_manifest_path=broker/'config'/'projects.json'
    heartbeat_path=state_root/'heartbeat.json'
    worker_state_path=state_root/'workers'/'worker-01'/'state.json'
    proof_path=root/'SMART_WMCP_EXECUTION_PROOF_20260905.json'

    main_manifest=read_json(main_manifest_path)
    broker_manifest=read_json(broker_manifest_path)
    main_project=_find_project(main_manifest,project_id)
    broker_project=_find_project(broker_manifest,project_id)
    heartbeat=read_json(heartbeat_path)
    worker_state=read_json(worker_state_path) if worker_state_path.exists() else {}

    prior=read_json(proof_path) if proof_path.exists() else {}
    task_id=prior.get('e2e',{}).get('task_id')
    if not isinstance(task_id,str) or not task_id:
        candidates=[]
        for result_path in (state_root/'tasks').glob('*/result.json'):
            try:
                candidate=read_json(result_path)
            except (OSError,ValueError,json.JSONDecodeError):
                continue
            if (
                candidate.get('state')=='completed'
                and candidate.get('exit_code')==0
                and str(candidate.get('stdout','')).strip()==WMCP_E2E_STDOUT
            ):
                candidates.append((str(candidate.get('completed_at','')),result_path.parent.name))
        if candidates:
            task_id=sorted(candidates)[-1][1]
    task_root=state_root/'tasks'/str(task_id or '')
    task_state=read_json(task_root/'state.json') if task_id and (task_root/'state.json').exists() else {}
    result=read_json(task_root/'result.json') if task_id and (task_root/'result.json').exists() else {}

    broker_runtime=_powershell_json(r"""
$ErrorActionPreference='Stop'
$task=Get-ScheduledTask -TaskName 'Windows-MCP-Process-Broker'
$procs=Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match 'windows_mcp\.multiproject\.process_broker' -and
  $_.CommandLine -match 'PrivilegedBroker'
}
$rows=@()
foreach($p in $procs){
  $ownerSid=Invoke-CimMethod -InputObject $p -MethodName GetOwnerSid
  $rows += [pscustomobject]@{
    pid=[int]$p.ProcessId
    parent_pid=[int]$p.ParentProcessId
    sid=[string]$ownerSid.Sid
  }
}
[pscustomobject]@{task_state=[string]$task.State;processes=$rows} | ConvertTo-Json -Depth 4 -Compress
""")
    processes=broker_runtime.get('processes',[])
    if isinstance(processes,dict):
        processes=[processes]
    if not isinstance(processes,list):
        processes=[]

    now=datetime.now(timezone.utc)
    heartbeat_age=_age_seconds(heartbeat.get('time'),now=now)
    runnable=heartbeat.get('runnable_priority',{})
    runnable_total=sum(int(v or 0) for v in runnable.values()) if isinstance(runnable,dict) else -1
    active_workers=int(heartbeat.get('active_workers',0) or 0)
    capacity_limited=bool(heartbeat.get('capacity_limited'))
    drained=(
        heartbeat.get('state')=='ready'
        and active_workers==0
        and runnable_total==0
        and not capacity_limited
    )
    worker_age=_age_seconds(worker_state.get('heartbeat_at'),now=now)
    live_worker=(
        active_workers>0
        and worker_state.get('state') in {'starting','idle','assigned','running','waiting','validating'}
        and worker_state.get('runtime_probe_ok') is True
        and worker_age is not None
        and 0.0 <= worker_age <= WMCP_WORKER_MAX_HEARTBEAT_AGE_SECONDS
    )
    broker_bytes=broker_manifest_path.read_bytes()
    broker_no_bom=not (
        broker_bytes.startswith(b'\xef\xbb\xbf')
        or broker_bytes.startswith(b'\xff\xfe')
        or broker_bytes.startswith(b'\xfe\xff')
    )
    broker_sids=[str(row.get('sid','')) for row in processes if isinstance(row,dict)]
    result_path=task_root/'result.json'
    result_sha=sha(result_path) if result_path.exists() else None
    checks={
        'canonical_wmcp_root':wmcp==CANONICAL_WMCP_ROOT,
        'canonical_broker_root':broker==CANONICAL_WMCP_BROKER_ROOT,
        'main_manifest_windows_account':main_project.get('isolation_mode')=='windows-account' and main_project.get('windows_identity')=='svc-wmcp-smart-mega',
        'broker_manifest_windows_account':broker_project.get('isolation_mode')=='windows-account' and broker_project.get('windows_identity')=='svc-wmcp-smart-mega',
        'broker_manifest_utf8_no_bom':broker_no_bom,
        'broker_task_running':str(broker_runtime.get('task_state','')).casefold()=='running',
        'broker_process_present':len(processes)>=1,
        'broker_processes_system':bool(broker_sids) and all(sid=='S-1-5-18' for sid in broker_sids),
        'supervisor_heartbeat_fresh':heartbeat_age is not None and 0.0 <= heartbeat_age <= WMCP_SUPERVISOR_MAX_HEARTBEAT_AGE_SECONDS,
        'supervisor_ready':heartbeat.get('state')=='ready',
        'supervisor_execution_enabled':heartbeat.get('execution_enabled') is True,
        'supervisor_isolation_windows_account':heartbeat.get('isolation_mode')=='windows-account',
        'runtime_capacity_not_limited':capacity_limited is False,
        'worker_live_or_demand_drained':live_worker or drained,
        'command_completed':task_state.get('state')=='completed' and result.get('state')=='completed',
        'isolated_worker_executed':result.get('worker_id')=='worker-01' and result.get('project_id')==project_id,
        'exit_zero':task_state.get('exit_code')==0 and result.get('exit_code')==0,
        'stdout_exact':str(result.get('stdout','')).strip()==WMCP_E2E_STDOUT,
        'result_hash_present':isinstance(result_sha,str) and len(result_sha)==64,
        'fencing_token_valid':isinstance(result.get('fencing_token'),int) and int(result.get('fencing_token'))>0,
    }
    generated=now.isoformat()
    proof={
        'schema':WMCP_PROOF_SCHEMA,
        'generated_at_utc':generated,
        'project_id':project_id,
        'workspace':str(root),
        'live_runtime':{
            'observed_at_utc':generated,
            'wmcp_root':str(wmcp),
            'broker_root':str(broker),
            'supervisor_state':heartbeat.get('state'),
            'supervisor_pid':heartbeat.get('pid'),
            'supervisor_heartbeat_at':heartbeat.get('time'),
            'supervisor_heartbeat_age_seconds':None if heartbeat_age is None else round(heartbeat_age,3),
            'active_workers':active_workers,
            'capacity_limited':capacity_limited,
            'runnable_total':runnable_total,
            'worker_state':worker_state.get('state'),
            'worker_pid':worker_state.get('pid'),
            'worker_runtime_probe_ok':worker_state.get('runtime_probe_ok'),
            'worker_mode':'LIVE' if live_worker else ('DEMAND_DRAINED' if drained else 'INVALID'),
            'broker_task_state':broker_runtime.get('task_state'),
            'broker_process_count':len(processes),
            'broker_system':bool(broker_sids) and all(sid=='S-1-5-18' for sid in broker_sids),
            'main_manifest_sha256':sha(main_manifest_path),
            'broker_manifest_sha256':sha(broker_manifest_path),
            'heartbeat_sha256':sha(heartbeat_path),
            'worker_state_sha256':sha(worker_state_path) if worker_state_path.exists() else None,
        },
        'control_plane':{
            'isolation_mode':main_project.get('isolation_mode'),
            'windows_identity':main_project.get('windows_identity'),
            'broker_state':'ready' if checks['broker_task_running'] and checks['broker_process_present'] else 'invalid',
            'broker_system':checks['broker_processes_system'],
        },
        'e2e':{
            'task_id':task_id,
            'command_state':task_state.get('state'),
            'created_at':task_state.get('created_at'),
            'started_at':task_state.get('started_at'),
            'completed_at':task_state.get('completed_at'),
            'result_sha256':result_sha,
            'executor_node_id':task_state.get('executor_node_id'),
            'fencing_token':result.get('fencing_token'),
            'exit_code':result.get('exit_code'),
            'stdout':str(result.get('stdout','')).strip(),
            'stderr_empty':str(result.get('stderr',''))=='',
        },
        'checks':checks,
        'status':'PASS' if all(checks.values()) else 'FAIL',
        'secret_material_in_artifact':False,
    }
    proof['sha256']=sha256_json(proof)
    proof_path.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return proof


def _canonical_wmcp_live_binding_valid(doc: dict[str,Any], *, require_runtime_fresh: bool=True) -> bool:
    live=doc.get('live_runtime',{})
    e2e=doc.get('e2e',{})
    if not isinstance(live,dict) or not isinstance(e2e,dict):
        return False
    if live.get('wmcp_root')!=CANONICAL_WMCP_ROOT_TEXT or live.get('broker_root')!=CANONICAL_WMCP_BROKER_ROOT_TEXT:
        return False
    project_id='smart-mega'
    state_root=CANONICAL_WMCP_ROOT/'.orquestrador'/'projects'/project_id
    main_manifest_path=CANONICAL_WMCP_ROOT/'config'/'projects.json'
    broker_manifest_path=CANONICAL_WMCP_BROKER_ROOT/'config'/'projects.json'
    heartbeat_path=state_root/'heartbeat.json'
    task_id=e2e.get('task_id')
    if not isinstance(task_id,str) or not task_id:
        return False
    result_path=state_root/'tasks'/task_id/'result.json'
    try:
        if live.get('main_manifest_sha256')!=sha(main_manifest_path):
            return False
        if live.get('broker_manifest_sha256')!=sha(broker_manifest_path):
            return False
        if e2e.get('result_sha256')!=sha(result_path):
            return False
        if not require_runtime_fresh:
            return True
        heartbeat=read_json(heartbeat_path)
    except (OSError,ValueError,json.JSONDecodeError):
        return False
    age=_age_seconds(heartbeat.get('time'))
    runnable=heartbeat.get('runnable_priority',{})
    runnable_total=sum(int(v or 0) for v in runnable.values()) if isinstance(runnable,dict) else -1
    active_workers=int(heartbeat.get('active_workers',0) or 0)
    capacity_limited=bool(heartbeat.get('capacity_limited'))
    current_runtime_ok=(
        heartbeat.get('state')=='ready'
        and heartbeat.get('execution_enabled') is True
        and heartbeat.get('isolation_mode')=='windows-account'
        and capacity_limited is False
        and age is not None
        and 0.0 <= age <= WMCP_SUPERVISOR_MAX_HEARTBEAT_AGE_SECONDS
        and (active_workers>0 or runnable_total==0)
    )
    return current_runtime_ok


def _canonical_wmcp_artifact_binding_valid(doc: dict[str,Any]) -> bool:
    """Validate immutable/canonical WMCP bindings without consulting live runtime state."""
    live=doc.get('live_runtime',{})
    e2e=doc.get('e2e',{})
    if not isinstance(live,dict) or not isinstance(e2e,dict):
        return False
    if live.get('wmcp_root')!=CANONICAL_WMCP_ROOT_TEXT or live.get('broker_root')!=CANONICAL_WMCP_BROKER_ROOT_TEXT:
        return False
    if doc.get('project_id')!='smart-mega':
        return False
    task_id=e2e.get('task_id')
    if not isinstance(task_id,str) or not task_id:
        return False
    for value in (
        live.get('main_manifest_sha256'),
        live.get('broker_manifest_sha256'),
        e2e.get('result_sha256'),
    ):
        if not isinstance(value,str) or len(value)!=64:
            return False
        try:
            int(value,16)
        except ValueError:
            return False
    return True

def _wmcp_execution_valid(
    doc: dict[str,Any],
    *,
    require_fresh: bool=False,
    max_age_seconds: float=WMCP_PROOF_MAX_AGE_SECONDS,
) -> bool:
    unsigned=dict(doc)
    declared=unsigned.pop('sha256',None)
    live=doc.get('live_runtime',{})
    base_valid=(
        doc.get('schema')==WMCP_PROOF_SCHEMA
        and declared==sha256_json(unsigned)
        and doc.get('status')=='PASS'
        and doc.get('secret_material_in_artifact') is False
        and bool(doc.get('checks'))
        and all(v is True for v in doc.get('checks',{}).values())
        and isinstance(live,dict)
        and live.get('supervisor_state')=='ready'
        and live.get('capacity_limited') is False
        and live.get('worker_mode') in {'LIVE','DEMAND_DRAINED'}
        and live.get('broker_task_state')=='Running'
        and live.get('broker_system') is True
    )
    if not base_valid:
        return False
    if not _canonical_wmcp_artifact_binding_valid(doc):
        return False
    if not require_fresh:
        return True
    if not _canonical_wmcp_live_binding_valid(doc, require_runtime_fresh=True):
        return False
    age=_age_seconds(doc.get('generated_at_utc'))
    observed_age=_age_seconds(live.get('observed_at_utc'))
    return (
        age is not None
        and observed_age is not None
        and 0.0 <= age <= max_age_seconds
        and 0.0 <= observed_age <= max_age_seconds
        and _canonical_wmcp_live_binding_valid(doc, require_runtime_fresh=True)
    )


def build(root: Path, *, require_fresh_wmcp: bool=False) -> dict[str,Any]:
    root=Path(root).resolve()
    current=resolve_current_epoch(root)
    mission=load_mission_status(root/'SMART_MISSION_STATUS.json', root=root)
    orchestration=agent_skill_orchestration.build_orchestration(root)
    functional_integration=agent_skill_gate.evaluate(root)
    total_integration=read_json(root/'SMART_TOTAL_INTEGRATION_PROOF.json')
    wmcp_execution=read_json(root/'SMART_WMCP_EXECUTION_PROOF_20260905.json')
    powered=read_json(root/'SMART_FALSIFICATION_REPORT_POWERED.json')
    atlas1000_path=root/'SMART_RANDOMNESS_ATLAS_1000.json'
    atlas1000=read_json(atlas1000_path) if atlas1000_path.exists() else None
    manifest1000_path=root/'SMART_NULL_UNIVERSE_MANIFEST_1000.json'
    manifest1000=read_json(manifest1000_path) if manifest1000_path.exists() else None
    p1p2=read_json(root/'SMART_P1_P2_CARTOGRAPHY_PROOF.json')
    convergence=read_json(root/'SMART_MONTE_CARLO_CONVERGENCE_1000.json')
    adversarial_path=root/'SMART_ADVERSARIAL_CLAIM_AUDIT.json'
    adversarial=read_json(adversarial_path) if adversarial_path.exists() else {}
    legacy_freeze=root/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'
    legacy_data=root/'Mega-Sena_through_3053_v2.xlsx'
    legacy_freeze_sha=sha(legacy_freeze) if legacy_freeze.exists() else None
    legacy_data_sha=sha(legacy_data) if legacy_data.exists() else None
    current_data=root/current['data_file']
    current_freeze_ok=(
        current['status']=='RESET_READY' and not current['freeze_authority_present'] and current['freeze_sha256'] is None
    ) or (
        current['status']=='FROZEN' and current['freeze_authority_present'] and isinstance(current['freeze_sha256'],str) and len(current['freeze_sha256'])==64
    ) or (
        current['status']=='POST_RESULT_HOLD' and current.get('post_result_hold') is True
        and not current['freeze_authority_present'] and current['freeze_sha256'] is None
        and current.get('prepare_allowed') is False and current.get('current_engineering_generation_authority') is False
    )
    checks={
        'active_epoch_contract_valid': current['target_contest']==current['cutoff_contest']+1 and current['result_used'] is False,
        'canonical_data_bound_to_active_epoch': current_data.is_file() and sha(current_data)==current['data_sha256'],
        'current_freeze_state_consistent': current_freeze_ok,
        'carry_forward_freeze_hash_preserved': legacy_freeze_sha==LEGACY_FREEZE_EXPECTED_SHA256,
        'carry_forward_dataset_hash_preserved': legacy_data_sha==LEGACY_DATA_EXPECTED_SHA256,
        'agent_skill_structural_orchestration_pass': orchestration['integration_status']=='PASS' and orchestration.get('integration_scope')=='STRUCTURAL_ORCHESTRATION_ONLY',
        'agent_skill_functional_integration_pass': functional_integration.get('status')=='PASS' and all(functional_integration.get('checks',{}).values()),
        'total_integration_gate_pass': _total_integration_valid(total_integration),
        'wmcp_execution_proof_pass': _wmcp_execution_valid(wmcp_execution,require_fresh=require_fresh_wmcp),
        'role_executors_have_no_terminal_authority': all(not bool(agent.get('terminal_authority')) and not bool(agent.get('predictive_weight_authorized')) and not bool(agent.get('freeze_mutation_authorized')) for agent in orchestration.get('agents',{}).values()),
        'powered_falsification_resolution_sufficient': powered['multiplicity']['resolution_sufficient'] is True,
        'powered_falsification_no_predictive_weight': powered['predictive_weight_authorized'] is False,
        'powered_controls_detected': powered['adversarial_sensitivity']['all_expected_directions_detected'] is True,
        'adversarial_non_inert_pipeline_proof_pass': adversarial.get('status')=='PASS' and all(adversarial.get('checks',{}).values()),
        'mission_active_not_false_proven': mission['status']=='MISSION_ACTIVE' and mission['terminal_6of6_proven'] is False,
        'atlas_1000_complete': bool(atlas1000 and atlas1000.get('replications')==1000),
        'manifest_1000_complete': bool(manifest1000 and manifest1000.get('replications')==1000),
        'canonical_p1p2_promoted_to_1000': int(p1p2.get('replications',0))==1000 and p1p2.get('p2_atlas_sha256')==sha(root/'SMART_RANDOMNESS_ATLAS.json'),
        'convergence_audit_bound_to_1000': int(convergence.get('final_replications',0))==1000 and convergence.get('final_atlas_sha256')==sha(atlas1000_path),
    }
    source_identity=_source_identity(root)
    return {
        'schema':'SMART_CURRENT_CONTINUITY_V2',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'canonical continuity derived from the current lifecycle contract; post-result HOLD is non-generative and legacy freeze/data are historical evidence only',
        'workspace':str(root),
        'branch':source_identity['branch'],
        'head':source_identity['head'],
        'head_short':source_identity['head_short'],
        'source_identity':source_identity,
        'current_epoch':current,
        'canonical_data':{
            'file':current['data_file'],'cutoff':current['cutoff_contest'],'sha256':current['data_sha256'],'authority':('POST_RESULT_HOLD' if current['status']=='POST_RESULT_HOLD' else 'ACTIVE_EPOCH')
        },
        'prospective_freeze':{
            'status':current['status'],'file':current['freeze_file'],'target_contest':current['target_contest'],
            'cutoff_contest':current['cutoff_contest'],'top6':current['top6'],'sha256':current['freeze_sha256'],
            'authority':('NONE_POST_RESULT_HOLD' if current['status']=='POST_RESULT_HOLD' else ('HISTORICAL_FROZEN_POST_ADJUDICATION' if current.get('post_adjudication') is True else ('CARRY_FORWARD_PROSPECTIVE_AUTHORITY' if current.get('authority_mode')=='CARRY_FORWARD_UNRESOLVED_PROSPECTIVE' else ('ACTIVE_CURRENT_ENGINEERING_EPOCH' if current['freeze_authority_present'] else 'NONE_RESET_READY')))),
            'result_used':current['result_used'],
        },
        'legacy_pre_activation':{
            'freeze_file':legacy_freeze.name,'freeze_sha256':legacy_freeze_sha,'freeze_expected_sha256':LEGACY_FREEZE_EXPECTED_SHA256,
            'data_file':legacy_data.name,'data_sha256':legacy_data_sha,'data_expected_sha256':LEGACY_DATA_EXPECTED_SHA256,
            'authority':'PRE_FULL_ACTIVATION_HISTORICAL_ONLY',
            'scientific_attempt_preserved': bool(current.get('freeze_sha256')==legacy_freeze_sha and current.get('scientific_adjudication_authority')),
        },
        'agent_skill_integration':{
            'artifact':'SMART_AGENT_SKILL_ORCHESTRATION.json','structural_status':orchestration['integration_status'],
            'structural_scope':orchestration.get('integration_scope'),'functional_status':functional_integration.get('status'),
            'functional_proof_sha256':functional_integration.get('sha256'),'unique_capabilities_total':orchestration['inventory']['unique_capabilities_total'],
            'role_executor_count':len(orchestration.get('agents',{})),
            'claim_boundary':'deterministic role executors and methodology aliases; not autonomous LLM agents or direct third-party skill execution',
            'external_code_auto_execute':orchestration['policy']['external_code_auto_execute'],'predictive_authority':'NONE_DIRECT',
        },
        'wmcp_execution':{
            'artifact':'SMART_WMCP_EXECUTION_PROOF_20260905.json','status':wmcp_execution.get('status'),'sha256':wmcp_execution.get('sha256'),
            'command_state':wmcp_execution.get('e2e',{}).get('command_state'),'exit_code':wmcp_execution.get('e2e',{}).get('exit_code'),
            'proof_schema':wmcp_execution.get('schema'),'generated_at_utc':wmcp_execution.get('generated_at_utc'),
            'live_supervisor_state':wmcp_execution.get('live_runtime',{}).get('supervisor_state'),'live_worker_mode':wmcp_execution.get('live_runtime',{}).get('worker_mode'),
        },
        'total_integration':{
            'artifact':'SMART_TOTAL_INTEGRATION_PROOF.json','status':total_integration.get('status'),'health':total_integration.get('health'),
            'schema':total_integration.get('schema'),'sha256':total_integration.get('sha256'),'gate_count':len(total_integration.get('gates',{})),
        },
        'adversarial_claim_audit':{
            'artifact':'SMART_ADVERSARIAL_CLAIM_AUDIT.json','status':adversarial.get('status'),'sha256':adversarial.get('sha256'),
            'anchor_top6':adversarial.get('anchor_top6'),'policy_top6':adversarial.get('policy_top6'),
            'heaviest_signal':adversarial.get('heaviest_signal'),'heaviest_weight_delta':adversarial.get('heaviest_weight_delta'),
        },
        'powered_falsification':{
            'artifact':'SMART_FALSIFICATION_REPORT_POWERED.json','replications':powered['replications'],'family_size':powered['multiplicity']['family_size'],
            'minimum_replications_for_resolution':powered['multiplicity']['minimum_replications_for_resolution'],'resolution_sufficient':powered['multiplicity']['resolution_sufficient'],
            'holm_rejections':powered['multiplicity']['rejected_comparisons'],'all_adversarial_expected_directions_detected':powered['adversarial_sensitivity']['all_expected_directions_detected'],
            'predictive_weight_authorized':powered['predictive_weight_authorized'],'scientific_conclusion':powered['scientific_conclusion'],
        },
        'monte_carlo_convergence':{
            'artifact':'SMART_MONTE_CARLO_CONVERGENCE_1000.json','schema':convergence.get('schema'),'stability_summary':convergence.get('stability_summary'),
            'predictive_weight_authorized':convergence.get('predictive_weight_authorized'),
        },
        'null_atlas_1000':None if atlas1000 is None else {
            'atlas':'SMART_RANDOMNESS_ATLAS_1000.json','manifest':'SMART_NULL_UNIVERSE_MANIFEST_1000.json','replications':atlas1000.get('replications'),
            'cutoff':atlas1000.get('contest_max'),'atlas_sha256':sha(atlas1000_path),'manifest_sha256':sha(manifest1000_path),
        },
        'checks':checks,'consolidation_status':'PASS' if all(checks.values()) else 'INCOMPLETE',
        'mission_state':mission['status'],'terminal_6of6_proven':mission['terminal_6of6_proven'],
    }

def write(root: Path, *, refresh_total_gate: bool=True, refresh_wmcp_probe: bool=True) -> dict[str,Any]:
    if refresh_total_gate:
        total_integration_gate.write(root)
    if refresh_wmcp_probe:
        refresh_wmcp_execution_proof(root)
    doc=build(root,require_fresh_wmcp=refresh_wmcp_probe)
    out=root/'SMART_CHAT_CONSOLIDATION_20260904.json'
    out.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return doc


if __name__=='__main__':
    import sys
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
    doc=write(root)
    print(json.dumps({'consolidation_status':doc['consolidation_status'],'head_short':doc['head_short'],'atlas_1000_complete':doc['checks']['atlas_1000_complete'],'mission_state':doc['mission_state']},ensure_ascii=False))

