from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
p=root/'smart_multi_challengers.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("    for _ in range(len(fams) + 2):\n", "    while True:\n")
s=s.replace("    return _normalize(out)\n\n\ndef _bounded", "\n\ndef _bounded",1)
s=s.replace("        if not members:\n            raise ValueError('empty family is invalid')\n", "")
p.write_text(s,encoding='utf-8')
print('hardened')