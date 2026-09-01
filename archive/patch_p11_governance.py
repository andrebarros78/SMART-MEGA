from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
# Create canonical empty registry with current signal ids.
import sys
sys.path.insert(0,str(ROOT))
from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import SignalExpansionGovernance, REGISTRY_PATH, write_registry
write_registry(ROOT/REGISTRY_PATH, SignalExpansionGovernance(tuple(SIGNAL_NAMES)))

p=ROOT/'smart_champion_challenger.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('from smart_signal_agent import SmartSignalAgent, write_state\n','from smart_signal_agent import SmartSignalAgent, write_state, SIGNAL_NAMES\n',1)
if 'from smart_signal_expansion_governance import REGISTRY_PATH, load_registry\n' not in s:
    s=s.replace('from smart_signal_agent import SmartSignalAgent, write_state, SIGNAL_NAMES\n','from smart_signal_agent import SmartSignalAgent, write_state, SIGNAL_NAMES\nfrom smart_signal_expansion_governance import REGISTRY_PATH, load_registry\n',1)
s=s.replace("        'signal_interactions': sha256(Path('smart_signal_interactions.py')),\n", "        'signal_interactions': sha256(Path('smart_signal_interactions.py')),\n        'signal_expansion_governance': sha256(Path('smart_signal_expansion_governance.py')),\n",1)
marker="    data_hash = sha256(data)\n"
if "expansion_governance = load_registry" not in s:
    s=s.replace(marker, marker+"    expansion_governance = load_registry(REGISTRY_PATH, tuple(SIGNAL_NAMES))\n    expansion_snapshot = expansion_governance.snapshot()\n    expansion_registry_hash = sha256(REGISTRY_PATH) if REGISTRY_PATH.exists() else None\n",1)
state_marker="                  'source_cutoff_timestamp': source_ts, 'signal_cutoff_timestamp': signal_ts,\n                  'signal_cutoff_timestamp_kind': signal_ts_kind})\n"
if "'signal_expansion_governance': expansion_snapshot" not in s:
    s=s.replace(state_marker,"                  'source_cutoff_timestamp': source_ts, 'signal_cutoff_timestamp': signal_ts,\n                  'signal_cutoff_timestamp_kind': signal_ts_kind,\n                  'signal_expansion_governance': expansion_snapshot})\n",1)
s=s.replace("        'signal_interactions_sha256': component_hashes['signal_interactions'],\n", "        'signal_interactions_sha256': component_hashes['signal_interactions'],\n        'signal_expansion_governance_sha256': component_hashes['signal_expansion_governance'],\n        'signal_expansion_registry_file': str(REGISTRY_PATH),\n        'signal_expansion_registry_sha256': expansion_registry_hash,\n",1)
s=s.replace("                     'meta_governor': freeze_obj['challenger']['meta_governor']},\n", "                     'meta_governor': freeze_obj['challenger']['meta_governor'],\n                     'signal_expansion_governance': expansion_snapshot},\n",1)
p.write_text(s,encoding='utf-8')

# Continuous Red Team must become stale when P10/P11 behavior changes.
r=ROOT/'smart_continuous_red_team.py'
t=r.read_text(encoding='utf-8-sig')
if "    'smart_bounded_online_learning.py',\n" not in t:
    t=t.replace("    'smart_meta_governor.py',\n", "    'smart_meta_governor.py',\n    'smart_bounded_online_learning.py',\n    'smart_signal_expansion_governance.py',\n")
elif "    'smart_signal_expansion_governance.py',\n" not in t:
    t=t.replace("    'smart_bounded_online_learning.py',\n", "    'smart_bounded_online_learning.py',\n    'smart_signal_expansion_governance.py',\n")
r.write_text(t,encoding='utf-8')

# Architecture assertions: operational signal stack cannot import expansion governance upward.
a=ROOT/'test_smart_architecture_alignment.py'
u=a.read_text(encoding='utf-8-sig')
if "'smart_signal_expansion_governance.py'," not in u:
    u=u.replace("    'smart_continuous_red_team.py',\n", "    'smart_continuous_red_team.py',\n    'smart_signal_expansion_governance.py',\n")
anchor="    assert 'smart_continuous_red_team' not in deps['smart_v2_engine.py']\n"
if anchor in u and "smart_signal_expansion_governance' not in deps['smart_signal_agent.py']" not in u:
    u=u.replace(anchor,anchor+"    assert 'smart_signal_expansion_governance' not in deps['smart_signal_agent.py']\n    assert 'smart_signal_expansion_governance' not in deps['smart_v2_engine.py']\n")
a.write_text(u,encoding='utf-8')
print('patched P11 governance')
