from pathlib import Path
import pandas as pd, json, hashlib
p=Path(r'C:\New Projet\SMART-MEGA\Mega-Sena_through_3050.xlsx')
d=pd.read_excel(p)
rows=[]
for _,r in d.iterrows():
    rows.append([int(r['Concurso'])]+[int(r[f'Bola{i}']) for i in range(1,7)])
raw=json.dumps(rows,separators=(',',':')).encode('utf-8')
print('ROWS='+str(len(rows)))
print('CONTENT_SHA256='+hashlib.sha256(raw).hexdigest())
print('TAIL='+json.dumps(rows[-3:]))
