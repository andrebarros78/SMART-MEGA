from __future__ import annotations
import json, math, random, statistics
from pathlib import Path
import pandas as pd
from pypdf import PdfReader

ROOT=Path('.')
DATA=json.loads((ROOT/'runtime/procedural_sources/MEGA_PROCEDURAL_CRONOGRAM_DATASET.json').read_text(encoding='utf-8'))
HIST=pd.read_excel(ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx')
HIST['Data do Sorteio']=pd.to_datetime(HIST['Data do Sorteio'],dayfirst=True)
DRAW={int(r.Concurso):[int(getattr(r,f'Bola{i}')) for i in range(1,7)] for r in HIST.itertuples(index=False)}

def venue_from_pdf(path):
    t='\n'.join((p.extract_text() or '') for p in PdfReader(path).pages).upper()
    if 'PAULISTA' in t or 'ESPA�O DA SORTE' in t: return 'ESPACO_DA_SORTE_PAULISTA_SP'
    if 'CRUZEIRO DO SUL' in t or 'RODOVI' in t or 'TIET' in t or 'ESPA�O LOTERIAS CAIXA' in t: return 'ESPACO_LOTERIAS_CAIXA_TIETE_SP'
    return 'UNKNOWN'

pdf_venue={}
rows=[]
for r in DATA['rows']:
    if not r['evidence_status'].startswith('VERIFIED'): continue
    p=r['official_pdf_file']
    if p not in pdf_venue: pdf_venue[p]=venue_from_pdf(p)
    rows.append({'contest':r['contest'],'venue':pdf_venue[p],'draw':DRAW[r['contest']]})

# chronological split to prevent venue discovery on evaluation data
rows=sorted(rows,key=lambda x:x['contest'])
cut=int(len(rows)*0.70); cal=rows[:cut]; eva=rows[cut:]

def freq(group):
    n=len(group); counts=[0]*60
    for r in group:
        for x in r['draw']: counts[x-1]+=1
    return [c/n for c in counts]

def l1(a,b): return sum(abs(x-y) for x,y in zip(a,b))

def stat_by_venue(group):
    by={}
    for r in group: by.setdefault(r['venue'],[]).append(r)
    valid={k:v for k,v in by.items() if k!='UNKNOWN' and len(v)>=20}
    if len(valid)<2: return None, {k:len(v) for k,v in by.items()}
    ks=sorted(valid,key=lambda k:len(valid[k]),reverse=True)[:2]
    return l1(freq(valid[ks[0]]),freq(valid[ks[1]])), {k:len(v) for k,v in by.items()}

cal_stat,cal_counts=stat_by_venue(cal); eva_stat,eva_counts=stat_by_venue(eva)
# Evaluate only if both venues remain supported in untouched evaluation.
rng=random.Random(20260905); p=None
if eva_stat is not None:
    labels=[r['venue'] for r in eva]; draws=[r['draw'] for r in eva]; obs=eva_stat; ge=0; reps=5000
    for _ in range(reps):
        sh=labels[:]; rng.shuffle(sh); sim=[{'venue':v,'draw':d} for v,d in zip(sh,draws)]; s,_=stat_by_venue(sim)
        if s is not None and s>=obs-1e-15: ge+=1
    p=(ge+1)/(reps+1)
report={'schema':'SMART_PROCEDURAL_VENUE_EXPERIMENT_V1','verified_rows':len(rows),'calibration_n':len(cal),'evaluation_n':len(eva),'calibration_venue_counts':cal_counts,'evaluation_venue_counts':eva_counts,'calibration_l1_between_two_main_venues':cal_stat,'evaluation_l1_between_two_main_venues':eva_stat,'permutation_p_evaluation':p,'predictive_weight_authorized':False,'interpretation':'venue is only usable if both venue categories recur in untouched evaluation; otherwise time/venue confounding prevents causal predictive promotion'}
Path('runtime/historical_training_shadow/PROCEDURAL_VENUE_EXPERIMENT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(report,indent=2,ensure_ascii=False))
