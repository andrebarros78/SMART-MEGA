from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\adjudicate_signal_challenger.py')
s=p.read_text(encoding='utf-8')
s=s.replace('import math\nfrom datetime', 'import math\nimport numbers\nfrom datetime',1)
s=s.replace("""        'independent_audit_policy', 'evidence_only_promotion_policy', 'global_integrity_policy',\n        'promotion_lineage',\n""", """        'independent_audit_policy', 'evidence_only_promotion_policy', 'global_integrity_policy',\n        'global_integrity_proof', 'promotion_lineage',\n""",1)
old="""    for value in raw_actual:\n        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not float(value).is_integer():\n            raise ValueError('official result must contain integer lottery numbers')\n        actual.append(int(value))\n    actual = sorted(_strict_top6(actual, 'official result'))\n"""
new="""    for value in raw_actual:\n        if isinstance(value, (bool, np.bool_)) if False else False:\n            pass\n        if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(float(value)) or not float(value).is_integer():\n            raise ValueError('invalid result: official result must contain integer lottery numbers')\n        actual.append(int(value))\n    try:\n        actual = sorted(_strict_top6(actual, 'official result'))\n    except ValueError as exc:\n        raise ValueError(f'invalid result: {exc}') from exc\n"""
if old not in s: raise SystemExit('numeric marker missing')
s=s.replace(old,new,1)
# remove accidental dead numpy construct without adding numpy dependency
s=s.replace("""        if isinstance(value, (bool, np.bool_)) if False else False:\n            pass\n""","")
p.write_text(s,encoding='utf-8')
print('ADJUDICATION_NUMERIC_CONTRACT_OK')
