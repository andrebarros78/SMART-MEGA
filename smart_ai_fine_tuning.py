from __future__ import annotations
import hashlib,json,math
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any
import smart_v2_engine as e
from smart_contextual_meta_weights import DEFAULT_META_STRENGTH
from smart_signal_agent import SmartSignalAgent
from smart_signal_redundancy_consensus import DEFAULT_CORRELATION_THRESHOLD
SCHEMA='SMART_AI_FINE_TUNING_1'; AUTHORITY_SCHEMA='SMART_AI_HYPERPARAMETER_AUTHORITY_1'
REPORT_PATH=Path('SMART_AI_FINE_TUNING_CURRENT.json'); AUTHORITY_PATH=Path('SMART_AI_HYPERPARAMETERS.json')
DEFAULT_START=1000; CALIBRATION_RANGE=(1500,2499); VALIDATION_RANGE=(2500,2850); HOLDOUT_START=2851

def sha256_json(obj:Any)->str:
 raw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); return hashlib.sha256(raw).hexdigest()
def sha256_file(path:Path)->str:
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()
@dataclass(frozen=True)
class Candidate:
 candidate_id:str; eta:float; redundancy_threshold:float; meta_strength:float
 def validate(self):
  vals=(self.eta,self.redundancy_threshold,self.meta_strength)
  if any(not math.isfinite(float(x)) for x in vals): raise ValueError('fine-tuning candidate values must be finite')
  if self.eta<=0: raise ValueError('eta must be positive')
  if not .50<=self.redundancy_threshold<=.99: raise ValueError('redundancy_threshold out of safe range')
  if not 0<=self.meta_strength<=.25: raise ValueError('meta_strength out of safe range')
def candidate_space()->list[Candidate]:
 b=math.log(2); r=float(DEFAULT_CORRELATION_THRESHOLD); m=float(DEFAULT_META_STRENGTH)
 rows=[Candidate('baseline',b,r,m),Candidate('eta_050x',b*.5,r,m),Candidate('eta_075x',b*.75,r,m),Candidate('eta_125x',b*1.25,r,m),Candidate('redundancy_080',b,.80,m),Candidate('redundancy_075',b,.75,m),Candidate('meta_000',b,r,0),Candidate('meta_030',b,r,.03),Candidate('meta_090',b,r,.09),Candidate('meta_120',b,r,.12)]
 for x in rows:x.validate()
 return rows
def _summary(rows,lo,hi):
 a=[r for r in rows if lo<=int(r['contest'])<=hi]; hits=sum(int(r['challenger_hits']) for r in a); n=len(a)
 return {'start':int(lo),'end':int(hi),'n':n,'hits':int(hits),'mean_hits':float(hits/n) if n else 0.0}
def _evaluate_one(args):
 c,data_file,target,start=args; c.validate(); draws,contests=e.load_draws(Path(data_file)); cutoff=int(contests[-1])
 if int(target)!=cutoff+1: raise ValueError('fine-tuning target must be cutoff+1')
 agent=SmartSignalAgent(start=int(start),eta=float(c.eta),redundancy_threshold=float(c.redundancy_threshold),meta_strength=float(c.meta_strength),calibration_strength=0.0,marginal_strength=0.0)
 pred,bt=agent.predict_next(draws,contests,target_contest=int(target)); rows=list(bt['rows'])
 decisions={str(int(r['contest'])):[int(x) for x in r['challenger_top6']] for r in rows}
 return {'candidate':asdict(c),'calibration':_summary(rows,CALIBRATION_RANGE[0],min(CALIBRATION_RANGE[1],cutoff)),'validation':_summary(rows,VALIDATION_RANGE[0],min(VALIDATION_RANGE[1],cutoff)),'holdout':_summary(rows,HOLDOUT_START,cutoff),'global':_summary(rows,int(contests[int(start)]),cutoff),'next_top6':[int(x) for x in pred.top6],'architecture_profile':str(agent.architecture_profile),'effective_redundancy_threshold':float(agent.redundancy_threshold),'decisions':decisions}
def _rank_key(row,stage):
 s=row[stage]; return (int(s['hits']),float(s['mean_hits']),1 if row['candidate']['candidate_id']=='baseline' else 0)
def select_without_holdout(results):
 if not results or not any(r['candidate']['candidate_id']=='baseline' for r in results): raise ValueError('fine-tuning results require baseline')
 ranked=sorted(results,key=lambda r:_rank_key(r,'calibration'),reverse=True); best=int(ranked[0]['calibration']['hits'])
 shortlist=[r for r in ranked if int(r['calibration']['hits'])>=best-1][:4]
 selected=max(shortlist,key=lambda r:_rank_key(r,'validation'))
 return {'shortlist_ids':[r['candidate']['candidate_id'] for r in shortlist],'selected_candidate_id':selected['candidate']['candidate_id'],'selection_stages':['calibration','validation'],'holdout_used_for_selection':False}
def _decision_change_count(a,b):
 keys=sorted(set(a['decisions'])&set(b['decisions']),key=int); return sum(a['decisions'][k]!=b['decisions'][k] for k in keys)
def adjudicate_selected(results,selection):
 by={r['candidate']['candidate_id']:r for r in results}; base=by['baseline']; sel=by[str(selection['selected_candidate_id'])]
 gains={k:int(sel[k]['hits'])-int(base[k]['hits']) for k in ('calibration','validation','holdout','global')}; changes=int(_decision_change_count(sel,base))
 nonreg=all(gains[k]>=0 for k in gains); promoted=bool(sel['candidate']['candidate_id']!='baseline' and nonreg and gains['validation']>0 and max(gains.values())>0 and changes>0)
 return {'selected_candidate_id':sel['candidate']['candidate_id'],'baseline_candidate_id':'baseline','gains_vs_baseline':gains,'decision_change_count':changes,'material_decision_effect':changes>0,'non_regressive_all_partitions':nonreg,'positive_validation_gain_required':True,'holdout_used_only_for_final_acceptance':True,'promotion_authorized':promoted,'status':'PROMOTED' if promoted else 'BASELINE_RETAINED_NO_PROVEN_GAIN','effective_candidate_id':sel['candidate']['candidate_id'] if promoted else 'baseline'}
def build_authority(report):
 if report.get('schema')!=SCHEMA or report.get('status')!='PASS': raise ValueError('fine-tuning report must be PASS')
 by={r['candidate']['candidate_id']:r for r in report['results']}; effective=by[report['adjudication']['effective_candidate_id']]
 obj={'schema':AUTHORITY_SCHEMA,'status':'AUTHORIZED' if report['adjudication']['promotion_authorized'] else 'BASELINE_RETAINED','target_contest':int(report['target_contest']),'cutoff_contest':int(report['cutoff_contest']),'data_sha256':str(report['data_sha256']),'fine_tuning_report_sha256':str(report['sha256']),'fine_tuning_report_file_sha256':None,'effective_candidate':effective['candidate'],'promotion_authorized':bool(report['adjudication']['promotion_authorized']),'causal_partitioning':True,'holdout_used_for_selection':False,'future_result_used':False}
 obj['sha256']=sha256_json(obj); return obj
def load_authority(path:Path,*,target_contest:int,data_sha256:str|None=None):
 p=Path(path)
 if not p.is_file(): return None
 obj=json.loads(p.read_text(encoding='utf-8')); canonical=dict(obj); observed=canonical.pop('sha256',None)
 if obj.get('schema')!=AUTHORITY_SCHEMA: raise ValueError('AI fine-tuning authority schema invalid')
 if not isinstance(observed,str) or observed!=sha256_json(canonical): raise ValueError('AI fine-tuning authority self-hash invalid')
 if int(obj.get('target_contest',-1))!=int(target_contest): raise ValueError('AI fine-tuning authority target mismatch')
 if data_sha256 is not None and obj.get('data_sha256')!=data_sha256: raise ValueError('AI fine-tuning authority data mismatch')
 Candidate(**obj.get('effective_candidate',{})).validate()
 if obj.get('future_result_used') is not False or obj.get('holdout_used_for_selection') is not False: raise ValueError('AI fine-tuning authority violates causal partitioning')
 return obj
def run_fine_tuning(data_file:Path,target_contest:int,*,start:int=DEFAULT_START,max_workers:int=4,candidates:list[Candidate]|None=None):
 data_file=Path(data_file).resolve(); draws,contests=e.load_draws(data_file); cutoff=int(contests[-1]); target=int(target_contest)
 if target!=cutoff+1: raise ValueError('fine-tuning target must be cutoff+1')
 if cutoff<HOLDOUT_START: raise ValueError('insufficient history for canonical fine-tuning partitions')
 candidates=list(candidates or candidate_space()); ids=[c.candidate_id for c in candidates]
 if len(ids)!=len(set(ids)) or 'baseline' not in ids: raise ValueError('candidate IDs must be unique and include baseline')
 work=[(c,str(data_file),target,int(start)) for c in candidates]; results=[]; workers=max(1,min(int(max_workers),len(work)))
 if workers==1: results=[_evaluate_one(x) for x in work]
 else:
  with ProcessPoolExecutor(max_workers=workers) as pool:
   futs={pool.submit(_evaluate_one,x):x[0].candidate_id for x in work}
   for fut in as_completed(futs): results.append(fut.result())
 results.sort(key=lambda r:ids.index(r['candidate']['candidate_id'])); selection=select_without_holdout(results); adjudication=adjudicate_selected(results,selection)
 persisted=[]
 for row in results:
  clean=dict(row); clean['decision_trace_sha256']=sha256_json(clean.pop('decisions')); persisted.append(clean)
 report={'schema':SCHEMA,'status':'PASS','target_contest':target,'cutoff_contest':cutoff,'data_file':str(data_file),'data_sha256':sha256_file(data_file),'start':int(start),'partitions':{'calibration':list(CALIBRATION_RANGE),'validation':list(VALIDATION_RANGE),'holdout':[HOLDOUT_START,cutoff]},'candidate_count':len(candidates),'selection':selection,'adjudication':adjudication,'results':persisted,'guardrails':{'future_result_used':False,'holdout_used_for_selection':False,'test_result_hyperparameter_selection_prohibited':True,'baseline_wins_exact_ties':True,'promotion_requires_material_decision_change':True,'promotion_requires_non_regression_all_partitions':True,'promotion_requires_positive_validation_gain':True}}
 report['sha256']=sha256_json(report); return report
def write_report_and_authority(report,report_path:Path=REPORT_PATH,authority_path:Path=AUTHORITY_PATH):
 canonical=dict(report); observed=canonical.pop('sha256',None)
 if observed!=sha256_json(canonical): raise ValueError('fine-tuning report self-hash invalid')
 report_path=Path(report_path); authority_path=Path(authority_path); report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 authority=build_authority(report); authority['fine_tuning_report_file_sha256']=sha256_file(report_path); authority.pop('sha256',None); authority['sha256']=sha256_json(authority); authority_path.write_text(json.dumps(authority,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return sha256_file(report_path),sha256_file(authority_path)
def main():
 import argparse
 ap=argparse.ArgumentParser(); ap.add_argument('data_file'); ap.add_argument('--target',type=int,required=True); ap.add_argument('--start',type=int,default=DEFAULT_START); ap.add_argument('--workers',type=int,default=4); a=ap.parse_args()
 r=run_fine_tuning(Path(a.data_file),a.target,start=a.start,max_workers=a.workers); rh,ah=write_report_and_authority(r)
 print(json.dumps({'status':r['status'],'candidate_count':r['candidate_count'],'selection':r['selection'],'adjudication':r['adjudication'],'report_sha256':rh,'authority_sha256':ah},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
