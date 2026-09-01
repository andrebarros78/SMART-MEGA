from pathlib import Path
root=Path(r'C:\New Projet\SMART-MEGA')
p=root/'smart_multi_challengers.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace("                            redundancy_audit: dict[str, Any], context_state: dict[str, Any]) -> dict[str, Any]:\n", "                            redundancy_audit: dict[str, Any], context_state: dict[str, Any],\n                            audit_detail: bool = True) -> dict[str, Any]:\n")
old="""        policies[policy_id] = {
            'policy_id': policy_id,
            'top6': top6,
            'ranking60': ranking60,
            'aggregate_scores': aggregate_scores,
            'weights': weights,
            'max_weight': float(max(weights.values())),
            'family_totals': fam_totals,
            'context_active': bool(context_state.get('active', False)),
            'selection_authority': False,
        }
"""
new="""        policies[policy_id] = {
            'policy_id': policy_id,
            'top6': top6,
            'ranking60': ranking60 if audit_detail else [],
            'aggregate_scores': aggregate_scores if audit_detail else {},
            'weights': weights,
            'max_weight': float(max(weights.values())),
            'family_totals': fam_totals,
            'context_active': bool(context_state.get('active', False)),
            'selection_authority': False,
            'audit_detail': bool(audit_detail),
        }
"""
if old not in s: raise SystemExit('policy block not found')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')

p=root/'smart_signal_agent.py'
s=p.read_text(encoding='utf-8-sig')
old="multi = build_multi_challengers(sc, weights, metrics, families, redundancy_audit, self.context_engine.metrics())"
new="multi = build_multi_challengers(sc, weights, metrics, families, redundancy_audit, self.context_engine.metrics(), audit_detail=audit_detail)"
if old not in s: raise SystemExit('agent call not found')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
print('optimized replay audit')