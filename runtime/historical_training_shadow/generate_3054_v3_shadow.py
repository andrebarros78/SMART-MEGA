from __future__ import annotations
import hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from smart_signal_agent import SmartSignalAgent
from smart_v2_engine import load_draws

DATA=ROOT/'runtime/historical_training_shadow/Mega-Sena_uploaded_2026-09-05.xlsx'
OUT=ROOT/'SMART_3054_SHADOW_V3_FREEZE.json'
V2=ROOT/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def git_head()->str:
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()

def main():
    draws, contests=load_draws(DATA)
    if int(contests[-1])!=3053: raise ValueError(f'dataset must end at 3053, got {int(contests[-1])}')
    if 3054 in set(int(x) for x in contests): raise ValueError('future leakage: contest 3054 present in source')
    data_hash=sha256_file(DATA)
    v2_hash_before=sha256_file(V2)
    agent=SmartSignalAgent(start=1000)
    pred, backtest=agent.predict_next(draws,contests,target_contest=3054,cutoff_timestamp='2026-09-05T08:04:00-03:00',cutoff_timestamp_kind='shadow_freeze_generated_before_official_result')
    state=agent.state_document(data_sha256=data_hash)
    doc={
      'schema':'SMART_3054_SHADOW_V3_FREEZE_1',
      'mode':'SHADOW_ONLY_NON_PRODUCTION',
      'target_contest':3054,
      'cutoff_contest':3053,
      'generated_at_brasilia':'2026-09-05T08:04:00-03:00',
      'source_dataset':str(DATA.relative_to(ROOT)),
      'source_sha256':data_hash,
      'source_last_contest':int(contests[-1]),
      'future_leakage_3054_present':False,
      'git_head':git_head(),
      'architecture_context_calibration_id':state['context_regime']['calibration_id'],
      'architecture_rank_calibration_mode':state['rank_score_calibration']['calibration_mode'],
      'architecture_meta_governor':state['meta_governor'],
      'top6':list(pred.top6),
      'ranking60':list(pred.ranking60),
      'weights':pred.weights,
      'context_state':pred.context_state,
      'rank_score_calibration':pred.rank_score_calibration,
      'multi_challengers':pred.multi_challengers,
      'meta_governor':pred.meta_governor,
      'backtest_total_hits':int(backtest['total_hits']),
      'backtest_mean_hits':float(backtest['mean_hits']),
      'uniform_expected_hits':float(backtest['uniform_expected_hits']),
      'v2_freeze_sha256_before':v2_hash_before,
      'production_authority':False,
      'terminal_authority':False,
      'immutable_intent':'compare V3 shadow against V2 original and official 3054 result without replacing V2'
    }
    raw=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    doc['document_sha256']=hashlib.sha256(raw).hexdigest()
    OUT.write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf-8')
    v2_hash_after=sha256_file(V2)
    if v2_hash_after!=v2_hash_before: raise RuntimeError('V2 freeze changed during V3 generation')
    print(json.dumps({'status':'PASS','top6':doc['top6'],'document_sha256':doc['document_sha256'],'source_sha256':data_hash,'git_head':doc['git_head'],'v2_unchanged':True,'backtest_total_hits':doc['backtest_total_hits'],'context_calibration_id':doc['architecture_context_calibration_id']},indent=2,ensure_ascii=False))
if __name__=='__main__': main()
