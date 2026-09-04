from __future__ import annotations
import json, hashlib
from pathlib import Path
import numpy as np
import networkx as nx
import ruptures as rpt
from statsmodels.stats.diagnostic import acorr_ljungbox
from smart_v2_engine import load_draws, onehot

SCHEMA='SMART_RANDOMNESS_ATLAS_EXTENDED_V1'

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def binary_mi(x,y):
    x=np.asarray(x,dtype=np.uint8); y=np.asarray(y,dtype=np.uint8)
    joint=np.zeros((2,2),float)
    for a,b in zip(x,y): joint[int(a),int(b)]+=1
    if joint.sum()==0: return 0.0
    joint/=joint.sum(); px=joint.sum(1); py=joint.sum(0); out=0.0
    for i in range(2):
        for j in range(2):
            if joint[i,j]>0 and px[i]>0 and py[j]>0:
                out += joint[i,j]*np.log2(joint[i,j]/(px[i]*py[j]))
    return float(out)

def temporal_memory(draws):
    a=np.asarray(draws,int); X=onehot(a)
    mis=[binary_mi(X[:-1,j],X[1:,j]) for j in range(60)] if len(a)>1 else [0.0]*60
    out={'lag1_binary_mutual_information_mean_bits':float(np.mean(mis)),'lag1_binary_mutual_information_max_bits':float(np.max(mis))}
    sums=a.sum(1).astype(float); lags=[x for x in (5,10,20) if x < len(sums)]
    if lags:
        lb=acorr_ljungbox(sums,lags=lags,return_df=True)
        out['ljung_box_sum_pvalues']={str(int(k)):float(v) for k,v in lb['lb_pvalue'].items()}
    return out

def network_structure(draws):
    X=onehot(np.asarray(draws,int)); pairs=X.T@X; np.fill_diagonal(pairs,0)
    up=pairs[np.triu_indices(60,1)].astype(float); threshold=float(up.mean()+up.std(ddof=1))
    G=nx.Graph(); G.add_nodes_from(range(1,61))
    for i,j in zip(*np.triu_indices(60,1)):
        w=float(pairs[i,j])
        if w>threshold: G.add_edge(i+1,j+1,weight=w)
    deg=np.asarray([d for _,d in G.degree()],float)
    return {'edge_threshold':threshold,'edges':int(G.number_of_edges()),'density':float(nx.density(G)),'average_clustering':float(nx.average_clustering(G)) if G.number_of_edges() else 0.0,'degree_mean':float(deg.mean()),'degree_cv':float(deg.std(ddof=1)/deg.mean()) if deg.mean()>0 else 0.0}

def regime_structure(draws):
    a=np.asarray(draws,int); n=len(a)
    feats=np.column_stack([a.sum(1),(a%2==0).sum(1),a[:,-1]-a[:,0]]).astype(float)
    if n<40:
        return {'method':'ruptures.Binseg(l2)','penalty':None,'min_size':None,'breakpoints_index':[],'count':0,'diagnostic_only':True}
    z=(feats-feats.mean(0))/(feats.std(0)+1e-12)
    min_size=max(10,n//100); pen=float(2.0*np.log(max(n,2)))
    algo=rpt.Binseg(model='l2',min_size=min_size).fit(z)
    bkps=[int(x) for x in algo.predict(pen=pen) if int(x)<n]
    return {'method':'ruptures.Binseg(l2)','penalty':pen,'min_size':int(min_size),'breakpoints_index':bkps,'count':len(bkps),'diagnostic_only':True}

def build(draws,contests,data_file=None,data_sha256=None):
    a=np.asarray(draws,int); c=np.asarray(contests,int)
    if len(a)!=len(c): raise ValueError('contests length mismatch')
    return {'schema':SCHEMA,'contest_min':int(c.min()),'contest_max':int(c.max()),'n_draws':int(len(a)),'temporal_memory':temporal_memory(a),'network':network_structure(a),'regime_detection':regime_structure(a),'falsification':{'future_information_used':False,'causal_claim':False,'predictive_weight_authorized':False,'promotion_requires_holdout_and_prospective_evidence':True},'data_file':data_file,'data_sha256':data_sha256}

def write(data_path,out_path,expected_max_contest=3053):
    draws,contests=load_draws(data_path)
    if int(contests.max())>int(expected_max_contest): raise ValueError('future contest detected beyond expected cutoff')
    obj=build(draws,contests,Path(data_path).name,sha256_file(data_path))
    Path(out_path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    return obj

if __name__=='__main__':
    obj=write('Mega-Sena_through_3053_v2.xlsx','SMART_RANDOMNESS_ATLAS_EXTENDED.json',3053)
    print(json.dumps({'schema':obj['schema'],'cutoff':obj['contest_max'],'regime_breaks':obj['regime_detection']['count']}))


