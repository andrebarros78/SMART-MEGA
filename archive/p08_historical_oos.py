from pathlib import Path
import json,hashlib,sys,collections
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent
from smart_multi_challengers import POLICY_IDS

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
data=ROOT/'Mega-Sena_through_3050.xlsx'; draws,contests=e.load_draws(data)
agent=SmartSignalAgent(start=1000); pred,back=agent.predict_next(draws,contests,target_contest=3051)
sel_counts=collections.Counter(); selected_hits=0; fixed={p:0 for p in POLICY_IDS}; switches=0; prev=None; oracle=0
rows=[]
for r in back['rows']:
    pre=r['meta_governor_before_result']; upd=r['meta_governor_update_after_result']; selected=pre['selected_policy']
    sel_counts[selected]+=1; selected_hits+=int(upd['selected_hits']); oracle+=max(int(x) for x in upd['policy_hits'].values())
    for p in POLICY_IDS: fixed[p]+=int(upd['policy_hits'][p])
    if prev is not None and selected!=prev: switches+=1
    prev=selected
    rows.append({'contest':r['contest'],'selected_policy_before_result':selected,'selected_top6_before_result':pre['selected_top6'],'selected_hits_after_result':upd['selected_hits'],'policy_weights_before_result':pre['policy_weights_before_result'],'policy_hits_after_result':upd['policy_hits']})
out={'schema':'SMART_P08_META_GOVERNOR_HISTORICAL_OOS_1','data_cutoff':int(contests[-1]),'oos_start':int(contests[1000]),'oos_predictions':len(rows),
'parameters':{'eta':pred.meta_governor['eta'],'prior_mix':pred.meta_governor['prior_mix'],'tuned_on_replay':False},
'selected_cumulative_hits':selected_hits,'fixed_policy_hits':fixed,'selection_counts':dict(sel_counts),'switches':switches,
'posthoc_oracle_hits_not_used':oracle,'oracle_selection_prohibited':True,
'next_selection_shadow':pred.meta_governor,'governor_state':agent.meta_governor.state(),
'guards':{'selection_before_result_all':all('selected_policy_before_result' in x for x in rows),'update_after_result_only':all(r['meta_governor_update_after_result']['update_after_result_only'] for r in back['rows']),'selected_hits_state_matches':selected_hits==agent.meta_governor.selected_cumulative_hits,'production_authority':False,'champion_remains_active':True,'retroactive_selection':False,'primary_challenger_not_rewritten':True},
'hashes':{'data':sha(data),'meta_governor':sha(ROOT/'smart_meta_governor.py'),'multi_challengers':sha(ROOT/'smart_multi_challengers.py'),'agent':sha(ROOT/'smart_signal_agent.py')},
'interpretation':'historical causal engineering evidence only; no prospective superiority claim'}
path=ROOT/'SMART_P08_META_GOVERNOR_HISTORICAL.json'; path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'oos_predictions':out['oos_predictions'],'selected_cumulative_hits':selected_hits,'fixed_policy_hits':fixed,'selection_counts':dict(sel_counts),'switches':switches,'next_selected_policy':pred.meta_governor['selected_policy'],'next_top6':pred.meta_governor['selected_top6'],'sha256':sha(path)},ensure_ascii=False,indent=2))