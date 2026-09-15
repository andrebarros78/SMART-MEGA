from dataclasses import dataclass,asdict
from hashlib import sha256
import json
from pathlib import Path

@dataclass(frozen=True)
class ScientificMemoryRecord:
    record_id: str
    claim: str
    evidence_ids: tuple
    tags: tuple
    confidence: float
    source_type: str
    @classmethod
    def create(cls,claim,evidence_ids,tags=(),confidence=1.0,source_type="unknown"):
        claim=str(claim).strip(); evidence=tuple(sorted({str(x).strip() for x in evidence_ids if str(x).strip()})); tags=tuple(sorted({str(x).strip().casefold() for x in tags if str(x).strip()}))
        if not claim: raise ValueError("claim_required")
        if not evidence: raise ValueError("evidence_required")
        if not 0 <= float(confidence) <= 1: raise ValueError("confidence_out_of_range")
        raw=json.dumps({"claim":claim,"evidence":evidence,"tags":tags,"source_type":source_type},sort_keys=True).encode()
        return cls(sha256(raw).hexdigest(),claim,evidence,tags,float(confidence),str(source_type))

class ScientificMemoryStore:
    def __init__(self,path): self.path=Path(path)
    def records(self):
        if not self.path.exists(): return tuple()
        out=[]
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d=json.loads(line); d["evidence_ids"]=tuple(d["evidence_ids"]); d["tags"]=tuple(d["tags"]); out.append(ScientificMemoryRecord(**d))
        return tuple(out)
    def append(self,record):
        if record.record_id in {r.record_id for r in self.records()}: return False
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open("a",encoding="utf-8") as h: h.write(json.dumps(asdict(record),sort_keys=True)+chr(10))
        return True
    def search(self,query,tag=None,limit=20):
        terms={x for x in str(query).casefold().split() if x}; tag=str(tag).casefold().strip() if tag else None; scored=[]
        for r in self.records():
            if tag and tag not in r.tags: continue
            hay=(r.claim+" "+" ".join(r.tags)).casefold(); score=sum(1 for t in terms if t in hay)
            if score or not terms: scored.append((score,r.confidence,r))
        scored.sort(key=lambda x:(x[0],x[1]),reverse=True); return tuple(x[2] for x in scored[:int(limit)])
