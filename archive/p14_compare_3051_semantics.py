from pathlib import Path
import pandas as pd, json, hashlib
ROOT=Path(__file__).resolve().parents[1]
a=pd.read_excel(ROOT/'Mega-Sena_through_3050.xlsx')
b=pd.read_excel(ROOT/'Mega-Sena_through_3051.xlsx')
bp=b.iloc[:len(a)].copy()

def norm_df(df):
    out=df.copy()
    for c in out.columns:
        s=out[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            out[c]=s.dt.strftime('%Y-%m-%dT%H:%M:%S').where(s.notna(), None)
        else:
            out[c]=s.astype(object).where(s.notna(), None)
            out[c]=out[c].map(lambda v: int(v) if isinstance(v,float) and v.is_integer() else v)
    return out
na=norm_df(a); nb=norm_df(bp)
mask=~(na.eq(nb) | (na.isna() & nb.isna()))
per=mask.sum().astype(int).to_dict()
coords=list(zip(*mask.to_numpy().nonzero()))[:40]
examples=[]
for i,j in coords:
    c=na.columns[j]
    examples.append({'row':int(i),'contest':na.iloc[i]['Concurso'],'col':c,'a':repr(na.iloc[i,j]),'b':repr(nb.iloc[i,j])})
essential=['Concurso']+[f'Bola{i}' for i in range(1,7)]
def rows(df,cols): return [[df.iloc[i][c] for c in cols] for i in range(len(df))]
def h(obj): return hashlib.sha256(json.dumps(obj,ensure_ascii=False,separators=(',',':'),default=str).encode()).hexdigest()
row3051=norm_df(b.iloc[[len(a)]])[essential].iloc[0].to_dict()
print(json.dumps({
 'rows_a':len(a),'rows_b':len(b),'columns_equal':list(a.columns)==list(b.columns),
 'diff_total':int(mask.to_numpy().sum()),'diff_by_column':{k:int(v) for k,v in per.items() if v},
 'diff_examples':examples,
 'essential_prefix_equal':na[essential].equals(nb[essential]),
 'essential_sha_a':h(rows(na,essential)),
 'essential_sha_b_prefix':h(rows(nb,essential)),
 'all_semantic_sha_a':h(rows(na,list(na.columns))),
 'all_semantic_sha_b_prefix':h(rows(nb,list(nb.columns))),
 'row3051':row3051,
},ensure_ascii=False,indent=2,default=str))
