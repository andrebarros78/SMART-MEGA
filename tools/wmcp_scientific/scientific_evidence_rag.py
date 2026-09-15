from dataclasses import dataclass
import math

@dataclass(frozen=True)
class EvidenceDocument:
    evidence_id: str
    title: str
    text: str
    source: str

@dataclass(frozen=True)
class RetrievalHit:
    evidence_id: str
    title: str
    source: str
    score: float
    excerpt: str

def _tokens(text):
    out=set()
    for raw in str(text).split():
        token="".join(ch for ch in raw.casefold() if ch.isalnum() or ch in "-_")
        if len(token)>1: out.add(token)
    return out

class ScientificEvidenceRAG:
    def __init__(self,documents=()):
        self.docs={}
        for d in documents: self.add(d)
    def add(self,doc):
        if not doc.evidence_id or not doc.title or not doc.text or not doc.source: raise ValueError("evidence_fields_required")
        if doc.evidence_id in self.docs and self.docs[doc.evidence_id] != doc: raise ValueError("evidence_id_collision")
        self.docs[doc.evidence_id]=doc
    def retrieve(self,query,k=5,min_score=0.05):
        q=_tokens(query); hits=[]
        if not q: return tuple()
        for d in self.docs.values():
            dt=_tokens(d.title+" "+d.text); overlap=len(q & dt)
            if not overlap: continue
            score=(overlap/len(q))*0.8+math.sqrt(overlap/max(1,len(dt)))*0.2
            if score >= min_score: hits.append(RetrievalHit(d.evidence_id,d.title,d.source,round(score,6),d.text.replace(chr(10)," ")[:360]))
        hits.sort(key=lambda h:(h.score,h.evidence_id),reverse=True); return tuple(hits[:int(k)])
    @staticmethod
    def context_block(hits):
        return (chr(10)+chr(10)).join("["+h.evidence_id+"] "+h.title+" | "+h.source+" | score="+format(h.score,".6f")+chr(10)+h.excerpt for h in hits)
