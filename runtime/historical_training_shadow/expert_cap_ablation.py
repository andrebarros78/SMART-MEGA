from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import smart_signal_agent as ssa
import smart_signal_weights as ssw
from smart_signal_agent import SmartSignalAgent

HIST=ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx'
OUT=ROOT/'runtime/historical_training_shadow/EXPERT_CAP_ABLATION.json'
CAPS=[0.25,0.30,0.35,0.42]

def load():
 d=pd.read_excel(HIST)
 d['Data do Sorteio']=pd.to_datetime(d['Data do Sorteio'],dayfirst=True)
 contests=[int(x) for x in d['Concurso']]
 draws=[[int(row[f'Bola{i}']) for i in range(1,7)] for _,row in d.iterrows()]
 return draws,contests

def capped(weights,cap):
 out=ssw._normalize(dict(weights))
 cap=max(float(cap),1.0/len(out))
 while True:
  over=[k for k,v in out.items() if v>cap+1e-15]
  if not over: break
  locked=cap*len(over); free=[k for k in out if k not in over]; fm=sum(out[k] for k in free)
  for k in over: out[k]=cap
  if not free or fm<=0: break
  scale=(1-locked)/fm
  for k in free: out[k]*=scale
 return ssw._normalize(out)

def run_cap(draws,contests,cap):
 original=ssa.dynamic_weights
 def wrapper(metrics,families):
  w,c=original(metrics,families)
  w=capped(w,cap)
  for k in c: c[k]['shadow_cap_final_weight']=w[k]
  return w,c
 ssa.dynamic_weights=wrapper
 try:
  a=SmartSignalAgent(start=1000)
  rep=a.replay_history(draws,contests)
  rows=rep['rows']
 finally:
  ssa.dynamic_weights=original
 def hits(lo,hi): return sum(int(r['challenger_hits']) for r in rows if lo<=int(r['contest'])<=hi)
 return {'cap':cap,'calibration_hits_1001_2200':hits(1001,2200),'validation_hits_2201_2700':hits(2201,2700),'holdout_hits_2701_3053':hits(2701,3053),'global_hits':sum(int(r['challenger_hits']) for r in rows),'final_max_weight':max(rows[-1]['weights_before_result'].values())}

def main():
 draws,contests=load(); results=[]
 for cap in CAPS:
  x=run_cap(draws,contests,cap); results.append(x); print(json.dumps(x))
 best=max(results,key=lambda x:(x['calibration_hits_1001_2200'],-x['cap']))
 baseline=next(x for x in results if x['cap']==0.42)
 report={'schema':'SMART_EXPERT_CAP_ABLATION_V1','design':'causal replay for each cap; cap selected only by contests 1001-2200; validation 2201-2700; diagnostic holdout 2701-3053','caps':CAPS,'results':results,'selected_by_calibration':best,'baseline_cap_042':baseline,'selected_validation_delta_vs_baseline':best['validation_hits_2201_2700']-baseline['validation_hits_2201_2700'],'selected_holdout_delta_vs_baseline':best['holdout_hits_2701_3053']-baseline['holdout_hits_2701_3053'],'selected_global_delta_vs_baseline':best['global_hits']-baseline['global_hits'],'predictive_weight_authorized':False,'note':'historical diagnostic only; no production mutation'}
 OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
