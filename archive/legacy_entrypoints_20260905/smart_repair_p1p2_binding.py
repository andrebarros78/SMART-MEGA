from __future__ import annotations
import hashlib, json, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import smart_randomness_cartography as rc

DATA=Path('Mega-Sena_through_3053_v2.xlsx')
M=Path('SMART_NULL_UNIVERSE_MANIFEST.json')
A=Path('SMART_RANDOMNESS_ATLAS.json')
TM=Path('SMART_NULL_UNIVERSE_MANIFEST.json.tmp')
TA=Path('SMART_RANDOMNESS_ATLAS.json.tmp')
FREEZE=Path('SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json')
PROOF=Path('SMART_P1_P2_CARTOGRAPHY_PROOF.json')
SEED=20260904; REPS=rc.DEFAULT_REPLICATIONS

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()

freeze_before=sha(FREEZE)
manifest,atlas=rc.write_program_artifacts(DATA,TM,TA,REPS,SEED,3053)
assert manifest['replications']==REPS and atlas['replications']==REPS
assert manifest['data_sha256']==atlas['data_sha256']==sha(DATA)
assert freeze_before==sha(FREEZE)
os.replace(TM,M); os.replace(TA,A)
obj={
 'schema':'SMART_P1_P2_CARTOGRAPHY_PROOF_V2',
 'created_brasilia':datetime.now(timezone(timedelta(hours=-3))).isoformat(),
 'cutoff_contest':3053,'data_file':DATA.name,'data_sha256':sha(DATA),'data_quality':'PASS',
 'p1_null_universes':['U0','U1','U2','U3','U4','U5','U6'],
 'p1_manifest_sha256':sha(M),'p2_atlas_sha256':sha(A),'replications':REPS,'seed':SEED,
 'freeze_3054_sha256':freeze_before,'freeze_3054_modified':False,
 'scientific_status':'DIAGNOSTIC_ONLY_NO_PREDICTIVE_ADVANTAGE_CLAIM',
 'engineering_status':'P1_P2_ARTIFACT_BINDING_REPAIRED',
 'integrity_assertions':{'manifest_replications_match':True,'atlas_replications_match':True,'manifest_atlas_data_hash_match':True,'freeze_unchanged':True}
}
PROOF.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'manifest_sha':obj['p1_manifest_sha256'],'atlas_sha':obj['p2_atlas_sha256'],'replications':REPS,'freeze_unchanged':True}))
