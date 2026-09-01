from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 1) Harden promotion gate input validation and policy declaration.
p = ROOT / 'smart_promotion_gate.py'
s = p.read_text(encoding='utf-8-sig')
if 'import math\n' not in s:
    s = s.replace('from __future__ import annotations\n\n', 'from __future__ import annotations\n\nimport math\n')

if "POLICY_SCHEMA = 'SMART_PROMOTION_GATE_POLICY_1'" not in s:
    s = s.replace("BASE_MIN_PROSPECTIVE_CONTESTS = 20\nMIN_E_VALUE = 10.0\n",
                  "POLICY_SCHEMA = 'SMART_PROMOTION_GATE_POLICY_1'\nBASE_MIN_PROSPECTIVE_CONTESTS = 20\nMIN_E_VALUE = 10.0\nMIN_HITS = 0\nMAX_HITS = 6\n")

old = "def adaptive_min_contests(mean_hit_advantage: float) -> int:\n    \"\"\"Return a predeclared sample floor that rises as observed advantage shrinks.\"\"\"\n    advantage = float(mean_hit_advantage)\n"
new = "def _validated_hits(value: Any, field: str) -> int:\n    if isinstance(value, bool):\n        raise ValueError(f'{field} must be an integer in [{MIN_HITS}, {MAX_HITS}]')\n    try:\n        numeric = float(value)\n        hits = int(value)\n    except (TypeError, ValueError, OverflowError) as exc:\n        raise ValueError(f'{field} must be an integer in [{MIN_HITS}, {MAX_HITS}]') from exc\n    if not math.isfinite(numeric) or numeric != hits or not (MIN_HITS <= hits <= MAX_HITS):\n        raise ValueError(f'{field} must be an integer in [{MIN_HITS}, {MAX_HITS}]')\n    return hits\n\n\ndef adaptive_min_contests(mean_hit_advantage: float) -> int:\n    \"\"\"Return a predeclared sample floor that rises as observed advantage shrinks.\"\"\"\n    advantage = float(mean_hit_advantage)\n    if not math.isfinite(advantage):\n        raise ValueError('mean_hit_advantage must be finite')\n"
if old in s:
    s = s.replace(old, new, 1)

old = "    rows = list(records)\n    n = len(rows)\n    challenger_hits = sum(int(row['challenger_hits']) for row in rows)\n    champion_hits = sum(int(row['champion_hits']) for row in rows)\n"
new = "    rows = list(records)\n    validated = [\n        {\n            'challenger_hits': _validated_hits(row.get('challenger_hits'), 'challenger_hits'),\n            'champion_hits': _validated_hits(row.get('champion_hits'), 'champion_hits'),\n        }\n        for row in rows\n    ]\n    observed_e_value = float(e_value)\n    if not math.isfinite(observed_e_value) or observed_e_value < 0.0:\n        raise ValueError('e_value must be finite and non-negative')\n    n = len(validated)\n    challenger_hits = sum(row['challenger_hits'] for row in validated)\n    champion_hits = sum(row['champion_hits'] for row in validated)\n"
if old in s:
    s = s.replace(old, new, 1)

s = s.replace("    sequential_evidence = float(e_value) >= MIN_E_VALUE\n", "    sequential_evidence = observed_e_value >= MIN_E_VALUE\n")
s = s.replace("        'e_value': float(e_value),\n", "        'e_value': observed_e_value,\n        'inputs_validated': True,\n")

old = "    return {\n        'base_min_prospective_contests': BASE_MIN_PROSPECTIVE_CONTESTS,\n"
new = "    return {\n        'schema': POLICY_SCHEMA,\n        'base_min_prospective_contests': BASE_MIN_PROSPECTIVE_CONTESTS,\n"
if old in s:
    s = s.replace(old, new, 1)

s = s.replace("        'promotion_before_evidence_prohibited': True,\n", "        'promotion_before_evidence_prohibited': True,\n        'accepted_hit_domain': [MIN_HITS, MAX_HITS],\n        'invalid_or_nonfinite_inputs_rejected': True,\n")
p.write_text(s, encoding='utf-8')

# 2) Preserve the promotion policy explicitly inside the append-only FREEZE ledger snapshot.
p = ROOT / 'smart_champion_challenger.py'
s = p.read_text(encoding='utf-8-sig')
old = "                     'sequential_prospective_proof': sequential_snapshot},\n"
new = "                     'sequential_prospective_proof': sequential_snapshot,\n                     'promotion_policy': freeze_obj['promotion_policy']},\n"
if old in s and new.strip() not in s:
    s = s.replace(old, new, 1)
# Avoid truncating malformed numeric adjudication values before gate validation.
old = "        {'challenger_hits': int(ad['challenger_hits']), 'champion_hits': int(ad['champion_hits'])}\n"
new = "        {'challenger_hits': ad['challenger_hits'], 'champion_hits': ad['champion_hits']}\n"
if old in s:
    s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# 3) Architecture alignment: promotion gate is a required leaf module.
p = ROOT / 'test_smart_architecture_alignment.py'
s = p.read_text(encoding='utf-8-sig')
if "    'smart_promotion_gate.py',\n" not in s:
    marker = "    'smart_sequential_prospective_proof.py',\n"
    s = s.replace(marker, marker + "    'smart_promotion_gate.py',\n", 1)
leaf_assert = "    assert deps['smart_promotion_gate.py'] & {'smart_signal_agent','smart_champion_challenger','adjudicate_signal_challenger'} == set()\n"
if leaf_assert not in s:
    marker = "    assert 'smart_signal_expansion_governance' not in deps['smart_v2_engine.py']\n"
    s = s.replace(marker, marker + leaf_assert, 1)
p.write_text(s, encoding='utf-8')

# 4) Expand P13 adversarial and freeze-preservation tests.
p = ROOT / 'test_smart_promotion_gate.py'
s = p.read_text(encoding='utf-8-sig')
if 'import json\n' not in s:
    s = s.replace('from __future__ import annotations\n\n', 'from __future__ import annotations\n\nimport json\nfrom pathlib import Path\n\nimport numpy as np\nimport pandas as pd\nimport pytest\n\n')
if 'import smart_champion_challenger as cc\n' not in s:
    s = s.replace('from smart_champion_challenger import promotion_status\n', 'from smart_champion_challenger import promotion_status\nimport smart_champion_challenger as cc\n')

add = r'''


def test_gate_rejects_invalid_hit_domain_instead_of_truncating_or_promoting():
    for bad in (-1, 7, 1.5, True, float('nan')):
        rows = [{'challenger_hits': bad, 'champion_hits': 0}]
        with pytest.raises(ValueError):
            assess_promotion_records(rows, e_value=100.0)
    with pytest.raises(ValueError):
        promotion_status(_ledger(20, challenger=4, champion=3, e_value=10.0) | {
            'events': _ledger(20, challenger=4, champion=3, e_value=10.0)['events'][:-1] + [
                {**_ledger(20, challenger=4, champion=3, e_value=10.0)['events'][-1], 'challenger_hits': 6.5}
            ]
        })


def test_gate_rejects_nonfinite_or_negative_sequential_evidence():
    rows = _rows(20, 6, 0)
    for bad in (float('nan'), float('inf'), float('-inf'), -0.01):
        with pytest.raises(ValueError):
            assess_promotion_records(rows, e_value=bad)


def test_adaptive_sample_rejects_nonfinite_advantage():
    with pytest.raises(ValueError):
        adaptive_min_contests(float('nan'))
    with pytest.raises(ValueError):
        adaptive_min_contests(float('inf'))


def _dataset(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(1, n + 1):
        draw = np.sort(rng.choice(np.arange(1, 61), 6, replace=False))
        row = {'Concurso': i, 'Data do Sorteio': pd.Timestamp('2024-01-01') + pd.Timedelta(days=i)}
        row.update({f'Bola{j}': int(draw[j - 1]) for j in range(1, 7)})
        rows.append(row)
    return pd.DataFrame(rows)


def test_freeze_preserves_promotion_gate_hash_and_policy_in_file_and_ledger(tmp_path: Path):
    data = tmp_path / 'pre.xlsx'
    freeze = tmp_path / 'freeze.json'
    ledger = tmp_path / 'ledger.json'
    state = tmp_path / 'state.json'
    _dataset(65, 1313).to_excel(data, index=False)
    out = cc.freeze_champion_challenger(data, 66, freeze, ledger, state, start=30)
    assert out['status'] == 'FROZEN'
    frozen = json.loads(freeze.read_text(encoding='utf-8'))
    led = json.loads(ledger.read_text(encoding='utf-8'))
    event = next(ev for ev in led['events'] if ev.get('event_type') == 'FREEZE')
    policy = policy_snapshot()
    assert frozen['promotion_policy'] == policy
    assert event['snapshot']['promotion_policy'] == policy
    assert frozen['promotion_gate_sha256'] == cc.sha256(Path('smart_promotion_gate.py'))
    assert event['hashes']['promotion_gate'] == frozen['promotion_gate_sha256']
    assert policy['schema'] == 'SMART_PROMOTION_GATE_POLICY_1'
    assert policy['invalid_or_nonfinite_inputs_rejected'] is True
'''
if 'test_gate_rejects_invalid_hit_domain_instead_of_truncating_or_promoting' not in s:
    s += add
p.write_text(s, encoding='utf-8')

print('P13 hardening patch applied')
