"""SQLite WAL transactional isolated source gate; no production pointer writes."""
import json,sqlite3
from pathlib import Path
from .source_gate_admin import transition,digest
class IsolatedGate:
 def __init__(self,path):
  path=Path(path)
  if path.is_symlink():raise ValueError('DB_SYMLINK')
  path.parent.mkdir(parents=True,exist_ok=True)
  self.db=sqlite3.connect(str(path),isolation_level=None)
  self.db.execute('PRAGMA synchronous=FULL')
  self.db.execute('PRAGMA journal_mode=WAL')
  self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,body TEXT NOT NULL)')
 def read(self):
  state={'state':'BLOCKED','generation':0,'head':'','events':[]}
  for seq,raw in self.db.execute('SELECT seq,body FROM events ORDER BY seq'):
   e=json.loads(raw)
   if seq!=state['generation']+1 or e['generation']!=seq or e['previous_head']!=state['head'] or e['sha256']!=digest({k:v for k,v in e.items() if k!='sha256'}) or e['state']==state['state']:raise ValueError('AUDIT_CORRUPT')
   state={'state':e['state'],'generation':seq,'head':e['sha256'],'events':state['events']+[e]}
  return state
 def apply(self,envelope,trust,approval_check,proof_check,now=None):
  self.db.execute('BEGIN IMMEDIATE')
  try:
   old=self.read();new=transition(old,envelope,trust,now);p=envelope['payload']
   if not callable(approval_check) or approval_check(p['approval_id'],p['authority_id'],p['operation']) is not True:raise ValueError('APPROVAL_DENIED')
   if not callable(proof_check) or proof_check(p['access_proof_sha256']) is not True:raise ValueError('ACCESS_DENIED')
   if new!=old:self.db.execute('INSERT INTO events VALUES (?,?)',(new['generation'],json.dumps(new['events'][-1],sort_keys=True)))
   self.db.execute('COMMIT');return new
  except BaseException:
   self.db.execute('ROLLBACK');raise
 def close(self):self.db.close()
