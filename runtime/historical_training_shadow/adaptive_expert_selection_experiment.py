import json, math, random, statistics, sys
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\New Projet\SMART-MEGA'); sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
DATA=ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx'
draws,contests=e.load_draws(DATA); pre=e.precompute_scores(e.onehot(draws))
experts=['freq25','freq50','freq100','freq250','freq500','freq1000','freq_global','ewma10','ewma25','ewma50','ewma100','ewma250']
replay=json.loads((ROOT/'runtime/historical_training_shadow/SMART_CAUSAL_REPLAY_1001_3053.json').read_text(encoding='utf-8'))
rr=replay if isinstance(replay,list) else replay.get('rows',replay.get('replay',replay.get('records',[])))
byc={int(r['contest']):r for r in rr}
# Build expert causal hit history and top6 lookup from pre-result scores.
expert_hits={k:[] for k in experts}; records=[]
for t in range(1000,len(draws)):
    c=int(contests[t]); actual=set(draws[t]); tops={}; hits={}
    for k in experts:
        top,_=e.rank_top6(pre[k][t]); tops[k]=top; hits[k]=len(set(top)&actual)
    records.append({'contest':c,'ensemble_hits':int(byc[c]['challenger_hits']),'hits':hits,'tops':tops})
# 70/30 split fixed. Select ONLY window on calibration, then evaluate once.
cut=int(len(records)*.70); cal=records[:cut]; ev=records[cut:]
windows=[25,50,100,250]
def run_policy(rows,w,history_rows):
    hist=list(history_rows); out=[]
    for r in rows:
        trailing=hist[-w:] if len(hist)>=w else hist
        means={k:(sum(x['hits'][k] for x in trailing)/len(trailing) if trailing else 0.6) for k in experts}
        best=max(experts,key=lambda k:(means[k],k))
        out.append({'contest':r['contest'],'selected':best,'selected_hits':r['hits'][best],'ensemble_hits':r['ensemble_hits'],'mean_before':means[best]})
        hist.append(r)
    return out
cal_scores={}
for w in windows:
    out=run_policy(cal,w,[]); cal_scores[w]=sum(x['selected_hits'] for x in out)
best_w=max(windows,key=lambda w:(cal_scores[w],-w))
out=run_policy(ev,best_w,cal)
diffs=[x['selected_hits']-x['ensemble_hits'] for x in out]; obs=sum(diffs); mean_diff=statistics.mean(diffs)
# paired random sign-flip test, one-sided adaptive > ensemble
rng=random.Random(2026090502); ge=0; reps=20000
for _ in range(reps):
    s=sum(d if rng.random()<.5 else -d for d in diffs)
    if s>=obs: ge+=1
p=(ge+1)/(reps+1)
# also compare to uniform expected 0.6 hits/contest
selected_total=sum(x['selected_hits'] for x in out); ensemble_total=sum(x['ensemble_hits'] for x in out); expected=.6*len(out)
counts={k:sum(1 for x in out if x['selected']==k) for k in experts}
result={'schema':'SMART_ADAPTIVE_EXPERT_SELECTION_V1','policy':'select expert with highest trailing mean hits; selection uses only prior contests','calibration_n':len(cal),'evaluation_n':len(ev),'evaluation_contest_min':ev[0]['contest'],'evaluation_contest_max':ev[-1]['contest'],'candidate_windows':windows,'calibration_total_hits_by_window':cal_scores,'selected_window':best_w,'evaluation_selected_total_hits':selected_total,'evaluation_ensemble_total_hits':ensemble_total,'evaluation_uniform_expected_hits':expected,'paired_total_gain_vs_ensemble':obs,'paired_mean_gain_vs_ensemble':mean_diff,'paired_signflip_p_one_sided':p,'selection_counts':counts,'passes_005_vs_ensemble':p<.05}
(ROOT/'runtime/historical_training_shadow/ADAPTIVE_EXPERT_SELECTION_EXPERIMENT.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))
