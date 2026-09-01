from pathlib import Path
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import smart_independent_audit as ia
ROOT=Path(__file__).resolve().parents[1]
ledger=json.loads((ROOT/'SMART_SIGNAL_LEDGER.json').read_text(encoding='utf-8'))
ad=next(ev for ev in ledger['events'] if ev.get('event_type')=='ADJUDICATION' and int(ev.get('target_contest',-1))==3051)
fr=next(ev for ev in ledger['events'] if ev.get('event_type')=='FREEZE' and ev.get('freeze_sha256')==ad.get('freeze_sha256'))
freeze=json.loads((ROOT/fr['freeze_file']).read_text(encoding='utf-8'))
prefix=ROOT/freeze['data_file']
current=ROOT/'Mega-Sena_through_3051.xlsx'
pdf=pd.read_excel(prefix)
cdf=pd.read_excel(current)
if list(pdf.columns)!=list(cdf.columns): raise SystemExit('columns differ')
if len(cdf)!=len(pdf)+1: raise SystemExit('row count mismatch')
if not ia._semantic_frame(pdf).equals(ia._semantic_frame(cdf.iloc[:len(pdf)].copy())): raise SystemExit('semantic prefix mismatch')
actual=ia._contest_numbers(cdf,3051)
stored=sorted(ia._valid_top6(ad['actual_numbers'],'adjudication actual numbers'))
if actual!=stored: raise SystemExit('target result mismatch')
if int(cdf['Concurso'].astype(int).max())!=3051: raise SystemExit('future contest present')
now=datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()
mtime=datetime.fromtimestamp(current.stat().st_mtime, ZoneInfo('America/Sao_Paulo')).isoformat()
obj={
 'schema':ia.LEGACY_CONTINUITY_SCHEMA,
 'created_brt':now,
 'target_contest':3051,
 'scope':'legacy binary XLSX reserialization after adjudication; semantic continuity only; no ledger rewrite',
 'original_adjudicated_result_sha256':ad['result_data_sha256'],
 'current_result_file':current.name,
 'current_result_sha256':ia.sha256_file(current),
 'current_result_modified_brt':mtime,
 'adjudication_created_utc':ad.get('created_utc'),
 'frozen_prefix_file':prefix.name,
 'frozen_prefix_sha256':ia.sha256_file(prefix),
 'frozen_prefix_rows':len(pdf),
 'current_result_rows':len(cdf),
 'columns':list(pdf.columns),
 'prefix_semantic_sha256':ia.semantic_dataframe_sha256(pdf),
 'current_prefix_semantic_sha256':ia.semantic_dataframe_sha256(cdf.iloc[:len(pdf)].copy()),
 'current_semantic_sha256':ia.semantic_dataframe_sha256(cdf),
 'exact_prefix_semantic_equal':True,
 'target_numbers':actual,
 'no_rows_beyond_target':True,
 'ledger_rewritten':False,
 'original_binary_restored':False,
 'exception_permitted_only_for_target_3051':True,
}
out=ROOT/'SMART_P14_LEGACY_RESULT_CONTINUITY_3051.json'
out.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':'WRITTEN','file':out.name,'sha256':ia.sha256_file(out),'prefix_semantic_sha256':obj['prefix_semantic_sha256'],'current_semantic_sha256':obj['current_semantic_sha256'],'current_result_sha256':obj['current_result_sha256']},ensure_ascii=False))
