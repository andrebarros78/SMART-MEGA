from __future__ import annotations
import hashlib,json,os,shutil
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

FREEZE_SHA='503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816'
DATA_SHA='287afcdb89ba822c6e4acc848a80583a17653d646581d2a582cad3abc1947c60'
REPS=1000

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def read(path:Path)->dict[str,Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))

def promote(root:Path)->dict[str,Any]:
    data=root/'Mega-Sena_through_3053_v2.xlsx'
    freeze=root/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'
    src_m=root/'SMART_NULL_UNIVERSE_MANIFEST_1000.json'
    src_a=root/'SMART_RANDOMNESS_ATLAS_1000.json'
    conv_p=root/'SMART_MONTE_CARLO_CONVERGENCE_1000.json'
    for p in (data,freeze,src_m,src_a,conv_p):
        if not p.exists(): raise FileNotFoundError(p.name)
    if sha(data)!=DATA_SHA: raise RuntimeError('dataset hash mismatch')
    if sha(freeze)!=FREEZE_SHA: raise RuntimeError('freeze 3054 hash mismatch')
    m=read(src_m); a=read(src_a); conv=read(conv_p)
    checks={
      'manifest_replications_1000':int(m.get('replications',0))==REPS,
      'atlas_replications_1000':int(a.get('replications',0))==REPS,
      'cutoff_3053':int(a.get('contest_max',0))==3053 and int(m.get('cutoff_contest',0))==3053,
      'manifest_data_bound':m.get('data_sha256')==DATA_SHA,
      'atlas_data_bound':a.get('data_sha256')==DATA_SHA,
      'convergence_final_1000':int(conv.get('final_replications',0))==REPS,
      'convergence_atlas_bound':conv.get('final_atlas_sha256')==sha(src_a),
      'freeze_immutable':sha(freeze)==FREEZE_SHA,
    }
    if not all(checks.values()): raise RuntimeError({'promotion_checks':checks})
    dst_m=root/'SMART_NULL_UNIVERSE_MANIFEST.json'; dst_a=root/'SMART_RANDOMNESS_ATLAS.json'
    tmp_m=root/'SMART_NULL_UNIVERSE_MANIFEST.json.promote.tmp'; tmp_a=root/'SMART_RANDOMNESS_ATLAS.json.promote.tmp'
    shutil.copyfile(src_m,tmp_m); shutil.copyfile(src_a,tmp_a)
    os.replace(tmp_m,dst_m); os.replace(tmp_a,dst_a)
    proof={
      'schema':'SMART_P1_P2_CARTOGRAPHY_PROOF_V3',
      'created_at_utc':datetime.now(timezone.utc).isoformat(),
      'cutoff_contest':3053,
      'data_file':data.name,'data_sha256':sha(data),'data_quality':'PASS',
      'p1_null_universes':['U0','U1','U2','U3','U4','U5','U6'],
      'p1_manifest_sha256':sha(dst_m),'p2_atlas_sha256':sha(dst_a),
      'replications':REPS,'seed':int(a.get('seed',20260904)),
      'convergence_artifact':conv_p.name,'convergence_sha256':sha(conv_p),
      'convergence_summary':conv.get('stability_summary'),
      'freeze_3054_sha256':sha(freeze),'freeze_3054_modified':False,
      'scientific_status':'DIAGNOSTIC_ONLY_NO_PREDICTIVE_ADVANTAGE_CLAIM',
      'engineering_status':'P1_P2_1000_REPLICATION_CANONICAL_PROMOTED_AFTER_CONVERGENCE_AUDIT',
      'predictive_weight_authorized':False,'terminal_6of6_proven':False,
      'integrity_assertions':{**checks,
         'canonical_manifest_matches_1000_source':sha(dst_m)==sha(src_m),
         'canonical_atlas_matches_1000_source':sha(dst_a)==sha(src_a),
      },
    }
    (root/'SMART_P1_P2_CARTOGRAPHY_PROOF.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return proof

if __name__=='__main__':
    import sys
    r=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
    p=promote(r)
    print(json.dumps({'schema':p['schema'],'replications':p['replications'],'engineering_status':p['engineering_status'],'freeze_unchanged':p['integrity_assertions']['freeze_immutable']}))
