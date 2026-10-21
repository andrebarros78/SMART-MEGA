"""Fail-closed Ed25519 source gate transition; isolated only."""
import base64,hashlib,json
from datetime import datetime,timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def transition(state,envelope,trust,now=None):
 p=envelope['payload']; now=now or datetime.now(timezone.utc)
 required={'schema','operation','source','expected_state','expected_generation','expected_head','authority_id','nonce','issued_at','expires_at','access_proof_sha256','approval_id'}
 if set(p)!=required or p['schema']!='SMART_SOURCE_GATE_ADMIN_V1' or p['operation'] not in ('RELEASE','ROLLBACK') or p['source']!='CAIXA_OFFICIAL_VIDEO':raise ValueError('CONTRACT_DENIED')
 try:Ed25519PublicKey.from_public_bytes(trust[p['authority_id']]).verify(base64.b64decode(envelope['signature_b64'],validate=True),canonical(p))
 except Exception as e:raise ValueError('SIGNATURE_DENIED') from e
 issued=datetime.fromisoformat(p['issued_at'].replace('Z','+00:00'));expires=datetime.fromisoformat(p['expires_at'].replace('Z','+00:00'))
 if issued.tzinfo is None or expires.tzinfo is None or not issued<=now<expires:raise ValueError('EXPIRED')
 if not p['nonce'] or not p['approval_id'] or len(p['access_proof_sha256'])!=64:raise ValueError('EVIDENCE_DENIED')
 for e in state['events']:
  if e['nonce']==p['nonce']:
   if e['fingerprint']==digest(envelope):return state
   raise ValueError('NONCE_REUSE')
 if (p['expected_state'],p['expected_generation'],p['expected_head'])!=(state['state'],state['generation'],state['head']):raise ValueError('STALE')
 target='RELEASED' if p['operation']=='RELEASE' else 'BLOCKED'
 if target==state['state']:raise ValueError('NO_TRANSITION')
 event={'generation':state['generation']+1,'previous_head':state['head'],'state':target,'nonce':p['nonce'],'fingerprint':digest(envelope),'approval_id':p['approval_id'],'access_proof_sha256':p['access_proof_sha256']}
 event['sha256']=digest(event)
 return {'state':target,'generation':event['generation'],'head':event['sha256'],'events':state['events']+[event]}
