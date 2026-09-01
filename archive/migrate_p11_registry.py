from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import SignalExpansionGovernance, write_registry
p=ROOT/'SMART_SIGNAL_EXPANSION_REGISTRY.json'
g=SignalExpansionGovernance(tuple(SIGNAL_NAMES))
print(write_registry(p,g))
