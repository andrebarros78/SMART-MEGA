from collections import deque
import numpy as np
from smart_context_regime import ContextRegimeEngine, TOTAL_WINDOW

class FakeDetector:
    def __init__(self, drift_detected=True):
        self.drift_detected=drift_detected
        self.width=1
        self.estimation=0.0
    def update(self, value):
        return None

def primed_engine():
    e=ContextRegimeEngine()
    row=np.zeros(60,dtype=float); row[:6]=1.0
    e.recent_rows=deque([row.copy() for _ in range(TOTAL_WINDOW)])
    e.reference_sum=np.sum(list(e.recent_rows)[:300],axis=0)
    e.recent_sum=np.sum(list(e.recent_rows)[300:],axis=0)
    e.last_score=0.0
    e.cooldown=0
    return e

def test_adwin_alert_activates_context_even_below_fixed_threshold():
    e=primed_engine(); e.score_detector=FakeDetector(True)
    assert e.active is True

def test_adwin_alert_counts_detection_on_update():
    e=primed_engine(); e.score_detector=FakeDetector(True)
    before=e.detection_count
    e.update([1,2,3,4,5,6])
    assert e.detection_count==before+1
    assert e.cooldown>0

def test_no_alert_and_low_score_remains_inactive():
    e=primed_engine(); e.score_detector=FakeDetector(False)
    assert e.active is False
