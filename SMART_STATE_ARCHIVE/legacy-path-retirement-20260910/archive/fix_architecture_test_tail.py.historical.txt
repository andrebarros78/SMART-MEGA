from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_architecture_alignment.py')
s=p.read_text(encoding='utf-8-sig')
marker='def test_governance_rejects_out_of_order_ledger_before_sorting():'
pos=s.find(marker)
if pos < 0:
    raise SystemExit('marker missing')
s=s[:pos]+'''def test_governance_rejects_out_of_order_ledger_before_sorting():
    text = (ROOT / 'smart_v2_production.py').read_text(encoding='utf-8-sig')
    assert "if contests != sorted(contests):" in text
    assert 'valid.sort()' not in text
    assert "legacy_production_authority_disabled'" in text
    assert "P15 evidence-only promotion is required" in text
'''
p.write_text(s,encoding='utf-8')
print('ARCHITECTURE_TEST_TAIL_FIXED')
