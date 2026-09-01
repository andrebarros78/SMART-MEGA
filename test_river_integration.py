import river
from river import base, drift, ensemble


class _ConstantRegressor(base.Regressor):
    def __init__(self, value: float):
        self.value = value

    def learn_one(self, x, y, **kwargs):
        return self

    def predict_one(self, x):
        return self.value


def test_river_version_is_pinned():
    assert river.__version__ == "0.26.1"


def test_ewa_reweights_experts_from_observed_loss():
    model = ensemble.EWARegressor(
        [_ConstantRegressor(0.0), _ConstantRegressor(1.0)],
        learning_rate=0.5,
    )
    initial = list(model.weights)
    for _ in range(12):
        model.learn_one({"signal": 1.0}, 0.0)
    final = list(model.weights)
    assert final[0] > final[1]
    assert final != initial


def test_adwin_detects_regime_shift():
    detector = drift.ADWIN(delta=0.002)
    detected = False
    for value in ([0.0] * 300 + [1.0] * 300):
        detector.update(value)
        if detector.drift_detected:
            detected = True
            break
    assert detected
