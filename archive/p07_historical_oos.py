from pathlib import Path
import json,hashlib,sys
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent
from smart_multi_challengers import POLICY_IDS

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
data=ROOT/'Mega-Sena_through_3050.xlsx'
draws,contests=e.load_draws(data)
agent=SmartSignalAgent(start=1000)
pred,back=agent.predict_next(draws,contests,target_contest=3051)
totals={pid:0 for pid in POLICY_IDS}
diff_vs_primary={pid:0 for pid in POLICY_IDS}
pair_diff={}
for row in back['rows']:
    h=row['multi_challenger_hits_after_result']; tops=row['multi_challenger_top6_before_result']
    for pid in POLICY_IDS: totals[pid]+=int(h[pid])
    base=set(tops['quality_dynamic'])
    for pid in POLICY_IDS:
        if set(tops[pid])!=base: diff_vs_primary[pid]+=1
for i,a in enumerate(POLICY_IDS):
    for b in POLICY_IDS[i+1:]:
        pair_diff[f'{a}|{b}']=sum(set(r['multi_challenger_top6_before_result'][a])!=set(r['multi_challenger_top6_before_result'][b]) for r in back['rows'])
next_policies={pid:{'top6':pred.multi_challengers['policies'][pid]['top6'],'max_weight':pred.multi_challengers['policies'][pid]['max_weight'],'family_totals':pred.multi_challengers['policies'][pid]['family_totals']} for pid in POLICY_IDS}
out={
 'schema':'SMART_P07_MULTI_CHALLENGERS_HISTORICAL_OOS_1','data_cutoff':int(contests[-1]),'oos_start':int(contests[1000]),'oos_predictions':len(back['rows']),
 'policy_ids':list(POLICY_IDS),'selection_performed':False,'selection_deferred_to_p08':True,'retroactive_selection_prohibited':True,
 'total_hits':totals,'uniform_expected_hits':len(back['rows'])*e.UNIFORM_EXPECTED_HITS,'primary_challenger_total_hits':back['total_hits'],
 'different_top6_vs_quality_dynamic':diff_vs_primary,'pairwise_different_top6_contests':pair_diff,
 'next_prediction_shadow':next_policies,
 'primary_top6_preserved':pred.top6==pred.multi_challengers['policies']['quality_dynamic']['top6'],
 'current_multi_sha256':pred.multi_challengers['sha256'],
 'hashes':{'data':sha(data),'module':sha(ROOT/'smart_multi_challengers.py'),'agent':sha(ROOT/'smart_signal_agent.py')},
 'limits':{'historical_winner_not_selected':True,'prospective_predictive_claim':False,'production_switch':False}
}
path=ROOT/'SMART_P07_MULTI_CHALLENGERS_HISTORICAL.json'; path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({**{k:out[k] for k in ['oos_predictions','total_hits','different_top6_vs_quality_dynamic','primary_top6_preserved']},'next':next_policies,'sha256':sha(path)},ensure_ascii=False,indent=2))