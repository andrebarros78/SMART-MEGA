from pathlib import Path
p=Path(__file__).resolve().with_name('p11_validation.py')
s=p.read_text(encoding='utf-8')
if "sys.path.insert" not in s:
    s=s.replace("from pathlib import Path\nimport json, hashlib\n", "from pathlib import Path\nimport json, hashlib, sys\nROOT=Path(__file__).resolve().parents[1]\nsys.path.insert(0,str(ROOT))\n")
    s=s.replace("ROOT=Path(__file__).resolve().parents[1]\n\ndef run", "\ndef run",1)
p.write_text(s,encoding='utf-8')
print('fixed')
