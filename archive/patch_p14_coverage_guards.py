from pathlib import Path
p=Path(__file__).resolve().parents[1]/'smart_independent_audit.py'
s=p.read_text(encoding='utf-8')
old="""        contests = pre_df['Concurso'].astype(int)
        if len(pre_df) == 0 or int(contests.iloc[-1]) != cutoff or int(contests.max()) != cutoff:
            raise ValueError('frozen dataset does not end at causal cutoff')
        if int(target) in set(contests.tolist()):
            raise ValueError('future result leaked into frozen dataset')
"""
new="""        contests = pre_df['Concurso'].astype(int)
        if int(target) in set(contests.tolist()):
            raise ValueError('future result leaked into frozen dataset')
        if len(pre_df) == 0 or int(contests.iloc[-1]) != cutoff or int(contests.max()) != cutoff:
            raise ValueError('frozen dataset does not end at causal cutoff')
"""
if old not in s:
    raise SystemExit('leakage reorder marker missing')
p.write_text(s.replace(old,new,1),encoding='utf-8')
print('P14 leakage guard reordered')
