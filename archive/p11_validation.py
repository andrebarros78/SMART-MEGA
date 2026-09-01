from pathlib import Path
import json, hashlib, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import *

def run(cid,cal,val,nov):
    g=SignalExpansionGovernance(tuple(SIGNAL_NAMES)); g.register(cid,'freq',3051); c=3051
    for _ in range(MIN_CALIBRATION_OOS): c+=1; g.observe_oos(cid,c,cal,nov)
    for _ in range(MIN_VALIDATION_OOS): c+=1; g.observe_oos(cid,c,val,nov)
    return g,g.candidates[cid].evaluation()

good,gev=run('candidate_good',1,1,.9)
over,oev=run('candidate_overfit',1,-1,.9)
red,rev=run('candidate_redundant',1,1,.1)
noise,nev=run('candidate_noise',0,0,.9)
proof=good.candidates['candidate_good'].authorization_proof()
auth=good.authorize('candidate_good',proof)
checks={
 'good_eligible':gev['eligible_for_material_challenger_influence'] is True,
 'overfit_rejected':oev['eligible_for_material_challenger_influence'] is False and oev['checks']['positive_validation_marginal_utility'] is False,
 'redundant_rejected':rev['eligible_for_material_challenger_influence'] is False and rev['checks']['novelty_sufficient'] is False,
 'noise_rejected':nev['eligible_for_material_challenger_influence'] is False,
 'authorization_challenger_only':auth['scope']=='CHALLENGER_ONLY' and auth['champion_influence'] is False,
 'limited_cap':abs(auth['material_weight_cap']-MAX_LIMITED_CHALLENGER_WEIGHT)<1e-15,
 'no_automatic_material_influence':gev['automatic_material_influence'] is False,
 'authorization_proof_self_hash_valid':auth['proof_sha256']==proof['sha256'] and sha256_json({k:v for k,v in proof.items() if k!='sha256'})==proof['sha256'],
}
report={'schema':'SMART_P11_SIGNAL_EXPANSION_VALIDATION_1','status':'PASS' if all(checks.values()) else 'FAIL','all_checks_pass':all(checks.values()),'checks':checks,'policy':{'min_calibration_oos':MIN_CALIBRATION_OOS,'min_validation_oos':MIN_VALIDATION_OOS,'min_total_oos':MIN_TOTAL_OOS,'min_mean_novelty':MIN_MEAN_NOVELTY,'max_limited_challenger_weight':MAX_LIMITED_CHALLENGER_WEIGHT},'cases':{'good':gev,'overfit':oev,'redundant':rev,'noise':nev},'authorization_proof':proof,'authorization':auth,'interpretation':'engineering governance validation only; no new predictive signal has been promoted'}
out=ROOT/'SMART_P11_SIGNAL_EXPANSION_VALIDATION.json'; out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':report['status'],'checks':checks,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
if not report['all_checks_pass']: raise SystemExit(1)

