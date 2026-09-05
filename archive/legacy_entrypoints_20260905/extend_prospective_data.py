from pathlib import Path
import pandas as pd
src=Path('Mega-Sena.xlsx'); out=Path('Mega-Sena_through_3050.xlsx')
df=pd.read_excel(src)
known={3048:[2,6,27,39,44,50],3049:[6,13,36,43,53,55],3050:[11,14,30,38,49,55]}
for c,nums in known.items():
    if c in set(df['Concurso'].astype(int)): continue
    row={col:None for col in df.columns}; row['Concurso']=c
    for i,n in enumerate(nums,1): row[f'Bola{i}']=n
    df=pd.concat([df,pd.DataFrame([row])],ignore_index=True)
df=df.sort_values('Concurso').reset_index(drop=True)
df.to_excel(out,index=False)
print(df[['Concurso','Bola1','Bola2','Bola3','Bola4','Bola5','Bola6']].tail(4).to_string(index=False))
