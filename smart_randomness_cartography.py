from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from smart_v2_engine import load_draws, onehot
SCHEMA_NULL='SMART_NULL_UNIVERSE_MANIFEST_V1'; SCHEMA_ATLAS='SMART_RANDOMNESS_ATLAS_V1'
NUMBERS=np.arange(1,61,dtype=int); K=6; DEFAULT_SEED=20260904; DEFAULT_REPLICATIONS=1000
ATLAS_WINDOWS=(1,2,3,5,10,25,50,100,250,500,1000)

def sha256_file(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()

def _v(draws):
 a=np.sort(np.asarray(draws,dtype=int),axis=1)
 if a.ndim!=2 or a.shape[1]!=6: raise ValueError('draws shape')
 for r in a:
  if len(set(map(int,r)))!=6 or r.min()<1 or r.max()>60: raise ValueError('invalid draw')
 return a

def _weighted(rng,w):
 w=np.asarray(w,float).copy(); w=np.where(np.isfinite(w)&(w>=0),w,0)
 if w.sum()<=0: w[:]=1
 return np.sort(rng.choice(NUMBERS,6,replace=False,p=w/w.sum()))

def u0_uniform_iid(n,rng): return np.asarray([np.sort(rng.choice(NUMBERS,6,replace=False)) for _ in range(n)],int)
def u1_temporal_permutation(draws,rng):
 a=_v(draws); return a[rng.permutation(len(a))].copy()
def u2_label_permutation(draws,rng):
 a=_v(draws); p=rng.permutation(NUMBERS); m=np.empty(61,int); m[1:]=p; return np.sort(m[a],axis=1)
def u3_block_shuffle(draws,rng,block_size=25):
 a=_v(draws); blocks=[a[i:i+block_size] for i in range(0,len(a),block_size)]; return np.vstack([blocks[i] for i in rng.permutation(len(blocks))])
def empirical_marginals(draws): return onehot(_v(draws)).mean(axis=0)
def u4_marginals_preserved(draws,rng,swap_steps=None):
 a=_v(draws).copy(); X=onehot(a).astype(np.uint8); n=len(a)
 steps=int(swap_steps or max(1000,5*n))
 accepted=0
 for _ in range(steps):
  i,j=rng.integers(0,n,size=2)
  if i==j: continue
  left=np.flatnonzero((X[i]==1)&(X[j]==0)); right=np.flatnonzero((X[j]==1)&(X[i]==0))
  if not len(left) or not len(right): continue
  x=int(rng.choice(left)); y=int(rng.choice(right))
  X[i,x]=0; X[j,x]=1; X[j,y]=0; X[i,y]=1; accepted+=1
 out=np.asarray([np.flatnonzero(row)+1 for row in X],int)
 return np.sort(out,axis=1)

def fit_transition_weights(draws,alpha=1.0):
 a=_v(draws); X=onehot(a); c=np.full((60,60),alpha,float); d=np.full(60,2*alpha,float)
 for t in range(len(X)-1):
  for i in np.flatnonzero(X[t]>0): c[i]+=X[t+1]; d[i]+=1
 return c/d[:,None]
def u5_fitted_dynamic(draws,rng):
 a=_v(draws); tr=fit_transition_weights(a); base=empirical_marginals(a)+1e-6; out=[_weighted(rng,base)]
 for _ in range(1,len(a)):
  prev=np.asarray(out[-1])-1; out.append(_weighted(rng,.5*base+.5*tr[prev].mean(axis=0)))
 return np.asarray(out,int)
def u6_adversarial_controls(n,rng):
 if n<20: raise ValueError('n<20')
 null=u0_uniform_iid(n,rng); bw=np.ones(60); bw[:10]=4; bias=np.asarray([_weighted(rng,bw) for _ in range(n)])
 low=np.r_[np.full(30,3.0),np.ones(30)]; high=np.r_[np.ones(30),np.full(30,3.0)]
 regime=np.asarray([_weighted(rng,low if i<n//2 else high) for i in range(n)])
 motif=u0_uniform_iid(n,rng); motif[::7]=np.array([1,2,3,4,5,6])
 return {'u6_null_control':null,'u6_persistent_bias':bias,'u6_regime_switch':regime,'u6_repeated_motif':motif}
def _entropy(p):
 p=np.clip(np.asarray(p,float),1e-12,1-1e-12); return float(np.mean(-(p*np.log2(p)+(1-p)*np.log2(1-p))))
def _lz(bits):
 s=''.join('1' if x else '0' for x in np.asarray(bits,np.uint8).ravel()); D=set(); i=0; c=0
 while i<len(s):
  j=i+1
  while j<=len(s) and s[i:j] in D: j+=1
  D.add(s[i:j]); c+=1; i=j
 return c
def atlas_descriptors(draws):
 a=_v(draws); X=onehot(a); sums=a.sum(1); even=(a%2==0).sum(1); spans=a[:,-1]-a[:,0]; gaps=np.diff(a,axis=1)-1; cons=(np.diff(a,axis=1)==1).sum(1)
 rep=np.zeros(len(a),int)
 if len(a)>1: rep[1:]=(X[1:]*X[:-1]).sum(1).astype(int)
 marg=X.mean(0); pairs=X.T@X; np.fill_diagonal(pairs,0); up=pairs[np.triu_indices(60,1)]
 return {'n_draws':int(len(a)),'marginal_probability':[float(x) for x in marg],'marginal_min':float(marg.min()),'marginal_max':float(marg.max()),'marginal_std':float(marg.std(ddof=1)),'binary_entropy_mean_bits':_entropy(marg),'lz_phrase_count':int(_lz(X)),'sum':{'mean':float(sums.mean()),'std':float(sums.std(ddof=1)) if len(sums)>1 else 0.0},'even_count':{'mean':float(even.mean()),'distribution':{str(k):int(np.sum(even==k)) for k in range(7)}},'span':{'mean':float(spans.mean()),'std':float(spans.std(ddof=1)) if len(spans)>1 else 0.0},'internal_gap_mean':float(gaps.mean()),'consecutive_pairs_mean':float(cons.mean()),'repeat_from_previous_mean':float(rep[1:].mean()) if len(a)>1 else 0.0,'pair_cooccurrence':{'mean':float(up.mean()),'std':float(up.std(ddof=1)),'max':int(up.max())}}
def _stat(draws):
 d=atlas_descriptors(draws); return {'marginal_std':d['marginal_std'],'sum_mean':d['sum']['mean'],'span_mean':d['span']['mean'],'repeat_prev_mean':d['repeat_from_previous_mean'],'consecutive_pairs_mean':d['consecutive_pairs_mean'],'entropy':d['binary_entropy_mean_bits']}
def _compare(obs,vals):
 a=np.asarray(vals,float); m=float(a.mean()); sd=float(a.std(ddof=1)) if len(a)>1 else 0.0; z=(obs-m)/sd if sd>0 else 0.0; p=float((1+np.sum(np.abs(a-m)>=abs(obs-m)))/(len(a)+1)); return {'observed':float(obs),'null_mean':m,'null_std':sd,'z':float(z),'empirical_two_sided_p':p}
def _windows(draws):
 a=_v(draws); out={}
 for w in ATLAS_WINDOWS:
  if len(a)>=w:
   d=atlas_descriptors(a[-w:]); out[str(w)]={'sum_mean':d['sum']['mean'],'even_mean':d['even_count']['mean'],'span_mean':d['span']['mean'],'repeat_prev_mean':d['repeat_from_previous_mean'],'marginal_std':d['marginal_std']}
 return out
def build_null_manifest(draws,replications=DEFAULT_REPLICATIONS,seed=DEFAULT_SEED,block_size=25):
 a=_v(draws)
 if replications<20: raise ValueError('replications must be >=20')
 return {'schema':SCHEMA_NULL,'seed':int(seed),'replications':int(replications),'trajectory_length':int(len(a)),'families':{'U0':'uniform iid 6-of-60 without replacement','U1':'temporal permutation preserving real draws','U2':'global label permutation 1..60','U3':f'temporal block shuffle block_size={block_size}','U4':'exact fixed-marginal swap surrogate preserving each number total frequency and six numbers per draw','U5':'fitted first-order conditional inclusion generator','U6':'adversarial controls: null, persistent bias, regime switch, repeated motif'},'seeds_policy':'single master PCG64 seed fixed execution order','monte_carlo_error_policy':'add-one empirical p-value; null std and replication count reported','causal_claim':False}
def build_atlas(draws,contests,replications=DEFAULT_REPLICATIONS,seed=DEFAULT_SEED,block_size=25):
 a=_v(draws); contests=np.asarray(contests,int)
 if len(a)!=len(contests): raise ValueError('contests length mismatch')
 rng=np.random.default_rng(seed); obs=_stat(a); vals={u:{k:[] for k in obs} for u in ('U0','U1','U2','U3','U4','U5')}
 for _ in range(replications):
  us={'U0':u0_uniform_iid(len(a),rng),'U1':u1_temporal_permutation(a,rng),'U2':u2_label_permutation(a,rng),'U3':u3_block_shuffle(a,rng,block_size),'U4':u4_marginals_preserved(a,rng),'U5':u5_fitted_dynamic(a,rng)}
  for n,s in us.items():
   st=_stat(s)
   for k,v in st.items(): vals[n][k].append(float(v))
 comps={n:{k:_compare(obs[k],v) for k,v in metrics.items()} for n,metrics in vals.items()}
 u6={n:_stat(s) for n,s in u6_adversarial_controls(len(a),rng).items()}
 return {'schema':SCHEMA_ATLAS,'contest_min':int(contests.min()),'contest_max':int(contests.max()),'n_draws':int(len(a)),'observed':atlas_descriptors(a),'windows':_windows(a),'null_comparisons':comps,'u6_controls':u6,'interpretation_guardrail':'diagnostic cartography only; significance does not imply prospective predictability or determinism'}
def write_program_artifacts(data_path,manifest_path,atlas_path,replications=DEFAULT_REPLICATIONS,seed=DEFAULT_SEED,expected_max_contest=None):
 data_path=Path(data_path); draws,contests=load_draws(data_path)
 if expected_max_contest is not None and int(contests.max())>int(expected_max_contest): raise ValueError('future contest detected beyond expected cutoff')
 manifest=build_null_manifest(draws,replications,seed); dh=sha256_file(data_path); manifest.update({'data_file':data_path.name,'data_sha256':dh,'cutoff_contest':int(contests.max())})
 atlas=build_atlas(draws,contests,replications,seed); atlas.update({'data_file':data_path.name,'data_sha256':dh,'null_manifest_schema':SCHEMA_NULL,'seed':int(seed),'replications':int(replications)})
 Path(manifest_path).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'); Path(atlas_path).write_text(json.dumps(atlas,ensure_ascii=False,indent=2),encoding='utf-8')
 return manifest,atlas
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--data',default='Mega-Sena_through_3053_v2.xlsx'); ap.add_argument('--manifest',default='SMART_NULL_UNIVERSE_MANIFEST.json'); ap.add_argument('--atlas',default='SMART_RANDOMNESS_ATLAS.json'); ap.add_argument('--replications',type=int,default=DEFAULT_REPLICATIONS); ap.add_argument('--seed',type=int,default=DEFAULT_SEED); ap.add_argument('--expected-max-contest',type=int,default=3053); a=ap.parse_args()
 m,r=write_program_artifacts(a.data,a.manifest,a.atlas,a.replications,a.seed,a.expected_max_contest); print(json.dumps({'manifest':m['schema'],'atlas':r['schema'],'cutoff':r['contest_max'],'replications':r['replications']}))
if __name__=='__main__': main()


