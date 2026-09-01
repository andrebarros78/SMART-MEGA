from pathlib import Path
import pandas as pd
import pytest
import smart_v2_engine as e

def frame():
    return pd.DataFrame([
      {'Concurso':1,'Bola1':1,'Bola2':2,'Bola3':3,'Bola4':4,'Bola5':5,'Bola6':6},
      {'Concurso':2,'Bola1':7,'Bola2':8,'Bola3':9,'Bola4':10,'Bola5':11,'Bola6':12},
    ])

def save(tmp_path,df):
    p=tmp_path/'x.xlsx'; df.to_excel(p,index=False); return p

def test_valid_dataset(tmp_path):
    d,c=e.load_draws(save(tmp_path,frame())); assert d.shape==(2,6) and c.tolist()==[1,2]

def test_duplicate_number_rejected(tmp_path):
    f=frame(); f.loc[0,'Bola6']=5
    with pytest.raises(ValueError): e.load_draws(save(tmp_path,f))

def test_out_of_range_rejected(tmp_path):
    f=frame(); f.loc[0,'Bola1']=0
    with pytest.raises(ValueError): e.load_draws(save(tmp_path,f))

def test_duplicate_contest_rejected(tmp_path):
    f=frame(); f.loc[1,'Concurso']=1
    with pytest.raises(ValueError): e.load_draws(save(tmp_path,f))

def test_out_of_order_contest_rejected(tmp_path):
    f=frame(); f.loc[0,'Concurso']=2; f.loc[1,'Concurso']=1
    with pytest.raises(ValueError): e.load_draws(save(tmp_path,f))

def test_missing_value_rejected(tmp_path):
    f=frame(); f.loc[0,'Bola3']=None
    with pytest.raises(ValueError): e.load_draws(save(tmp_path,f))
