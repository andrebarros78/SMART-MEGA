import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.wmcp_scientific import HyperparameterRule,CalibrationGovernor,ScientificMemoryRecord,ScientificMemoryStore,EvidenceDocument,ScientificEvidenceRAG

def test_all():
    g=CalibrationGovernor({"temperature":HyperparameterRule("temperature",0.0,2.0,0.25)})
    assert g.evaluate({"temperature":0.8},{"temperature":1.0},"tester","calibration")["approved"]
    assert not g.evaluate({"temperature":0.2},{"temperature":1.8},"tester","probe")["approved"]
    with tempfile.TemporaryDirectory() as td:
        s=ScientificMemoryStore(Path(td)/"memory.jsonl")
        r=ScientificMemoryRecord.create("calibration improves reliability",["paper-1"],["calibration"],0.9,"paper")
        assert s.append(r) and not s.append(r) and s.search("calibration")[0].record_id==r.record_id
    rag=ScientificEvidenceRAG([EvidenceDocument("e1","Calibration","probability calibration confidence observed frequency","paper://e1"),EvidenceDocument("e2","Other","computer vision segmentation","paper://e2")])
    hits=rag.retrieve("probability calibration confidence")
    assert hits and hits[0].evidence_id=="e1" and "[e1]" in rag.context_block(hits)

if __name__=="__main__": test_all(); print("WMCP_SCIENTIFIC_TESTS_PASS")
