from pathlib import Path
ROOT=Path(r'C:\New Projet\SMART-MEGA')

# P12 linear supersede chain validation.
p=ROOT/'smart_sequential_prospective_proof.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("        'single_active_freeze_required': True,\n", "        'single_active_freeze_required': True,\n        'linear_supersede_chain_required': True,\n",1)
marker="""def _event_chain(events: list[tuple[int, dict[str, Any]]], stop_before_proof: bool = True) -> tuple[list[str], str]:\n"""
helper="""def _is_hex64(value: Any) -> bool:\n    if not isinstance(value, str) or len(value) != 64:\n        return False\n    try:\n        int(value, 16)\n        return True\n    except ValueError:\n        return False\n\n\ndef _validate_supersede_chain(events: list[tuple[int, dict[str, Any]]]) -> str:\n    active_hash: str | None = None\n    pending_new: str | None = None\n    seen_freezes: set[str] = set()\n    for _, ev in events:\n        et = ev.get('event_type')\n        if et == 'FREEZE':\n            h = str(ev.get('freeze_sha256', ''))\n            if not _is_hex64(h) or h in seen_freezes:\n                raise ValueError('invalid or duplicate freeze hash in supersede chain')\n            if pending_new is not None:\n                raise ValueError('new freeze encountered before prior supersede was linked')\n            seen_freezes.add(h)\n            if active_hash is None:\n                active_hash = h\n            else:\n                pending_new = h\n        elif et == 'SUPERSEDE':\n            old = str(ev.get('old_freeze_sha256', ''))\n            new = str(ev.get('new_freeze_sha256', ''))\n            if not _is_hex64(old) or not _is_hex64(new) or old == new:\n                raise ValueError('invalid supersede hash linkage')\n            if pending_new is None:\n                raise ValueError('supersede event requires a preceding new freeze')\n            if old != active_hash or new != pending_new:\n                raise ValueError('supersede must replace exactly the previously active freeze')\n            active_hash = pending_new\n            pending_new = None\n        elif pending_new is not None:\n            raise ValueError('supersede event must immediately link a newly appended freeze')\n    if pending_new is not None:\n        raise ValueError('new freeze is missing its supersede linkage')\n    if active_hash is None:\n        raise ValueError('supersede chain requires at least one freeze')\n    return active_hash\n\n\n"""+marker
if marker not in s: raise SystemExit('P12 insertion marker missing')
s=s.replace(marker,helper,1)
old="""    events = _target_events(ledger, target)\n    active = _active_freeze_from_events(events)\n"""
new="""    events = _target_events(ledger, target)\n    chain_active_hash = _validate_supersede_chain(events)\n    active = _active_freeze_from_events(events)\n"""
if old not in s: raise SystemExit('P12 validate marker missing')
s=s.replace(old,new,1)
old2="""    active_i, active_fr = active\n    freeze_indices = [i for i, ev in events if ev.get('event_type') == 'FREEZE']\n"""
new2="""    active_i, active_fr = active\n    if str(active_fr.get('freeze_sha256')) != chain_active_hash:\n        raise ValueError('active freeze resolution disagrees with supersede chain')\n    freeze_indices = [i for i, ev in events if ev.get('event_type') == 'FREEZE']\n"""
if old2 not in s: raise SystemExit('P12 active marker missing')
s=s.replace(old2,new2,1)
p.write_text(s,encoding='utf-8')

# P14 independent chain validation inside audit_prospective_ledger.
p=ROOT/'smart_independent_audit.py'
s=p.read_text(encoding='utf-8-sig')
marker="""def audit_prospective_ledger(root: Path, ledger_path: Path) -> dict[str, Any]:\n"""
helper="""def _audit_supersede_chains(events: list[dict[str, Any]]) -> dict[int, str]:\n    states: dict[int, dict[str, Any]] = {}\n    for ev in events:\n        et = ev.get('event_type')\n        if et not in {'FREEZE', 'SUPERSEDE'}:\n            continue\n        target = int(ev.get('target_contest', -1))\n        state = states.setdefault(target, {'active': None, 'pending': None, 'seen': set()})\n        if et == 'FREEZE':\n            h = str(ev.get('freeze_sha256', ''))\n            if not _is_hex64(h) or h in state['seen']:\n                raise ValueError('invalid or duplicate freeze hash in independent supersede audit')\n            if state['pending'] is not None:\n                raise ValueError('new freeze encountered before prior supersede linkage')\n            state['seen'].add(h)\n            if state['active'] is None:\n                state['active'] = h\n            else:\n                state['pending'] = h\n        else:\n            old = str(ev.get('old_freeze_sha256', ''))\n            new = str(ev.get('new_freeze_sha256', ''))\n            if not _is_hex64(old) or not _is_hex64(new) or old == new:\n                raise ValueError('invalid supersede hash linkage')\n            if state['pending'] is None:\n                raise ValueError('supersede event requires preceding new freeze')\n            if old != state['active'] or new != state['pending']:\n                raise ValueError('supersede must replace exactly the independently resolved active freeze')\n            state['active'] = state['pending']\n            state['pending'] = None\n    out: dict[int, str] = {}\n    for target, state in states.items():\n        if state['pending'] is not None:\n            raise ValueError('new freeze is missing supersede linkage')\n        if state['active'] is not None:\n            out[target] = str(state['active'])\n    return out\n\n\n"""+marker
if marker not in s: raise SystemExit('P14 insertion marker missing')
s=s.replace(marker,helper,1)
old="""    events = ledger['events']\n    freezes: dict[str, tuple[int, dict[str, Any]]] = {}\n"""
new="""    events = ledger['events']\n    independently_active = _audit_supersede_chains(events)\n    freezes: dict[str, tuple[int, dict[str, Any]]] = {}\n"""
if old not in s: raise SystemExit('P14 event marker missing')
s=s.replace(old,new,1)
old2="""        freeze_sha = str(ad.get('freeze_sha256', ''))\n        if freeze_sha not in freezes:\n"""
new2="""        freeze_sha = str(ad.get('freeze_sha256', ''))\n        if independently_active.get(target) != freeze_sha:\n            raise ValueError('adjudication does not reference independently resolved active freeze')\n        if freeze_sha not in freezes:\n"""
if old2 not in s: raise SystemExit('P14 active validation marker missing')
s=s.replace(old2,new2,1)
s=s.replace("        'hash_integrity': True,\n", "        'hash_integrity': True,\n        'supersede_chain_integrity': True,\n",1)
p.write_text(s,encoding='utf-8')
print('SUPERSEDE_CHAIN_HARDENING_OK')
