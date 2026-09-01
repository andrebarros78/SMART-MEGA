from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_independent_audit.py'
s=p.read_text(encoding='utf-8')
old="""    champion = list(actual[:1]) + [n for n in [1, 2, 3, 4, 5, 6, 7] if n not in actual][:5]
    challenger = list(actual[-1:]) + [n for n in [54, 55, 56, 57, 58, 59, 60] if n not in actual][:5]
    champion = champion[:6]
    challenger = challenger[:6]
"""
new="""    champion = [actual[0]] + [n for n in range(1, 61) if n not in actual and n != actual[0]][:5]
    challenger = [actual[-1]] + [n for n in range(60, 0, -1) if n not in actual and n != actual[-1]][:5]
"""
if old not in s:
    raise SystemExit('fixture marker missing')
p.write_text(s.replace(old,new,1),encoding='utf-8')
print('P14 fixture fixed')
