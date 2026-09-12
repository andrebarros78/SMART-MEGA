import json, math, statistics
from pathlib import Path
p=Path('runtime/historical_training_shadow/SMART_CAUSAL_REPLAY_1001_3053.json')
d=json.loads(p.read_text(encoding='utf-8'))
rows=d if isinstance(d,list) else d.get('rows',d.get('replay',d.get('records',[])))
# derive pre-result causal features available in each record and compare hot block 2501-2750 vs rest/recent
hot=[r for r in rows if 2501<=int(r['contest'])<=2750]
pre=[r for r in rows if 2251<=int(r['contest'])<=2500]
post=[r for r in rows if 2751<=int(r['contest'])<=3000]
recent=[r for r in rows if 2804<=int(r['contest'])<=3053]
print('GROUP_HITS')
for name,g in [('pre',pre),('hot',hot),('post',post),('recent',recent)]:
 print(name,len(g),sum(r['challenger_hits'] for r in g),sum(r['challenger_hits'] for r in g)/len(g))
# scalar pre-result fields
fields=['meta_strength_before_result','meta_factor_min_before_result','meta_factor_max_before_result','meta_family_divergence_before_result','meta_regime_intensity_before_result','rank_calibration_brier_after_result']
for f in fields:
 print('\nFIELD',f)
 for name,g in [('pre',pre),('hot',hot),('post',post),('recent',recent)]:
  vals=[r.get(f) for r in g if isinstance(r.get(f),(int,float))]
  if vals: print(name,round(statistics.mean(vals),8),round(statistics.pstdev(vals),8))
# weights average by group
print('\nWEIGHT_SHIFT')
keys=sorted(hot[0]['weights_before_result'])
for k in keys:
 vals=[]
 for g in [pre,hot,post,recent]: vals.append(statistics.mean(float(r['weights_before_result'][k]) for r in g))
 spread=max(vals)-min(vals)
 if spread>0.01: print(k,*[round(x,5) for x in vals],'spread',round(spread,5))
# identify expert whose performance changes most hot vs neighbors
print('\nEXPERT_REGIME_DIFF')
for k in keys:
 def mh(g): return statistics.mean(float(r['expert_hits'].get(k,0)) for r in g)
 a,b,c=mh(pre),mh(hot),mh(post)
 print(k,round(a,4),round(b,4),round(c,4),'hot-v-neighbor',round(b-(a+c)/2,4))
