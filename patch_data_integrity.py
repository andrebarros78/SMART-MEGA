from pathlib import Path
p=Path('smart_v2_engine.py')
s=p.read_text(encoding='utf-8')
old="""    draws=[]; contests=[]
    for _,r in df.iterrows():
        vals=sorted(int(r[c]) for c in cols)
        if len(set(vals))!=6 or vals[0]<1 or vals[-1]>60: raise ValueError('sorteio invalido')
        draws.append(vals); contests.append(int(r['Concurso']))
    return np.asarray(draws,int),np.asarray(contests,int)
"""
new="""    draws=[]; contests=[]
    for _,r in df.iterrows():
        try:
            vals=sorted(int(r[c]) for c in cols); contest=int(r['Concurso'])
        except Exception as exc:
            raise ValueError('linha com dado ausente ou nao inteiro') from exc
        if len(set(vals))!=6 or vals[0]<1 or vals[-1]>60: raise ValueError('sorteio invalido')
        draws.append(vals); contests.append(contest)
    if len(set(contests))!=len(contests): raise ValueError('concurso duplicado')
    if any(b<=a for a,b in zip(contests,contests[1:])): raise ValueError('concursos fora de ordem')
    return np.asarray(draws,int),np.asarray(contests,int)
"""
if old not in s: raise SystemExit('target not found')
p.write_text(s.replace(old,new),encoding='utf-8')
