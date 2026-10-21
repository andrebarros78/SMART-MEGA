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
class OfficialLearningPITTests(unittest.TestCase):
 def test_official_consumer_rejects_future_checkpoint(self):
  from smart_video_learning import get_visual_features
  prior={'status':'ACTIVE','training_contests':[101],'training_sha256':{},'normalized_event_center':0.5,'observed_spread':0.1,'eligible_observations':1,'active':True}
  with patch('smart_video_learning.learned_motion_prior',return_value=prior):
   with self.assertRaisesRegex(ValueError,'PIT_FUTURE_OR_TARGET_CONTEST'):
    get_visual_features('101','2026-10-21T12:00:00Z')
 def test_official_consumer_accepts_prior_only(self):
  from smart_video_learning import get_visual_features
  prior={'status':'ACTIVE','training_contests':[100],'training_sha256':{},'normalized_event_center':0.5,'observed_spread':0.1,'eligible_observations':1,'active':True}
  with patch('smart_video_learning.learned_motion_prior',return_value=prior):
   result=get_visual_features('101','2026-10-21T12:00:00Z')
   self.assertEqual(result['source_contests'],[100])
   self.assertEqual(result['predictive_weight'],0.0)

if __name__=='__main__':unittest.main()
