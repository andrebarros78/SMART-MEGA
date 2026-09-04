import json

import numpy as np
import pytest

import smart_falsification_lab as fl
import smart_randomness_cartography as rc


def sample(n=160, seed=71):
    return rc.u0_uniform_iid(n, np.random.default_rng(seed))


def test_holm_adjust_known_values_and_order():
    adjusted = fl.holm_adjust([0.01, 0.04, 0.03])
    assert adjusted == pytest.approx([0.03, 0.06, 0.06])


def test_regime_cusum_detects_adversarial_switch():
    controls = rc.u6_adversarial_controls(600, np.random.default_rng(17))
    null_score = fl.regime_max_cusum(controls["u6_null_control"])
    switch_score = fl.regime_max_cusum(controls["u6_regime_switch"])
    assert switch_score > null_score


def test_evaluation_is_reproducible_and_never_promotes():
    draws = sample()
    contests = np.arange(1000, 1000 + len(draws))
    first = fl.evaluate_falsification(draws, contests, replications=20, seed=9)
    second = fl.evaluate_falsification(draws, contests, replications=20, seed=9)
    assert first == second
    assert first["schema"] == fl.SCHEMA
    assert len(first["comparisons"]) == 10
    assert first["multiplicity"]["method"] == "Holm"
    assert first["predictive_weight_authorized"] is False
    assert first["terminal_6of6_proven"] is False
    assert first["holdout_integrity"] == "RETROSPECTIVE_TIME_SPLIT_NOT_PRISTINE"
    assert all(
        row["predictive_weight_authorized"] is False
        for row in first["comparisons"]
    )


def test_rejects_too_few_replications():
    draws = sample()
    with pytest.raises(ValueError, match="at least 20"):
        fl.evaluate_falsification(
            draws, np.arange(1, len(draws) + 1), replications=19
        )


def test_write_preregisters_before_report_and_binds_hashes(monkeypatch, tmp_path):
    draws = sample()
    contests = np.arange(2000, 2000 + len(draws))
    monkeypatch.setattr(fl, "load_draws", lambda _: (draws, contests))
    data = tmp_path / "data.xlsx"
    data.write_bytes(b"fixed-data")
    prereg = tmp_path / "prereg.json"
    report = tmp_path / "report.json"

    design, result = fl.write_artifacts(
        data,
        prereg,
        report,
        replications=20,
        seed=23,
        expected_max_contest=int(contests.max()),
    )

    prereg_document = json.loads(prereg.read_text(encoding="utf-8"))
    report_document = json.loads(report.read_text(encoding="utf-8"))
    assert prereg_document["design_sha256"] == design["design_sha256"]
    assert report_document["preregistration_design_sha256"] == design["design_sha256"]
    assert report_document["data_sha256"] == fl._sha256_file(data)
    assert result["report_sha256"] == report_document["report_sha256"]


def test_write_rejects_future_cutoff(monkeypatch, tmp_path):
    draws = sample()
    contests = np.arange(3000, 3000 + len(draws))
    monkeypatch.setattr(fl, "load_draws", lambda _: (draws, contests))
    data = tmp_path / "data.xlsx"
    data.write_bytes(b"x")
    with pytest.raises(ValueError, match="future contest"):
        fl.write_artifacts(
            data,
            tmp_path / "pre.json",
            tmp_path / "report.json",
            replications=20,
            expected_max_contest=int(contests.max()) - 1,
        )


def test_falsification_reports_monte_carlo_resolution():
    draws = sample(160, seed=77)
    contests = np.arange(1, 161)
    out = fl.evaluate_falsification(
        draws,
        contests,
        replications=20,
        seed=8,
        holdout_fraction=0.30,
    )
    assert out["multiplicity"]["minimum_replications_for_resolution"] == 199
    assert out["multiplicity"]["resolution_sufficient"] is False


def test_fast_mi_matches_reference_binary_mi():
    draws=sample(220,seed=101); x=fl.onehot(draws)
    reference=float(np.mean([fl.binary_mi(x[:-1,j],x[1:,j]) for j in range(60)]))
    assert fl._lag1_binary_mutual_information_mean_bits(x) == pytest.approx(reference,abs=1e-14,rel=1e-12)


def test_fast_network_clustering_matches_reference_networkx():
    draws=sample(260,seed=102); x=fl.onehot(draws)
    reference=float(fl.network_structure(draws)['average_clustering'])
    assert fl._network_average_clustering_from_onehot(x) == pytest.approx(reference,abs=1e-14,rel=1e-12)


def test_selective_metric_vector_matches_full_projection():
    draws=sample(180,seed=103); full=fl.metric_vector(draws)
    for metric in fl.ALL_METRICS:
        assert fl.metric_vector(draws,{metric})[metric] == pytest.approx(full[metric],abs=1e-14,rel=1e-12)


def test_default_replications_have_holm_resolution():
    assert fl.FAMILY_SIZE == 10
    assert fl.MIN_REPLICATIONS_FOR_HOLM_RESOLUTION == 199
    assert fl.DEFAULT_REPLICATIONS >= fl.MIN_REPLICATIONS_FOR_HOLM_RESOLUTION
