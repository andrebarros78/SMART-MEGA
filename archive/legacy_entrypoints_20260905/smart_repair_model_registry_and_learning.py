from __future__ import annotations
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()

def write(p,o): Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

freeze_path=Path('SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json')
freeze=json.loads(freeze_path.read_text(encoding='utf-8')); fh=sha(freeze_path)
champ=[int(x) for x in freeze['champion']['top6']]
chall=[int(x) for x in freeze['challenger']['top6']]
registry={'schema':'SMART_MODEL_REGISTRY_V2','cutoff_contest':3053,'source_of_truth':'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json','source_sha256':fh,'models':[
 {'id':'champion_3054','role':'FROZEN_CHAMPION','artifact':freeze_path.name,'sha256':fh,'top6':champ},
 {'id':'governed_challenger_3054','role':'FROZEN_CHALLENGER','artifact':freeze_path.name,'sha256':fh,'top6':chall}],
 'promotion_policy':'prospective evidence only; no retroactive selection','integrity_rule':'registry Top-6 must equal the referenced freeze content'}
write('SMART_MODEL_REGISTRY.json',registry)

hist=json.loads(Path('SMART_FRONTIER_HISTORICAL_3053.json').read_text(encoding='utf-8'))
decisions={}
for cid,row in hist['summaries'].items():
    ho=row['splits']['holdout']
    decisions[cid]={
      'family':row['family'],'historical_diagnostic_pass':bool(row['historical_diagnostic_pass']),
      'holdout_n':int(ho['n']),'holdout_mean_delta_hits_vs_champion':float(ho['mean_delta_hits_vs_champion']),
      'holdout_mean_brier_delta_vs_uniform':float(ho['mean_brier_delta_vs_uniform']),
      'holm_adjusted_p':float(row['holm_adjusted_p']),
      'material_weight':0.0,
      'decision':'REJECT_FOR_PREDICTIVE_PROMOTION_ON_CURRENT_HISTORICAL_EVIDENCE'}
learning={
 'schema':'SMART_FRONTIER_LEARNING_DECISION_V1','created_brasilia':datetime.now(timezone(timedelta(hours=-3))).isoformat(),
 'cutoff_contest':3053,'source_artifact':'SMART_FRONTIER_HISTORICAL_3053.json','source_sha256':sha('SMART_FRONTIER_HISTORICAL_3053.json'),
 'evaluated_contests':int(hist['evaluated_contests']),'partitions':hist['partitions'],'multiplicity':hist['multiple_testing'],
 'decisions':decisions,'global_decision':'NO_FRONTIER_CANDIDATE_PROMOTED','operational_effect':'ALL_MATERIAL_WEIGHTS_REMAIN_ZERO',
 'freeze_3054_policy':'existing shadow freeze remains immutable and diagnostic; no production influence',
 'learning':'negative holdout evidence is incorporated by neutralizing promotion authority instead of forcing diversity or preserving candidates by inertia'}
write('SMART_FRONTIER_LEARNING_DECISION.json',learning)
print(json.dumps({'model_registry_rebound':True,'freeze_sha256':fh,'champion':champ,'challenger':chall,'frontier_rejected':len(decisions)}))
