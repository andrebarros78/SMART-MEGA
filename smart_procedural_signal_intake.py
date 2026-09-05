from __future__ import annotations

import hashlib
from pathlib import Path
import pandas as pd

REQUIRED = [
    'contest','scheduled_datetime','draw_location','source_video_url','source_evidence_timestamp'
]
OPTIONAL = [
    'actual_pre_draw_timestamp','exceptional_location','schedule_class','ball_case_identifier',
    'opening_seal_identifier','equipment_identifier','pre_draw_manual_ball_release',
    'pre_draw_intervention_flag','auditor_count','evidence_sha256'
]
FORBIDDEN = {
    'drawn_numbers','bola1','bola2','bola3','bola4','bola5','bola6','winner_information',
    'prize_distribution','post_result_commentary','post_draw_closing_seal'
}

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def validate_frame(df: pd.DataFrame) -> dict:
    lower={str(c).strip().lower() for c in df.columns}
    missing=[c for c in REQUIRED if c not in lower]
    forbidden=sorted(lower & FORBIDDEN)
    if missing: raise ValueError(f'missing required fields: {missing}')
    if forbidden: raise ValueError(f'post-result/forbidden fields present: {forbidden}')
    cmap={str(c).strip().lower():c for c in df.columns}
    contests=pd.to_numeric(df[cmap['contest']],errors='raise').astype(int)
    if contests.duplicated().any(): raise ValueError('duplicate contest')
    if any(b<=a for a,b in zip(contests.tolist(),contests.tolist()[1:])): raise ValueError('contests must be strictly increasing')
    scheduled=pd.to_datetime(df[cmap['scheduled_datetime']],errors='raise',utc=True)
    evidence=pd.to_datetime(df[cmap['source_evidence_timestamp']],errors='raise',utc=True)
    if (evidence > scheduled).any():
        raise ValueError('source evidence timestamp occurs after scheduled draw time')
    return {
        'schema':'SMART_PROCEDURAL_SIGNAL_INPUT_VALIDATION_V1',
        'status':'PASS','rows':int(len(df)),'contest_min':int(contests.iloc[0]),
        'contest_max':int(contests.iloc[-1]),'forbidden_fields_present':False,
        'pre_draw_timestamp_gate':True
    }

def validate_file(path: str|Path) -> dict:
    p=Path(path)
    if p.suffix.lower()=='.csv': df=pd.read_csv(p)
    elif p.suffix.lower()=='.xlsx': df=pd.read_excel(p)
    else: raise ValueError('use CSV or XLSX')
    out=validate_frame(df); out['file']=p.name; out['sha256']=sha256_file(p); return out

__all__=['validate_frame','validate_file']
