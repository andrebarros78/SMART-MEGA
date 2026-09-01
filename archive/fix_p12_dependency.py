from pathlib import Path
p=Path(__file__).resolve().parents[1]/'smart_sequential_prospective_proof.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("SCHEMA = 'SMART_SEQUENTIAL_PROSPECTIVE_PROOF_1'\n", "SCHEMA = 'SMART_SEQUENTIAL_PROSPECTIVE_PROOF_1'\nLEDGER_SCHEMA = 'SMART_SIGNAL_LEDGER_1'\n")
# insert local ledger helpers before append_learning_update
marker='def append_learning_update(ledger_path: Path, target: int, state_file: Path,\n'
helpers="def _load_ledger(path: Path) -> dict[str, Any]:\n    p=Path(path)\n    if not p.is_file():\n        return {'schema': LEDGER_SCHEMA, 'events': []}\n    obj=json.loads(p.read_text(encoding='utf-8'))\n    if obj.get('schema')!=LEDGER_SCHEMA or not isinstance(obj.get('events'),list):\n        raise ValueError('invalid SMART signal ledger')\n    return obj\n\n\ndef _write_ledger(path: Path, ledger: dict[str, Any]) -> str:\n    Path(path).write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')\n    return sha256_file(Path(path))\n\n\n"
if helpers.strip() not in s:
    s=s.replace(marker,helpers+marker,1)
s=s.replace("    from smart_champion_challenger import load_ledger, write_ledger, sha256 as cc_sha256\n    ledger_path = Path(ledger_path)\n    ledger = load_ledger(ledger_path)\n", "    ledger_path = Path(ledger_path)\n    ledger = _load_ledger(ledger_path)\n")
s=s.replace("    before_hash = cc_sha256(ledger_path) if ledger_path.exists() else None\n", "    before_hash = sha256_file(ledger_path) if ledger_path.exists() else None\n")
s=s.replace("    ledger_hash = write_ledger(ledger_path, ledger)\n", "    ledger_hash = _write_ledger(ledger_path, ledger)\n",1)
s=s.replace("    from smart_champion_challenger import load_ledger, write_ledger\n    ledger_path = Path(ledger_path)\n    ledger = load_ledger(ledger_path)\n", "    ledger_path = Path(ledger_path)\n    ledger = _load_ledger(ledger_path)\n")
# replace second write_ledger occurrence
idx=s.find("    ledger_hash = write_ledger(ledger_path, ledger)")
if idx!=-1:
    s=s[:idx]+s[idx:].replace("    ledger_hash = write_ledger(ledger_path, ledger)","    ledger_hash = _write_ledger(ledger_path, ledger)",1)
# remove complete_prospective_cycle to keep P12 leaf
start=s.find('\ndef complete_prospective_cycle(')
if start!=-1:
    s=s[:start].rstrip()+"\n"
p.write_text(s,encoding='utf-8')
print('p12 dependency fixed')
