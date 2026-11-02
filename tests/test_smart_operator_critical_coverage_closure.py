"""Operator transitions missing from the source-bound critical coverage proof."""
from pathlib import Path

import smart_operator as op
import smart_contingency_card


def test_next_contest_contingency_keeps_old_freeze_immutable(monkeypatch, tmp_path):
    lifecycle={"state":"FROZEN","target_contest":3078,"sha256":"a"*64}
    monkeypatch.setattr(op,"canonical_root",lambda root=None: tmp_path)
    monkeypatch.setattr(op,"load_lifecycle",lambda root:lifecycle)
    calls=[]
    def contingency(root,target,*,preceding_target,lifecycle_sha256):
        calls.append((root,target,preceding_target,lifecycle_sha256))
        return {"status":"CONTINGENCY_NOT_MODEL_FREEZE","scientific_proven":False}
    monkeypatch.setattr(smart_contingency_card,"generate_contingency_card",contingency)
    assert op.generate_card_operation(tmp_path,3079)=={"status":"CONTINGENCY_NOT_MODEL_FREEZE","scientific_proven":False}
    assert calls==[(tmp_path,3079,3078,"a"*64)]


def test_prepared_epoch_uses_authorized_freeze_without_new_prepare(monkeypatch,tmp_path):
    lifecycle={"state":"PREPARED","target_contest":3078}
    calls=[]
    monkeypatch.setattr(op,"canonical_root",lambda root=None:tmp_path)
    monkeypatch.setattr(op,"load_lifecycle",lambda root:lifecycle)
    monkeypatch.setattr(op,"authorize_generation_operation",lambda root,target:calls.append(("authorize",target)))
    monkeypatch.setattr(op,"freeze_operation",lambda root,target:calls.append(("freeze",target)) or {"status":"FROZEN"})
    assert op.generate_card_operation(tmp_path,3078)=={"status":"FROZEN"}
    assert calls==[("authorize",3078),("freeze",3078)]


def test_terminal_probe_only_uses_readonly_path_without_adjudication(monkeypatch,tmp_path):
    monkeypatch.setattr(op,"canonical_root",lambda root=None:tmp_path)
    monkeypatch.setattr(op,"assert_lifecycle_state",lambda root,states,*,target_contest:{"state":"FROZEN"})
    monkeypatch.setattr(op,"verify_active_epoch",lambda path:{"target_contest":3078})
    calls=[]
    monkeypatch.setattr(op.terminal_executor,"probe",lambda root,target:calls.append((root,target)) or {"status":"WAITING_OFFICIAL_RESULT"})
    monkeypatch.setattr(op.terminal_executor,"execute",lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError("read-only probe must not execute terminal")))
    undecorated=op.terminal_operation
    while hasattr(undecorated,"__wrapped__"):
        undecorated=undecorated.__wrapped__
    assert undecorated(tmp_path,3078,probe_only=True)=={"status":"WAITING_OFFICIAL_RESULT"}
    assert calls==[(tmp_path,3078)]


def test_wrong_target_rejected_before_any_generation(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(op,"canonical_root",lambda root=None:tmp_path)
    monkeypatch.setattr(op,"load_lifecycle",lambda root:{"state":"HOLD","target_contest":3078})
    monkeypatch.setattr(op,"freeze_operation",lambda *a,**k:(_ for _ in ()).throw(AssertionError("freeze forbidden for wrong contest")))
    with pytest.raises(ValueError,match="operator requested target differs from lifecycle"):
        op.generate_card_operation(tmp_path,3080)


def test_already_frozen_epoch_reuses_freeze_without_new_authorization(monkeypatch,tmp_path):
    monkeypatch.setattr(op,"canonical_root",lambda root=None:tmp_path)
    monkeypatch.setattr(op,"load_lifecycle",lambda root:{"state":"FROZEN","target_contest":3078})
    monkeypatch.setattr(op,"authorize_generation_operation",lambda *a,**k:(_ for _ in ()).throw(AssertionError("must not reauthorize frozen epoch")))
    calls=[]
    monkeypatch.setattr(op,"freeze_operation",lambda root,target:calls.append((root,target)) or {"status":"FROZEN","idempotent_replay":True})
    assert op.generate_card_operation(tmp_path,3078)=={"status":"FROZEN","idempotent_replay":True}
    assert calls==[(tmp_path,3078)]
