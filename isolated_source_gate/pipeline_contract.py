"""Isolated PIT contract for visual learning. No production integration or promotion."""
from datetime import datetime,timezone
def guarded_observation(gate_reader,observe):
 try:
  gate=gate_reader()
  if not isinstance(gate,dict) or gate.get('state')!='RELEASED' or gate.get('authority_verified') is not True or gate.get('access_verified') is not True or gate.get('legacy_blocked') is not False:return {'status':'BLOCKED','predictive_weight':0.0}
 except Exception:return {'status':'BLOCKED','predictive_weight':0.0}
 result=observe()
 if not isinstance(result,dict):raise ValueError('INVALID_OBSERVATION')
 return {'status':'OBSERVATION_ONLY','observation_status':result.get('status'),'predictive_weight':0.0}
def guarded_features(feature_reader,target_contest,cutoff_utc,**kwargs):
 target=str(target_contest)
 if not target.isascii() or not target.isdecimal() or int(target)<=0 or str(int(target))!=target:raise ValueError('INVALID_TARGET')
 cutoff=datetime.fromisoformat(cutoff_utc.replace('Z','+00:00'))
 if cutoff.tzinfo is None:raise ValueError('NAIVE_CUTOFF')
 result=feature_reader(target_contest=target,cutoff_utc=cutoff_utc,**kwargs)
 if not isinstance(result,dict) or result.get('predictive_weight')!=0.0:raise ValueError('PREDICTIVE_PROMOTION_DENIED')
 sources=result.get('source_contests')
 if not isinstance(sources,list) or any(not str(s).isascii() or not str(s).isdecimal() or int(s)>=int(target) for s in sources):raise ValueError('PIT_CONTEST_VIOLATION')
 stamp=result.get('as_of_utc')
 if stamp is not None:
  at=datetime.fromisoformat(stamp.replace('Z','+00:00'))
  if at.tzinfo is None or at.astimezone(timezone.utc)!=cutoff.astimezone(timezone.utc):raise ValueError('PIT_CUTOFF_VIOLATION')
 return result
