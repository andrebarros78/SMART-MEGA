import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_checkpoint_is_derived_from_current_evidence():
    subprocess.run([sys.executable, str(ROOT / 'smart_execution_checkpoint.py')], cwd=ROOT, check=True, capture_output=True, text=True)
    cp = json.loads((ROOT / 'SMART_EXECUTION_CHECKPOINT_20260904.json').read_text(encoding='utf-8'))
    mc = json.loads((ROOT / 'SMART_MONTE_CARLO_CONVERGENCE_1000.json').read_text(encoding='utf-8'))
    fp = json.loads((ROOT / 'SMART_FALSIFICATION_REPORT_POWERED.json').read_text(encoding='utf-8'))
    assert cp['schema'] == 'SMART_EXECUTION_CHECKPOINT_20260904_V2'
    assert cp['monte_carlo']['final_replications'] == mc['final_replications'] == 1000
    assert cp['falsification_resolution']['replications'] == fp['replications'] == 200
    assert cp['falsification_resolution']['resolution_sufficient'] is True
    assert not any('power-limited' in x for x in cp['current_blockers'])
    assert cp['freeze_3054_top6'] == [10, 11, 27, 30, 35, 38]
    root = ET.parse(ROOT / 'SMART_AUDIT_JUNIT_CURRENT.xml').getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.findall('testsuite'))
    assert cp['regression']['tests'] == sum(int(s.attrib.get('tests', 0)) for s in suites)
    assert cp['regression']['failures'] == 0
    assert cp['regression']['errors'] == 0
