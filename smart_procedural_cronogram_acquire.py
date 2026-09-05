from __future__ import annotations

import hashlib, json, time
from pathlib import Path
from urllib.parse import quote
import requests

BASE='https://www.caixa.gov.br/Downloads/caixa-loterias/'
MONTHS={1:'Janeiro',2:'Fevereiro',3:'Marco',4:'Abril',5:'Maio',6:'Junho',7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
OUT=Path('runtime/procedural_sources/cronogramas_caixa')

def sha256_bytes(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def variants(year:int,month:int):
    mm=f'{month:02d}'; name=MONTHS[month]
    names=[name,name.lower(),name.capitalize()]
    if month==3: names += ['Março','março']
    stems=[]
    for n in dict.fromkeys(names):
        stems += [f'Cronograma_{mm}_{n}_{year}.pdf',f'cronograma_{mm}_{n}_{year}.pdf']
    return list(dict.fromkeys(stems))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sess=requests.Session(); sess.headers['User-Agent']='SMART-MEGA/1.0 scientific archival acquisition'
    manifest=[]
    for year in range(2019,2027):
        for month in range(1,13):
            if (year,month)<(2019,10) or (year,month)>(2026,9): continue
            found=None; attempts=[]
            for stem in variants(year,month):
                url=BASE+quote(stem,safe='/:._-')
                try:
                    r=sess.get(url,timeout=10)
                    attempts.append({'url':url,'status':r.status_code,'bytes':len(r.content)})
                    if r.status_code==200 and r.content.startswith(b'%PDF') and len(r.content)>1000:
                        path=OUT/f'{year}-{month:02d}.pdf'; path.write_bytes(r.content)
                        found={'year':year,'month':month,'status':'FOUND','url':url,'file':str(path),'bytes':len(r.content),'sha256':sha256_bytes(r.content)}
                        break
                except Exception as exc:
                    attempts.append({'url':url,'error':type(exc).__name__})
                time.sleep(0.03)
            if found is None:
                found={'year':year,'month':month,'status':'MISSING','attempt_count':len(attempts),'attempts':attempts[-3:]}
            manifest.append(found)
            print(year,month,found['status'],found.get('bytes',''))
    doc={'schema':'SMART_CAIXA_CRONOGRAM_ARCHIVE_V1','source_domain':'caixa.gov.br','range':'2019-10..2026-09','documents':manifest,'found':sum(x['status']=='FOUND' for x in manifest),'missing':sum(x['status']=='MISSING' for x in manifest)}
    Path('runtime/procedural_sources/CRONOGRAM_ARCHIVE_MANIFEST.json').write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'found':doc['found'],'missing':doc['missing']},ensure_ascii=False))

if __name__=='__main__': main()
