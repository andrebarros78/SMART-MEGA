from __future__ import annotations
import json,re,hashlib
from pathlib import Path

def extract_caption(path:str|Path, contest:int, video_id:str, video_url:str)->dict:
    p=Path(path); d=json.loads(p.read_text(encoding='utf-8'))
    events=[]
    for e in d.get('events',[]):
        text=''.join(s.get('utf8','') for s in e.get('segs',[])).replace('\n',' ').strip()
        if text: events.append((float(e.get('tStartMs',0))/1000.0,text))
    joined=' '.join(t for _,t in events)
    case=None; case_t=None
    for sec,text in events:
        m=re.search(r'\bCJ60[A-Z]\b',text,re.I)
        if m:
            case=m.group(0).upper(); case_t=sec; break
    seal=None; seal_t=None
    if case_t is not None:
        for sec,text in events:
            if case_t<=sec<=case_t+30:
                m=re.search(r'\bL\s*(\d{2})\s*(\d{3})\b',text,re.I)
                if m:
                    seal=f'L{m.group(1)}{m.group(2)}'; seal_t=sec; break
    auditor_mentions=sum('auditor' in t.lower() for _,t in events)
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    return {
      'schema':'SMART_PROCEDURAL_CAPTION_EVIDENCE_V1','contest':int(contest),'video_id':video_id,'video_url':video_url,
      'caption_sha256':h,'ball_case_identifier':case,'ball_case_timestamp_seconds':case_t,
      'opening_seal_identifier':seal,'opening_seal_timestamp_seconds':seal_t,'auditor_mention_count':auditor_mentions,
      'evidence_scope':'SCIENTIFIC_MECHANISM_ONLY','same_contest_predictive_weight_authorized':False,
      'reason':'broadcast procedural metadata is first observed after betting closes; retained for mechanism study only'
    }

if __name__=='__main__':
    src=Path('runtime/procedural_sources/youtube_captions/BcrFWNN7PWo.pt-orig.json3')
    out=extract_caption(src,3053,'BcrFWNN7PWo','https://www.youtube.com/watch?v=BcrFWNN7PWo')
    dst=Path('runtime/procedural_sources/YOUTUBE_PROCEDURAL_3053.json'); dst.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(out,indent=2,ensure_ascii=False))
