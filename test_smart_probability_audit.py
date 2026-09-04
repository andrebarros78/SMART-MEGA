import pytest

import smart_probability_audit as pa


def source_document():
    rows = {}
    for candidate, shift in (("alpha", 0.0), ("beta", 0.002)):
        values = []
        for index in range(120):
            contest = 2000 + index
            values.append(
                {
                    "contest": contest,
                    "cutoff_contest": contest - 1,
                    "split": "holdout",
                    "top6": [1, 2, 3, 4, 5, 6],
                    "hits": index % 3,
                    "champion_hits": 0,
                    "delta_hits": index % 3,
                    "novelty": 1.0,
                    "brier": 0.091 + shift,
                }
            )
        rows[candidate] = values
    document = {
        "schema": "TEST_FRONTIER",
        "future_leakage": False,
        "rows": rows,
    }
    document["sha256"] = pa.sha256_json(document)
    return document


def test_uniform_brier_constant():
    assert pa.UNIFORM_MEAN_BRIER == pytest.approx(0.09)


def test_moving_block_ci_is_reproducible():
    values = [0.001, 0.002, 0.003, 0.004] * 30
    first = pa.moving_block_mean_ci(values, 200, seed=7, block_size=8)
    second = pa.moving_block_mean_ci(values, 200, seed=7, block_size=8)
    assert first == second
    assert first["lower"] - 1e-15 <= first["mean"] <= first["upper"] + 1e-15


def test_audit_validates_and_never_promotes_historical_rows():
    audit = pa.audit_historical(
        source_document(),
        mc_replications=1000,
        bootstrap_replications=200,
        seed=9,
    )
    assert audit["schema"] == pa.SCHEMA
    assert audit["candidate_count"] == 2
    assert audit["causal_cutoff_verified_all"] is True
    assert audit["predictive_weight_authorized"] is False
    assert audit["terminal_6of6_proven"] is False
    assert all(
        row["decision"] == "RETAIN_UNIFORM_BASELINE"
        for row in audit["candidates"].values()
    )


def test_audit_rejects_hash_tampering():
    source = source_document()
    source["future_leakage"] = True
    with pytest.raises(ValueError, match="hash mismatch"):
        pa.audit_historical(
            source,
            mc_replications=1000,
            bootstrap_replications=200,
        )


def test_audit_rejects_noncausal_cutoff():
    source = source_document()
    source["rows"]["alpha"][0]["cutoff_contest"] = 2000
    source["sha256"] = pa.sha256_json(
        {key: value for key, value in source.items() if key != "sha256"}
    )
    with pytest.raises(ValueError, match="causal contest ordering"):
        pa.audit_historical(
            source,
            mc_replications=1000,
            bootstrap_replications=200,
        )
