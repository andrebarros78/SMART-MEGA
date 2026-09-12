from pathlib import Path
ROOT=Path(r'C:\New Projet\SMART-MEGA')
changed=[]
for p in ROOT.glob('*.py'):
    raw=p.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        text=raw.decode('utf-8-sig')
        p.write_text(text,encoding='utf-8')
        changed.append(p.name)
a=ROOT/'smart_independent_audit.py'
s=a.read_text(encoding='utf-8')
s=s.replace("source.read_text(encoding='utf-8')", "source.read_text(encoding='utf-8-sig')", 1)
a.write_text(s,encoding='utf-8')
print('NORMALIZED',changed)
