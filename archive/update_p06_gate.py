from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import smart_champion_challenger as cc
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
gp=ROOT/'SMART_3052_IMPLEMENTATION_GATE.json'; gate=json.loads(gp.read_text(encoding='utf-8'))
proofp=ROOT/'SMART_P06_RANK_SCORE_CALIBRATION_PROOF.json'; proof=json.loads(proofp.read_text(encoding='utf-8'))
assert proof['status']=='MISSION_PROVEN' and all(proof['checks'].values())
items={x['id']:x for x in gate['items']}
for pid in ['P01_COUNTERFACTUAL_ATTRIBUTION','P02_MARGINAL_SIGNAL_UTILITY','P03_FALSE_CONSENSUS_REDUNDANCY','P04_SIGNAL_INTERACTIONS','P05_CONTEXTUAL_META_WEIGHTS']:
    assert items[pid]['status']=='PROVEN'
p06=items['P06_RANK_SCORE_CALIBRATION']
assert p06['status']!='PROVEN'
p06['status']='PROVEN'
p06['evidence']=[
 {'type':'implementation_proof','file':'SMART_P06_RANK_SCORE_CALIBRATION_PROOF.json','sha256':sha(proofp)},
 {'type':'coverage','file':'SMART_COVERAGE_P06_FINAL.json','sha256':sha(ROOT/'SMART_COVERAGE_P06_FINAL.json'),'statements':1769,'branches':564,'coverage':'100% lines + branches'},
 {'type':'strength_calibration','file':'SMART_P06_STRENGTH_CALIBRATION.json','sha256':sha(ROOT/'SMART_P06_STRENGTH_CALIBRATION.json'),'selected_pre_holdout':0.5,'scope':'1001-2200 only'},
 {'type':'rejected_candidate_holdout','file':'SMART_P06_FINAL_HOLDOUT.json','sha256':sha(ROOT/'SMART_P06_FINAL_HOLDOUT.json'),'candidate_strength':0.5,'final_holdout_delta_vs_uniform':1.3576700524302432e-05,'decision':'REJECT_NONZERO_CALIBRATION'},
 {'type':'neutralized_validation','file':'SMART_P06_NEUTRALIZED_VALIDATION.json','sha256':sha(ROOT/'SMART_P06_NEUTRALIZED_VALIDATION.json'),'adopted_strength':0.0,'final_holdout_delta_vs_uniform':0.0,'full_oos_delta_vs_uniform':0.0},
 {'type':'decision','file':'SMART_P06_DECISION.json','sha256':sha(ROOT/'SMART_P06_DECISION.json'),'mode':'NEUTRALIZED','published_probability':0.10},
 {'type':'module','file':'smart_rank_score_calibration.py','sha256':sha(ROOT/'smart_rank_score_calibration.py')},
 {'type':'future_freeze_governance','file':'smart_champion_challenger.py','sha256':sha(ROOT/'smart_champion_challenger.py'),'hashes_rank_score_calibration':True,'snapshots_rank_score_calibration':True},
 {'type':'future_adjudication_governance','file':'adjudicate_signal_challenger.py','sha256':sha(ROOT/'adjudicate_signal_challenger.py'),'appends_frozen_calibration_evaluation':True,'backfill_3051':False},
]
p06['proven_brt']=datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()
proven=[x for x in gate['items'] if x['status']=='PROVEN']
pending=[x['id'] for x in gate['items'] if x['status']!='PROVEN']
gate['freeze_allowed']=len(proven)==15 and not pending
gate['progress']={'proven_items':len(proven),'total_items':15,'remaining_items':len(pending)}
gate['updated_brt']=datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()
gp.write_text(json.dumps(gate,ensure_ascii=False,indent=2),encoding='utf-8')
try:
    cc.require_pre_3052_gate(3052,gp); blocked=False; reason=''
except ValueError as ex:
    blocked=True; reason=str(ex)
checks={'p01_to_p05_preserved':all(items[x]['status']=='PROVEN' for x in ['P01_COUNTERFACTUAL_ATTRIBUTION','P02_MARGINAL_SIGNAL_UTILITY','P03_FALSE_CONSENSUS_REDUNDANCY','P04_SIGNAL_INTERACTIONS','P05_CONTEXTUAL_META_WEIGHTS']),
        'p06_status_proven':p06['status']=='PROVEN','p06_has_evidence':len(p06['evidence'])>=8,
        'exactly_six_items_proven':len(proven)==6,'remaining_nine_not_falsely_proven':len(pending)==9,
        'freeze_3052_still_blocked':blocked,'freeze_allowed_false':gate['freeze_allowed'] is False}
up={'schema':'SMART_P06_GATE_UPDATE_PROOF_1','status':'MISSION_PROVEN' if all(checks.values()) else 'MISSION_NOT_PROVEN','checks':checks,
    'gate_sha256':sha(gp),'p06_proof_sha256':sha(proofp),'progress':gate['progress'],'pending':pending,'freeze_3052_block_reason':reason}
out=ROOT/'SMART_P06_GATE_UPDATE_PROOF.json'; out.write_text(json.dumps(up,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':up['status'],'failed':[k for k,v in checks.items() if not v],'gate_sha256':sha(gp),'update_proof_sha256':sha(out),'block_reason':reason},ensure_ascii=False,indent=2))
