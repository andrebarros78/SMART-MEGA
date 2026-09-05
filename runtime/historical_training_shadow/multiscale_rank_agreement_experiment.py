import json, math, random, statistics, sys
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\New Projet\SMART-MEGA'); sys.path.insert(0,str(ROOT))
import smart_v2_engine as e
DATA=ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx'
draws,contests=e.load_draws(DATA); pre=e.precompute_scores(e.onehot(draws))
selected=['freq50','freq100','freq1000','ewma100','ewma250']
rows=[]
for t in range(1000,len(draws)):
    ranks={}; tops={}
    for name in selected:
        score=pre[name][t]; top,order=e.rank_top6(score); tops[name]=set(top)
        rank=np.empty(60,int); rank[order]=np.arange(60); ranks[name]=rank
    pair_corr=[]; pair_j=[]
    for i,a in enumerate(selected):
        for b in selected[i+1:]:
            ra=ranks[a]; rb=ranks[b]
            c=float(np.corrcoef(ra,rb)[0,1]); pair_corr.append(c)
            pair_j.append(len(tops[a]&tops[b])/len(tops[a]|tops[b]))
    union=set().union(*tops.values()); counts={n:sum(n in tops[k] for k in selected) for n in union}
    consensus3=sum(1 for v in counts.values() if v>=3)
    consensus4=sum(1 for v in counts.values() if v>=4)
    rows.append({'contest':int(contests[t]),'hits':None,
                 'mean_rank_corr':float(statistics.mean(pair_corr)),
                 'min_rank_corr':float(min(pair_corr)),
                 'mean_top6_jaccard':float(statistics.mean(pair_j)),
                 'consensus3_count':consensus3,'consensus4_count':consensus4,
                 'top_union_size':len(union)})
# bind causal replay outcome only after features are computed
replay=json.loads((ROOT/'runtime/historical_training_shadow/SMART_CAUSAL_REPLAY_1001_3053.json').read_text(encoding='utf-8'))
rr=replay if isinstance(replay,list) else replay.get('rows',replay.get('replay',replay.get('records',[])))
hmap={int(r['contest']):int(r['challenger_hits']) for r in rr}
for r in rows:r['hits']=hmap[r['contest']]
cut=int(len(rows)*.70); cal=rows[:cut]; ev=rows[cut:]
metrics=['mean_rank_corr','min_rank_corr','mean_top6_jaccard','consensus3_count','consensus4_count','top_union_size']
def quantile(vals,q):
 s=sorted(vals); x=(len(s)-1)*q; lo=int(math.floor(x)); hi=int(math.ceil(x)); return s[lo] if lo==hi else s[lo]*(hi-x)+s[hi]*(x-lo)
comps=[]; invalid=[]
for m in metrics:
 for tail,thr in [('low',quantile([x[m] for x in cal],.2)),('high',quantile([x[m] for x in cal],.8))]:
  flags=[x[m]<=thr if tail=='low' else x[m]>=thr for x in ev]; n=sum(flags)
  if n==0 or n==len(ev): invalid.append({'metric':m,'tail':tail,'threshold':thr,'n_selected':n}); continue
  a=[x['hits'] for x,f in zip(ev,flags) if f]; b=[x['hits'] for x,f in zip(ev,flags) if not f]; diff=statistics.mean(a)-statistics.mean(b)
  y=[x['hits'] for x in ev]; rng=random.Random(2026090501+len(comps)); ge=0
  for _ in range(5000):
   yy=y[:]; rng.shuffle(yy); aa=[v for v,f in zip(yy,flags) if f]; bb=[v for v,f in zip(yy,flags) if not f]
   if statistics.mean(aa)-statistics.mean(bb)>=diff-1e-15: ge+=1
  p=(ge+1)/5001
  comps.append({'metric':m,'tail':tail,'threshold':float(thr),'n_selected':len(a),'mean_selected':statistics.mean(a),'mean_other':statistics.mean(b),'diff':diff,'p_raw':p})
order=sorted(range(len(comps)),key=lambda i:comps[i]['p_raw']); run=0
for rank,i in enumerate(order):
 adj=min(1,(len(comps)-rank)*comps[i]['p_raw']); run=max(run,adj); comps[i]['p_holm']=run; comps[i]['reject_005']=run<=.05
out={'schema':'SMART_MULTISCALE_RANK_AGREEMENT_V1','feature_scope':'pre-contest only','selected_experts':selected,'calibration_n':len(cal),'evaluation_n':len(ev),'evaluation_contest_min':ev[0]['contest'],'evaluation_contest_max':ev[-1]['contest'],'invalid':invalid,'comparisons':comps,'holm_rejections':[c for c in comps if c['reject_005']]}
(ROOT/'runtime/historical_training_shadow/MULTISCALE_RANK_AGREEMENT_EXPERIMENT.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(out,indent=2,ensure_ascii=False))
