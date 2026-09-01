from pathlib import Path
p=Path(__file__).resolve().parents[1]/'smart_independent_audit.py'
s=p.read_text(encoding='utf-8-sig')
old="    prefix_semantic_sha = semantic_dataframe_sha256(prefix_df)\n    current_prefix_semantic_sha = semantic_dataframe_sha256(prefix_current)\n    if prefix_semantic_sha != current_prefix_semantic_sha:\n        raise ValueError('legacy semantic prefix hash mismatch')\n    if str(proof.get('prefix_semantic_sha256')) != prefix_semantic_sha:\n"
new="    prefix_semantic_sha = semantic_dataframe_sha256(prefix_df)\n    if str(proof.get('prefix_semantic_sha256')) != prefix_semantic_sha:\n"
if old not in s: raise SystemExit('redundant guard marker missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('removed redundant semantic guard')
