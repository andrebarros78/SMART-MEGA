"""Reproducing archived 3078 training cutoff from historical 3077 + official receipt."""
import numpy as np
import pytest

from research.SMART_MEGA_SELECTOR_RESEARCH_BACKTEST_20261031 import append_canonical_result


OFFICIAL_3078={
    "numero":3078,"numeroConcursoAnterior":3077,
    "dataApuracao":"29/10/2026","listaDezenas":["05","07","12","29","34","36"]
}


def test_causal_replay_appends_only_one_authenticated_consecutive_result():
    draws=np.array([[1,2,3,4,5,6]],dtype=int)
    contests=np.array([3077],dtype=int)
    new_draws,new_contests=append_canonical_result(draws,contests,OFFICIAL_3078)
    assert new_contests.tolist()==[3077,3078]
    assert new_draws.tolist()==[[1,2,3,4,5,6],[5,7,12,29,34,36]]
    assert draws.tolist()==[[1,2,3,4,5,6]]
    assert contests.tolist()==[3077]


@pytest.mark.parametrize("payload,previous", [
    (OFFICIAL_3078,3076),
    ({**OFFICIAL_3078,"numero":3079},3077),
    ({**OFFICIAL_3078,"numeroConcursoAnterior":3076},3077),
    ({**OFFICIAL_3078,"listaDezenas":["05","07","12","29","34","34"]},3077),
])
def test_replay_rejects_temporal_and_integrity_mismatch(payload,previous):
    with pytest.raises(ValueError):
        append_canonical_result(np.array([[1,2,3,4,5,6]],dtype=int),np.array([previous],dtype=int),payload)