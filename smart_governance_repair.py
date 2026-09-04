from __future__ import annotations
import json, hashlib, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT=Path('.')
BRT=timezone(timedelta(hours=-3))

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def write_json(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding='utf-8')

old=[]
for name in ('SMART_MISSION_PROVEN_6OF6.json','SMART_MISSION_PROVEN_FINAL_RETEST.json'):
    if Path(name).exists(): old.append({'file':name,'sha256':sha(name),'authority':'HISTORICAL_ENGINEERING_ONLY'})
status={
 'schema':'SMART_MISSION_STATUS_V2',
 'created_brasilia':datetime.now(BRT).isoformat(),
 'status':'MISSION_ACTIVE',
 'terminal_6of6_proven':False,
 'engineering_governance_status':'PROVEN',
 'scientific_predictive_status':'UNPROVEN',
 'prospective_advantage_status':'INSUFFICIENT_EVIDENCE',
 'supersedes_terminal_authority_of':old,
 'terminal_rule':'MISSION_PROVEN only after one unique Top-6 frozen before official result achieves exact 6/6 with causal lineage, immutable hashes, all attempts counted, and independent audit PASS',
 'anti_false_proof':{'historical_backtest_not_terminal_proof':True,'engineering_pass_not_terminal_6of6':True,'retroactive_selection_prohibited':True}
}
write_json('SMART_MISSION_STATUS.json',status)

reg={
 'schema':'SMART_HYPOTHESIS_REGISTRY_V2','cutoff_contest':3053,
 'rules':{'preregister_before_test':True,'future_leakage_prohibited':True,'multiplicity_control_required':True,'historical_discovery_not_proof':True,'predictive_weight_requires_oos_and_prospective_evidence':True},
 'hypotheses':[
  {'id':'H_NULL_IID','family':'reference','claim':'draws are compatible with uniform 6-of-60 without replacement','primary_null':'U0','status':'ACTIVE_NULL_REFERENCE'},
  {'id':'H_MEMORY_001','family':'temporal_memory','claim':'lagged inclusion dependence exceeds appropriate temporal nulls','metric':'lag1_binary_mutual_information_mean_bits','nulls':['U0','U1','U3','U4'],'status':'REGISTERED_DIAGNOSTIC','promotion_authority':False},
  {'id':'H_GRAPH_001','family':'cooccurrence_network','claim':'pair-network organization exceeds fixed-marginal and label-permutation nulls','metric':'network_density_and_clustering','nulls':['U0','U2','U4'],'status':'REGISTERED_DIAGNOSTIC','promotion_authority':False},
  {'id':'H_REGIME_001','family':'regime_change','claim':'causal feature stream contains stable change points beyond null expectations','metric':'penalized_change_point_count','nulls':['U0','U1','U3','U5'],'status':'REGISTERED_DIAGNOSTIC','promotion_authority':False},
  {'id':'H_HAZARD_001','family':'recurrence_hazard','claim':'waiting-time hazard adds causal OOS utility beyond frequency/recency baseline','nulls':['U0','U4'],'status':'SHADOW_ONLY','promotion_authority':False},
  {'id':'H_MARKOV_001','family':'conditional_transition','claim':'transition structure adds causal OOS utility beyond baseline','nulls':['U0','U1','U4','U5'],'status':'SHADOW_ONLY','promotion_authority':False},
  {'id':'H_PROSPECTIVE_ADVANTAGE','family':'operational','claim':'frozen causal Top-6/model beats declared baselines prospectively','status':'UNPROVEN','promotion_authority':False},
  {'id':'H_TERMINAL_6OF6','family':'terminal','claim':'a frozen pre-result Top-6 achieves exact 6/6 in an official contest','status':'UNPROVEN','promotion_authority':False}
 ],
 'multiplicity_policy':{'familywise_primary':'holm','exploratory_secondary':'benjamini_hochberg','no_single_p_value_promotion':True}
}
write_json('SMART_HYPOTHESIS_REGISTRY.json',reg)

cont='''# SMART-MEGA â€” CONTINUIDADE CANÃ”NICA\n\nCutoff cientÃ­fico: 3053. Freeze prospectivo ativo: concurso 3054.\n\nAutoridade terminal: `SMART_MISSION_STATUS.json`. Artefatos histÃ³ricos com nome `MISSION_PROVEN` sÃ£o preservados apenas como evidÃªncia de engenharia/governanÃ§a e nÃ£o possuem autoridade para declarar o 6/6 terminal.\n\nP1/P2: implementados, sujeitos a prova criptogrÃ¡fica regenerada e vinculada aos artefatos canÃ´nicos. P2 Estendido: memÃ³ria temporal, rede e regimes em modo diagnÃ³stico. P3/P4/P5: infraestrutura existente, falsificaÃ§Ã£o e validaÃ§Ã£o OOS/prospectiva em execuÃ§Ã£o. Nenhum achado diagnÃ³stico possui autoridade de promoÃ§Ã£o sem multiplicidade, holdout e evidÃªncia prospectiva.\n\nEstado terminal: `MISSION_ACTIVE`. NÃ£o declarar `MISSION_PROVEN` atÃ© satisfazer a regra oficial de um Top-6 Ãºnico congelado antes do resultado e 6/6 oficial auditado.\n'''
Path('SMART_CONTINUITY.md').write_text(cont,encoding='utf-8')
print(json.dumps({'mission_status':'MISSION_ACTIVE','hypotheses':len(reg['hypotheses']),'old_proofs_demoted':len(old)}))
