from __future__ import annotations

import hashlib, json, re
from pathlib import Path
import pandas as pd
from pypdf import PdfReader

ROOT=Path('.')
MANIFEST=ROOT/'runtime/procedural_sources/CRONOGRAM_ARCHIVE_MANIFEST.json'
HISTORY=ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx'
OUT=ROOT/'runtime/procedural_sources/MEGA_PROCEDURAL_CRONOGRAM_DATASET.json'
DATE_RE=re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')

def pdf_text(path:Path)->str:
    r=PdfReader(str(path))
    return '\n'.join((p.extract_text() or '') for p in r.pages)

def norm(s:str)->str:
    return re.sub(r'\s+',' ',s).strip()

def date_lines(text:str):
    out={}
    for raw in text.splitlines():
        m=DATE_RE.search(raw)
        if m:
            out.setdefault(m.group(1),[]).append(norm(raw))
    return out

def location_candidate(text:str):
    compact=text.replace('\r','')
    idx=compact.upper().rfind('LOCAL DO SORTEIO')
    if idx>=0:
        tail=compact[idx+len('LOCAL DO SORTEIO'):]
        stop=len(tail)
        for marker in ['Os sorteios','OS SORTEIOS','SORTEIOS (Hor','Informações disponíveis','Informa']:
            j=tail.find(marker)
            if j>=0: stop=min(stop,j)
        candidate=norm(tail[:stop])
        if 3<=len(candidate)<=500:
            return candidate
    for token in ['ESPAÇO DA SORTE','Espaço da Sorte','ESPAÇO LOTERIAS CAIXA','Espaço Loterias CAIXA']:
        if token in compact:
            return token
    return None

def main():
    man=json.loads(MANIFEST.read_text(encoding='utf-8'))
    hist=pd.read_excel(HISTORY)
    hist['Data do Sorteio']=pd.to_datetime(hist['Data do Sorteio'],dayfirst=True,errors='raise')
    docs={(int(x['year']),int(x['month'])):x for x in man['documents'] if x['status']=='FOUND'}
    cache={}
    for key,d in docs.items():
        path=Path(d['file']); text=pdf_text(path)
        cache[key]={'lines':date_lines(text),'location':location_candidate(text)}
    rows=[]; verified=0; mismatch=0
    for _,r in hist.iterrows():
        contest=int(r['Concurso']); dt=r['Data do Sorteio']; key=(int(dt.year),int(dt.month))
        if key not in docs or dt < pd.Timestamp('2019-10-01'): continue
        d=docs[key]; meta=cache[key]; ds=dt.strftime('%d/%m/%Y'); candidates=meta['lines'].get(ds,[])
        token=re.compile(rf'(?<!\d){contest}(?!\d)')
        matched=[line for line in candidates if token.search(line)]
        status='VERIFIED_CONTEST_DATE_IN_OFFICIAL_CRONOGRAM' if matched else 'DATE_PRESENT_CONTEST_NOT_MATCHED'
        verified += int(bool(matched)); mismatch += int(not matched)
        rows.append({'contest':contest,'draw_date':dt.strftime('%Y-%m-%d'),'evidence_status':status,'pre_draw_known':True,'official_source_domain':'caixa.gov.br','official_pdf_url':d['url'],'official_pdf_sha256':d['sha256'],'official_pdf_file':str(Path(d['file'])),'matched_source_lines':matched[:3],'date_source_lines':candidates[:5],'location_candidate_raw':meta['location'],'predictive_weight_authorized':False})
    history_hash=hashlib.sha256(HISTORY.read_bytes()).hexdigest()
    doc={'schema':'SMART_MEGA_PROCEDURAL_CRONOGRAM_DATASET_V1','source_policy':'official CAIXA cronograms only; no inferred missing metadata','history_source_sha256':history_hash,'rows':rows,'row_count':len(rows),'verified_contest_date_rows':verified,'mismatch_rows':mismatch,'predictive_weight_authorized':False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'rows':len(rows),'verified':verified,'mismatch':mismatch,'coverage_first':rows[0]['contest'] if rows else None,'coverage_last':rows[-1]['contest'] if rows else None},ensure_ascii=False))

if __name__=='__main__': main()
