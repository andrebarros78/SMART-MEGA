from pathlib import Path
import json, sys
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from smart_context_regime import ContextRegimeEngine

hist=pd.read_excel(ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx')
draws=[[int(getattr(r,f'Bola{i}')) for i in range(1,7)] for r in hist.itertuples(index=False)]
contests=[int(r.Concurso) for r in hist.itertuples(index=False)]
eng=ContextRegimeEngine(); rows=[]
for c,d in zip(contests,draws):
    pre=eng.metrics(); eng.update(d)
    rows.append({'contest':c,'pre_score':pre['l1_score'],'pre_active':pre['active']})
valid=[r for r in rows if r['contest']>=1001]
s=np.array([r['pre_score'] for r in valid],float)
qs={str(q):float(np.quantile(s,q)) for q in [0,.1,.25,.5,.75,.9,.95,.99,1]}
report={'schema':'SMART_CONTEXT_DETECTOR_DIAGNOSTIC_V1','n':len(valid),'score_quantiles':qs,'threshold':0.0355,'above_threshold':int(np.sum(s>=0.0355)),'max_score':float(s.max()),'mean_score':float(s.mean()),'std_score':float(s.std()),'active_count':sum(bool(r['pre_active']) for r in valid),'note':'read-only causal reconstruction; no predictive authority'}
out=ROOT/'runtime/historical_training_shadow/CONTEXT_DETECTOR_DIAGNOSTIC.json'; out.write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
