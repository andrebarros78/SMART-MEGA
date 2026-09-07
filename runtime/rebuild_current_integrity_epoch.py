from __future__ import annotations
import json, os, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import smart_independent_audit as ia
import smart_global_integrity as gi
import smart_continuous_red_team as rt
ROOT=Path(r'C:\New Projet\SMART-MEGA').resolve()
COV=ROOT/'SMART_COVERAGE_GLOBAL_CURRENT.json'
JUNIT=ROOT/'SMART_AUDIT_JUNIT_CURRENT.xml'
GATE=ROOT/'SMART_3052_IMPLEMENTATION_GATE.json'
P14=ROOT/'SMART_P14_INDEPENDENT_AUDIT_CURRENT.json'
GLOBAL=ROOT/'SMART_GLOBAL_INTEGRITY_PROOF.json'
DATA=ROOT/'runtime'/'learning_epochs'/'full-3e8a759590613fdc-01'/'Mega-Sena_cutoff_3053.xlsx'
LEDGER=ROOT/'SMART_SIGNAL_LEDGER.json'
BINDINGS={
 'SMART_P14_COVERAGE_BINDING_AUDIT.json':'smart_independent_audit.py',
 'SMART_P14_COVERAGE_BINDING_ORCHESTRATOR.json':'smart_champion_challenger.py',
 'SMART_P14_COVERAGE_BINDING_PROMOTION.json':'smart_promotion_gate.py',
 'SMART_P14_COVERAGE_BINDING_EVIDENCE_ONLY.json':'smart_evidence_only_promotion.py',
}
def atomic(path,obj):
 path=Path(path); fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent); os.close(fd); t=Path(tmp)
 try:
  t.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(t,path)
 finally:
  if t.exists(): t.unlink()
def main():
 cov=json.loads(COV.read_text(encoding='utf-8'))
 req=set(gi.REQUIRED_GLOBAL_COVERAGE_SOURCES); files=set(cov.get('files',{}))
 if files!=req: raise RuntimeError(f'coverage set mismatch missing={sorted(req-files)} extra={sorted(files-req)}')
 for src in req:
  s=cov['files'][src]['summary']
  if any(int(s.get(k,-1))!=0 for k in ('missing_lines','missing_branches')): raise RuntimeError(f'coverage incomplete {src}: {s}')
  if int(s['covered_lines'])!=int(s['num_statements']) or int(s['covered_branches'])!=int(s['num_branches']): raise RuntimeError(f'coverage mismatch {src}')
 red=rt.verify_latest_report(ROOT/'SMART_P09_RED_TEAM_LATEST.json',ROOT)
 if red.get('status')!='PASS': raise RuntimeError('red team stale')
 cov_hash=ia.sha256_file(COV); binding_paths=[]
 for name,src in BINDINGS.items():
  obj={'schema':ia.COVERAGE_BINDING_SCHEMA,'source_file':src,'source_sha256':ia.sha256_file(ROOT/src),'coverage_report_file':COV.name,'coverage_report_sha256':cov_hash,'coverage_file_key':src,'required':'100% lines + branches'}
  p=ROOT/name; atomic(p,obj); ia.audit_coverage_binding(ROOT,p); binding_paths.append(p)
 report=ia.run_independent_audit(ROOT,LEDGER,binding_paths,DATA,3054,start=1000)
 if report.get('status')!='PASS': raise RuntimeError('P14 FAIL')
 atomic(P14,report)
 p14v=gi.validate_p14_report(ROOT)
 gate=json.loads(GATE.read_text(encoding='utf-8'))
 specs=[(COV.name,src) for src in gi.REQUIRED_GLOBAL_COVERAGE_SOURCES]
 proof=gi.build_global_integrity_proof(ROOT,gate,JUNIT,specs)
 atomic(GLOBAL,proof)
 gate['global_integrity']={'file':GLOBAL.name,'sha256':gi.sha256_file(GLOBAL),'status':'PASS','material_deficiencies':[]}
 atomic(GATE,gate)
 verified=gi.verify_global_integrity(ROOT,GATE,GLOBAL)
 print(json.dumps({'status':'PASS','p14_file_sha256':ia.sha256_file(P14),'p14_self_sha256':report['sha256'],'p14_pairs':report['prospective_ledger']['pair_count'],'replay_data':report['deterministic_replay']['data_file'],'replay_data_sha256':report['deterministic_replay']['data_sha256'],'independent_oracle':report['deterministic_replay']['independent_decision_oracle'],'registry_open':len(report['material_deficiencies']),'global_file_sha256':gi.sha256_file(GLOBAL),'global_self_sha256':proof['sha256'],'gate_file_sha256':gi.sha256_file(GATE),'junit':proof['full_regression'],'verify':verified},ensure_ascii=False,indent=2))
if __name__=='__main__': main()

