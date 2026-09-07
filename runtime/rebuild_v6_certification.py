from __future__ import annotations
import json
from pathlib import Path
import smart_independent_audit as ia
import smart_global_integrity as gi
import smart_continuous_red_team as rt

ROOT=Path(r'C:\New Projet\SMART-MEGA').resolve()
COV=ROOT/'runtime'/'SMART_COVERAGE_FULL_CLOSURE.json'
JUNIT=ROOT/'SMART_AUDIT_JUNIT_CURRENT.xml'
GATE=ROOT/'SMART_3052_IMPLEMENTATION_GATE.json'
P14=ROOT/'SMART_P14_INDEPENDENT_AUDIT_CURRENT.json'
GLOBAL=ROOT/'SMART_GLOBAL_INTEGRITY_PROOF.json'
DATA=ROOT/'Mega-Sena_through_3053_v2.xlsx'
LEDGER=ROOT/'SMART_SIGNAL_LEDGER.json'
BINDINGS={
    'SMART_P14_COVERAGE_BINDING_AUDIT.json':'smart_independent_audit.py',
    'SMART_P14_COVERAGE_BINDING_ORCHESTRATOR.json':'smart_champion_challenger.py',
    'SMART_P14_COVERAGE_BINDING_PROMOTION.json':'smart_promotion_gate.py',
    'SMART_P14_COVERAGE_BINDING_EVIDENCE_ONLY.json':'smart_evidence_only_promotion.py',
}

def write_json(path:Path,obj:dict)->None:
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    if not COV.is_file(): raise SystemExit('coverage report missing')
    cov=json.loads(COV.read_text(encoding='utf-8'))
    files=cov.get('files',{})
    required=set(gi.REQUIRED_GLOBAL_COVERAGE_SOURCES)
    if set(files) != required:
        raise SystemExit(f'coverage source set mismatch missing={sorted(required-set(files))} extra={sorted(set(files)-required)}')
    bad=[]
    for source in gi.REQUIRED_GLOBAL_COVERAGE_SOURCES:
        s=files[source]['summary']
        if int(s.get('missing_lines',-1)) or int(s.get('missing_branches',-1)) or int(s.get('covered_lines',-1))!=int(s.get('num_statements',-2)) or int(s.get('covered_branches',-1))!=int(s.get('num_branches',-2)):
            bad.append(source)
    if bad: raise SystemExit(f'coverage incomplete: {bad}')
    red=rt.verify_latest_report(ROOT/'SMART_P09_RED_TEAM_LATEST.json',ROOT)
    binding_paths=[]
    cov_rel=str(COV.relative_to(ROOT)).replace('\\','/')
    cov_hash=ia.sha256_file(COV)
    for name,source in BINDINGS.items():
        p=ROOT/name
        obj={
            'schema':ia.COVERAGE_BINDING_SCHEMA,
            'source_file':source,
            'source_sha256':ia.sha256_file(ROOT/source),
            'coverage_report_file':cov_rel,
            'coverage_report_sha256':cov_hash,
            'coverage_file_key':source,
            'required':'100% lines + branches',
        }
        write_json(p,obj); binding_paths.append(p)
        ia.audit_coverage_binding(ROOT,p)
    report=ia.run_independent_audit(ROOT,LEDGER,binding_paths,DATA,3054,start=1000)
    if report.get('status')!='PASS': raise SystemExit('P14 not PASS')
    write_json(P14,report)
    gi.validate_p14_report(ROOT)
    if not JUNIT.is_file(): raise SystemExit('fresh junit missing')
    gate=json.loads(GATE.read_text(encoding='utf-8'))
    specs=[(cov_rel,source) for source in gi.REQUIRED_GLOBAL_COVERAGE_SOURCES]
    proof=gi.build_global_integrity_proof(ROOT,gate,JUNIT,specs)
    write_json(GLOBAL,proof)
    gate['global_integrity']={'file':GLOBAL.name,'sha256':gi.sha256_file(GLOBAL),'status':'PASS','material_deficiencies':[]}
    write_json(GATE,gate)
    verified=gi.verify_global_integrity(ROOT,GATE,GLOBAL)
    print(json.dumps({
      'status':'PASS','coverage_sources':len(required),'red_team':red,'p14_sha256':report.get('sha256'),
      'global_proof_sha256':gi.sha256_file(GLOBAL),'gate_sha256':gi.sha256_file(GATE),'verify':verified
    },ensure_ascii=False,indent=2))
if __name__=='__main__': main()
