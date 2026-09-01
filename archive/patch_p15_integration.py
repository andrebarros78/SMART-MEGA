from pathlib import Path

p=Path(__file__).resolve().parents[1]/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8')

old="from smart_promotion_gate import (\n    BASE_MIN_PROSPECTIVE_CONTESTS, MIN_E_VALUE, assess_promotion_records, policy_snapshot\n)\n"
new="from smart_promotion_gate import (\n    BASE_MIN_PROSPECTIVE_CONTESTS, MIN_E_VALUE, assess_promotion_records, policy_snapshot\n)\nfrom smart_evidence_only_promotion import (\n    assess_evidence_only_promotion_from_files,\n    policy_snapshot as evidence_only_promotion_policy_snapshot,\n)\n"
if new not in s:
    if old not in s: raise SystemExit('import marker missing')
    s=s.replace(old,new,1)

old="PRE_3052_GATE_SCHEMA = 'SMART_3052_IMPLEMENTATION_GATE_1'\n"
new="PRE_3052_GATE_SCHEMA = 'SMART_3052_IMPLEMENTATION_GATE_1'\nP14_AUDIT_REPORT_PATH = Path('SMART_P14_INDEPENDENT_AUDIT_CURRENT.json')\n"
if new not in s:
    if old not in s: raise SystemExit('constant marker missing')
    s=s.replace(old,new,1)

old="def promotion_status(ledger: dict[str, Any]) -> dict[str, Any]:\n"
new="def promotion_eligibility_status(ledger: dict[str, Any]) -> dict[str, Any]:\n"
if new not in s:
    if old not in s: raise SystemExit('promotion function marker missing')
    s=s.replace(old,new,1)

marker="    return assess_promotion_records(records, ev)\n\n\ndef _next_version_path(out: Path) -> Path:\n"
insert="    return assess_promotion_records(records, ev)\n\n\ndef promotion_status(ledger: dict[str, Any], gate_path: Path = PRE_3052_GATE_PATH,\n                     audit_report_path: Path = P14_AUDIT_REPORT_PATH) -> dict[str, Any]:\n    p13 = promotion_eligibility_status(ledger)\n    return assess_evidence_only_promotion_from_files(p13, gate_path, audit_report_path)\n\n\ndef _next_version_path(out: Path) -> Path:\n"
if insert not in s:
    if marker not in s: raise SystemExit('promotion wrapper marker missing')
    s=s.replace(marker,insert,1)

old="        'independent_audit': sha256(Path('smart_independent_audit.py')),\n"
new="        'independent_audit': sha256(Path('smart_independent_audit.py')),\n        'evidence_only_promotion': sha256(Path('smart_evidence_only_promotion.py')),\n"
if new not in s:
    if old not in s: raise SystemExit('component hash marker missing')
    s=s.replace(old,new,1)

old="    independent_audit_snapshot = independent_audit_policy_snapshot()\n"
new="    independent_audit_snapshot = independent_audit_policy_snapshot()\n    evidence_only_promotion_snapshot = evidence_only_promotion_policy_snapshot()\n"
if new not in s:
    if old not in s: raise SystemExit('snapshot marker missing')
    s=s.replace(old,new,1)

old="        'independent_audit_sha256': component_hashes['independent_audit'],\n"
new="        'independent_audit_sha256': component_hashes['independent_audit'],\n        'evidence_only_promotion_sha256': component_hashes['evidence_only_promotion'],\n"
if new not in s:
    if old not in s: raise SystemExit('freeze hash marker missing')
    s=s.replace(old,new,1)

old="        'independent_audit_policy': independent_audit_snapshot,\n"
new="        'independent_audit_policy': independent_audit_snapshot,\n        'evidence_only_promotion_policy': evidence_only_promotion_snapshot,\n"
if new not in s:
    if old not in s: raise SystemExit('freeze policy marker missing')
    s=s.replace(old,new,1)

old="                     'independent_audit_policy': freeze_obj['independent_audit_policy']},\n"
new="                     'independent_audit_policy': freeze_obj['independent_audit_policy'],\n                     'evidence_only_promotion_policy': freeze_obj['evidence_only_promotion_policy']},\n"
if new not in s:
    if old not in s: raise SystemExit('ledger snapshot marker missing')
    s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')
print('P15 integration patched')
