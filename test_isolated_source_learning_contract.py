"""Isolated regression: legacy access must never authorize media observation."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from isolated_source_gate.source_gate_versioned_reader import read_effective_gate
from isolated_source_gate.pipeline_contract import guarded_features,guarded_observation
class SourceGateTests(unittest.TestCase):
 def test_legacy_block_dominates(self):
  with TemporaryDirectory() as d:
   out=read_effective_gate(d,Path(d)/'ledger.sqlite',lambda _: {'state':'BLOCKED','reason':'YOUTUBE_SIGN_IN_REQUIRED'},False)
   self.assertEqual(out['state'],'BLOCKED')
 def test_unblocked_legacy_without_authority_is_blocked(self):
  with TemporaryDirectory() as d:
   out=read_effective_gate(d,Path(d)/'ledger.sqlite',lambda _: {'state':'UNBLOCKED'},False)
   self.assertEqual(out['state'],'BLOCKED')
 def test_blocked_does_not_invoke_observer(self):
  called=[]
  out=guarded_observation(lambda:{'state':'BLOCKED'},lambda:called.append(True))
  self.assertEqual(called,[])
  self.assertEqual(out['predictive_weight'],0)
 def test_pit_target_contest_rejected(self):
  def reader(**_):return {'source_contests':[101], 'predictive_weight':0.0,'as_of_utc':'2026-10-21T12:00:00Z'}
  with self.assertRaises(ValueError):guarded_features(reader,101,'2026-10-21T12:00:00Z')
 def test_pit_future_contest_rejected(self):
  def reader(**_):return {'source_contests':[102], 'predictive_weight':0.0,'as_of_utc':'2026-10-21T12:00:00Z'}
  with self.assertRaises(ValueError):guarded_features(reader,101,'2026-10-21T12:00:00Z')
 def test_pit_cutoff_mismatch_rejected(self):
  def reader(**_):return {'source_contests':[100], 'predictive_weight':0.0,'as_of_utc':'2026-10-22T12:00:00Z'}
  with self.assertRaises(ValueError):guarded_features(reader,101,'2026-10-21T12:00:00Z')
 def test_predictive_promotion_rejected(self):
  def reader(**_):return {'source_contests':[100], 'predictive_weight':0.1,'as_of_utc':'2026-10-21T12:00:00Z'}
  with self.assertRaises(ValueError):guarded_features(reader,101,'2026-10-21T12:00:00Z')
if __name__=='__main__':unittest.main()
