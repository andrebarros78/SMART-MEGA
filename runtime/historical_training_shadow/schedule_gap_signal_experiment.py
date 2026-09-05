from __future__ import annotations
import json,math,random
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path('.')
HIST=ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx'
REPLAY=ROOT/'runtime/historical_training_shadow/SMART_CAUSAL_REPLAY_1001_3053.json'
OUT=ROOT/'runtime/historical_training_shadow/SCHEDULE_GAP_SIGNAL_EXPERIMENT.json'
ALPHAS=[10.0,25.0,50.0,100.0,250.0]
START=1000
VALIDATION=(2201,2700)
HOLDOUT=(2701,3053)

def gap_class(days:int)->str:
    if days<=1:return 'D1'
    if days==2:return 'D2'
    if days==3:return 'D3'
    return 'D4P'

def rank_top6(score):
    nums=np.arange(1,61); order=np.lexsort((nums,-np.asarray(score,float))); return nums[order[:6]].tolist()

def run(alpha,draws,contests,dates):
    global_counts=np.zeros(60,float); global_n=0
    class_counts={}; class_n={}; rows=[]
    # prewarm all observations strictly before START
    for t in range(START):
        if t>0:
            g=gap_class((dates[t]-dates[t-1]).days); class_counts.setdefault(g,np.zeros(60,float)); class_n[g]=class_n.get(g,0)+1; class_counts[g][draws[t]-1]+=1
        global_counts[draws[t]-1]+=1; global_n+=1
    for t in range(START,len(draws)):
        g=gap_class((dates[t]-dates[t-1]).days)
        prior=(global_counts+1.0)/(global_n+10.0)
        cc=class_counts.get(g,np.zeros(60,float)); cn=class_n.get(g,0)
        p=(cc+alpha*prior)/(cn+alpha)
        top=rank_top6(p); actual=set(draws[t]); hits=len(set(top)&actual)
        rows.append({'contest':int(contests[t]),'gap_class':g,'gap_days':int((dates[t]-dates[t-1]).days),'top6':top,'hits':hits})
        class_counts.setdefault(g,np.zeros(60,float)); class_counts[g][draws[t]-1]+=1; class_n[g]=class_n.get(g,0)+1
        global_counts[draws[t]-1]+=1; global_n+=1
    return rows

def subset(rows,lo,hi): return [r for r in rows if lo<=r['contest']<=hi]
def total(rows): return sum(r['hits'] for r in rows)

def signflip_p(diffs,reps=20000,seed=20260905):
    obs=sum(diffs); rng=random.Random(seed); ge=0
    for _ in range(reps):
        s=sum(d if rng.random()<0.5 else -d for d in diffs)
        if s>=obs: ge+=1
    return (ge+1)/(reps+1)

def main():
    df=pd.read_excel(HIST); draws=df[[f'Bola{i}' for i in range(1,7)]].to_numpy(int); contests=df['Concurso'].to_numpy(int); dates=pd.to_datetime(df['Data do Sorteio'],dayfirst=True).tolist()
    candidates={}
    for a in ALPHAS:
        rows=run(a,draws,contests,dates); val=subset(rows,*VALIDATION); candidates[str(a)]={'validation_hits':total(val),'validation_n':len(val),'rows':rows}
    chosen=max(ALPHAS,key=lambda a:(candidates[str(a)]['validation_hits'],-a))
    final_rows=candidates[str(chosen)]['rows']; hold=subset(final_rows,*HOLDOUT)
    rd=json.loads(REPLAY.read_text(encoding='utf-8')); rr=rd if isinstance(rd,list) else rd.get('rows',[]); champ={int(r['contest']):int(r['challenger_hits']) for r in rr if HOLDOUT[0]<=int(r['contest'])<=HOLDOUT[1]}
    common=[r for r in hold if r['contest'] in champ]; diffs=[int(r['hits'])-champ[r['contest']] for r in common]
    by_gap={}
    for g in sorted(set(r['gap_class'] for r in common)):
        x=[r for r in common if r['gap_class']==g]; by_gap[g]={'n':len(x),'hits':total(x),'mean_hits':total(x)/len(x)}
    expected=len(common)*0.6
    report={'schema':'SMART_SCHEDULE_GAP_SIGNAL_EXPERIMENT_V1','feature_availability':'ACTIONABLE_BEFORE_BET_CLOSE','design':'alpha selected only on validation 2201-2700; final comparison on untouched holdout 2701-3053','candidate_validation_hits':{k:v['validation_hits'] for k,v in candidates.items()},'selected_alpha':chosen,'holdout_n':len(common),'holdout_gap_signal_hits':total(common),'holdout_champion_hits':sum(champ[r['contest']] for r in common),'holdout_uniform_expected_hits':expected,'delta_hits_vs_champion':sum(diffs),'paired_signflip_p_one_sided':signflip_p(diffs) if common else None,'holdout_by_gap':by_gap,'predictive_weight_authorized':False}
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
