from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_sequential_prospective_proof.py'
s=p.read_text(encoding='utf-8-sig')
if 'import adjudicate_signal_challenger as adj' not in s:
    s=s.replace('import smart_champion_challenger as cc\n', 'import smart_champion_challenger as cc\nimport adjudicate_signal_challenger as adj\nimport smart_v2_engine as e\nfrom smart_signal_agent import SmartSignalAgent, write_state\n')
old="    out=sp.complete_prospective_cycle(through,target,ledger,through,learned,start=30)\n    assert out['status']=='PROSPECTIVE_CYCLE_COMPLETE'\n"
new="    adj.adjudicate(through,target,ledger)\n    draws,contests=e.load_draws(through)\n    agent=SmartSignalAgent(start=30); agent.replay_history(draws,contests)\n    st=agent.state_document(data_sha256=sp.sha256_file(through)); st.update({'sequential_learning_target':target,'learning_after_adjudication':True})\n    write_state(learned,st)\n    lr=sp.append_learning_update(ledger,target,learned,through); assert lr['status']=='LEARNING_RECORDED'\n    pr=sp.append_sequence_proof(ledger,target); assert pr['status']=='SEQUENCE_PROVEN'\n"
if old not in s: raise SystemExit('cycle marker missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('p12 cycle test fixed')
