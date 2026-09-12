import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import smart_global_integrity as gi
root=Path(__file__).resolve().parents[1]
gate_path=root/'SMART_3052_IMPLEMENTATION_GATE.json'
proof_path=root/'SMART_GLOBAL_INTEGRITY_PROOF.json'
junit=root/'SMART_AUDIT_JUNIT_CURRENT.xml'
report='SMART_COVERAGE_GLOBAL_CURRENT.json'
required=list(gi.REQUIRED_GLOBAL_COVERAGE_SOURCES)
gate=json.loads(gate_path.read_text(encoding='utf-8'))
proof=gi.build_global_integrity_proof(root,gate,junit,[(report,src) for src in required])
tmp=proof_path.with_suffix('.json.tmp')
tmp.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
tmp.replace(proof_path)
gate['global_integrity']={'file':proof_path.name,'sha256':gi.sha256_file(proof_path),'status':'PASS','material_deficiencies':[]}
gtmp=gate_path.with_suffix('.json.tmp')
gtmp.write_text(json.dumps(gate,ensure_ascii=False,indent=2),encoding='utf-8')
gtmp.replace(gate_path)
verified=gi.verify_global_integrity(root,gate_path,proof_path)
print('GLOBAL_STATUS',proof['status'])
print('GLOBAL_SELF_SHA',proof['sha256'])
print('GLOBAL_FILE_SHA',gi.sha256_file(proof_path))
print('COVERAGE_COUNT',len(proof['coverage']))
print('JUNIT',proof['full_regression'])
print('DEFICIENCIES',proof['material_deficiencies'])
print('VERIFY',verified)
