from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import smart_independent_audit as ia
report=ia.run_independent_audit(
    ROOT,
    ROOT/'SMART_SIGNAL_LEDGER.json',
    [
      ROOT/'SMART_P14_COVERAGE_BINDING_AUDIT.json',
      ROOT/'SMART_P14_COVERAGE_BINDING_ORCHESTRATOR.json',
      ROOT/'SMART_P14_COVERAGE_BINDING_PROMOTION.json',
      ROOT/'SMART_P14_COVERAGE_BINDING_EVIDENCE_ONLY.json',
    ],
    ROOT/'Mega-Sena_through_3050.xlsx',
    3051,
    start=1000,
)
out=ROOT/'SMART_P14_INDEPENDENT_AUDIT_CURRENT.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({
  'status':report['status'],
  'sha256':report['sha256'],
  'coverage_bindings':report['coverage']['count'],
  'pair_count':report['prospective_ledger']['pair_count'],
  'comparison':report['prospective_ledger']['full_champion_comparison'],
  'deterministic':report['deterministic_replay']['deterministic'],
  'no_future_leakage':report['prospective_ledger']['no_future_leakage'],
},ensure_ascii=False,indent=2))

