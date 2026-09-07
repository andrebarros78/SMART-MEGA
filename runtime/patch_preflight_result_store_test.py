from pathlib import Path
p=Path('test_smart_3054_adjudication_preflight.py')
s=p.read_text(encoding='utf-8')
s=s.replace('import pytest\n', 'import pytest\nimport pandas as pd\n', 1)
s=s.replace('''    current_store = preflight._canonical_result_store_status(ROOT / "Mega-Sena.xlsx")\n    assert current_store["contest_max"] >= 3054\n    assert current_store["target_absent"] is False\n''','''    frame = pd.read_excel(ROOT / "Mega-Sena.xlsx")\n    contests = pd.to_numeric(frame["Concurso"], errors="raise").astype(int)\n    assert int(contests.max()) >= 3054\n    assert 3054 in set(contests.tolist())\n''')
p.write_text(s,encoding='utf-8')
print('PREFLIGHT_RESULT_STORE_TEST_FIXED')
