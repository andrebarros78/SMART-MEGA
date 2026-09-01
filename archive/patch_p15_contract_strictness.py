from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
p=root/'smart_evidence_only_promotion.py'
s=p.read_text(encoding='utf-8')
start=s.index('def _validated_p13(')
end=s.index('\n\ndef _gate_evidence',start)
new="""def _validated_p13(p13: dict[str, Any]) -> dict[str, Any]:\n    if not isinstance(p13, dict):\n        raise ValueError('P13 status must be an object')\n    eligible = p13.get('eligible')\n    if not isinstance(eligible, bool):\n        raise ValueError('P13 eligible flag must be boolean')\n    decision = p13.get('decision')\n    if eligible and decision != P13_PROMOTE_DECISION:\n        raise ValueError('P13 eligible status must carry the promotion eligibility decision')\n    if not eligible and decision != KEEP_DECISION:\n        raise ValueError('P13 ineligible status must keep Champion')\n    integer_fields = ('n', 'challenger_hits', 'champion_hits', 'advantage_hits', 'cumulative_regret')\n    for field in integer_fields:\n        value = p13.get(field)\n        if isinstance(value, bool) or not isinstance(value, int):\n            raise ValueError(f'P13 field {field} must be integer evidence')\n    e_value = p13.get('e_value')\n    if isinstance(e_value, bool) or not isinstance(e_value, (int, float)) or not math.isfinite(float(e_value)) or float(e_value) < 0.0:\n        raise ValueError('P13 field e_value must be finite non-negative numeric evidence')\n    if p13['n'] < 0 or p13['challenger_hits'] < 0 or p13['champion_hits'] < 0:\n        raise ValueError('P13 counts must be non-negative')\n    if p13['advantage_hits'] != p13['challenger_hits'] - p13['champion_hits']:\n        raise ValueError('P13 advantage_hits is internally inconsistent')\n    if p13['cumulative_regret'] != p13['champion_hits'] - p13['challenger_hits']:\n        raise ValueError('P13 cumulative_regret is internally inconsistent')\n    if eligible:\n        fingerprint = p13.get('candidate_fingerprint')\n        if not isinstance(fingerprint, str) or len(fingerprint) != 64:\n            raise ValueError('P13 eligible status must be bound to a 64-hex candidate fingerprint')\n        try:\n            int(fingerprint, 16)\n        except ValueError as exc:\n            raise ValueError('P13 eligible candidate fingerprint must be hexadecimal') from exc\n        lineage_pair_count = p13.get('lineage_pair_count')\n        if isinstance(lineage_pair_count, bool) or not isinstance(lineage_pair_count, int) or lineage_pair_count != p13['n']:\n            raise ValueError('P13 eligible lineage pair count must equal n')\n    return p13\n"""
s=s[:start]+new+s[end:]

s=s.replace("""    if int(gate.get('target_contest', -1)) != 3052:\n        blockers.append('implementation_gate_target_invalid')\n""", """    target = gate.get('target_contest')\n    if isinstance(target, bool) or not isinstance(target, int) or target != 3052:\n        blockers.append('implementation_gate_target_invalid')\n""",1)

old="""    if not isinstance(status.get('proof_file_sha256'), str) or len(status.get('proof_file_sha256', '')) != 64:\n        blockers.append('global_integrity_proof_hash_missing')\n"""
new2="""    proof_hash = status.get('proof_file_sha256')\n    if not isinstance(proof_hash, str) or len(proof_hash) != 64:\n        blockers.append('global_integrity_proof_hash_missing')\n    else:\n        try:\n            int(proof_hash, 16)\n        except ValueError:\n            blockers.append('global_integrity_proof_hash_invalid')\n"""
if old not in s: raise SystemExit('global hash marker missing')
s=s.replace(old,new2,1)

p.write_text(s,encoding='utf-8')

p2=root/'smart_global_integrity.py'
s2=p2.read_text(encoding='utf-8')
oldj="""    root = ET.parse(path).getroot()\n    suites = [root] if root.tag == 'testsuite' else list(root.findall('testsuite'))\n"""
newj="""    try:\n        root = ET.parse(path).getroot()\n    except ET.ParseError as exc:\n        raise ValueError('full regression JUnit XML is malformed') from exc\n    suites = [root] if root.tag == 'testsuite' else list(root.findall('testsuite'))\n"""
if oldj not in s2: raise SystemExit('junit parse marker missing')
s2=s2.replace(oldj,newj,1)
p2.write_text(s2,encoding='utf-8')
print('P15_CONTRACT_STRICTNESS_OK')
