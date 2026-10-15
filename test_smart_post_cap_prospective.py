"""Adversarial unit tests: all outcomes used here are synthetic, never scientific evidence."""
import copy
import json
from pathlib import Path

import pytest

import smart_post_cap_prospective as p

REG = Path(__file__).parent / "release_evidence/PROSPECTIVE_CAP60/REGISTRATION_3071.json"


def registered():
    return json.loads(REG.read_text(encoding="utf-8"))


def mock_official(contest=3071, numbers=None, date="18/10/2026"):
    if numbers is None:
        numbers = [19, 27, 29, 43, 54, 60]
    return {"numero": contest, "dataApuracao": date,
            "listaDezenas": [f"{n:02d}" for n in numbers]}


def test_actual_git_preregistration_self_hash_and_zero_result_leakage():
    reg = p.verify_registration(registered())
    assert reg["target_contest"] == 3071
    assert reg["cutoff_contest"] == 3070
    assert reg["controls"]["actual_numbers"] is None
    assert reg["candidate"]["numbers"] == reg["baseline"]["numbers"]
    assert reg["controls"]["promote_to_main"] is False


def test_any_json_modification_is_detected():
    reg = registered()
    reg["candidate"]["numbers"][0] = 3
    with pytest.raises(ValueError, match="self-hash"):
        p.verify_registration(reg)


def test_tampering_hash_can_not_bypass_no_target_result_rule():
    reg = registered()
    reg["controls"]["result_used"] = True
    reg["registration_sha256"] = p.canonical_sha256({
        k: v for k, v in reg.items() if k != "registration_sha256"
    })
    with pytest.raises(ValueError, match="result leakage"):
        p.verify_registration(reg)


def test_register_rejects_illegal_date_time_and_code_fingerprint():
    reg = registered()
    reg["expected_draw_brasilia"] = "2026-10-18T11:00:00"
    reg["registration_sha256"] = p.canonical_sha256({k: v for k, v in reg.items() if k != "registration_sha256"})
    with pytest.raises(ValueError, match="timezone"):
        p.verify_registration(reg)
    reg = registered()
    reg["candidate"]["source_file_sha256"] = "not a hash"
    reg["registration_sha256"] = p.canonical_sha256({k: v for k, v in reg.items() if k != "registration_sha256"})
    with pytest.raises(ValueError, match="source pin"):
        p.verify_registration(reg)


def test_fake_official_wrong_contest_rejected():
    with pytest.raises(ValueError, match="not registered target"):
        p.assess_series([registered()], [mock_official(3070)])


def test_fake_official_wrong_draw_day_rejected():
    with pytest.raises(ValueError, match="differs"):
        p.assess_series([registered()], [mock_official(date="19/10/2026")])


def test_six_unique_megasena_numbers_only():
    for bad in ([1, 2, 3, 4, 5, 5], [1, 2, 3, 4, 5, 61], [True, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5]):
        with pytest.raises(ValueError, match="six"):
            p.strict_numbers(bad)


def test_same_card_3071_must_produce_zero_delta_and_e_one():
    reg = registered()
    for fake_numbers in ([1, 2, 3, 4, 5, 6], [10, 11, 27, 38, 43, 53]):
        report = p.assess_series([reg], [mock_official(numbers=fake_numbers)])
        assert report["baseline_hits"] == report["candidate_hits"]
        assert report["delta_total"] == 0
        assert report["e_value"] == 1.0
        assert report["eligible"] is False
        assert report["status"] == "PROSPECTIVE_NOT_PROVEN"


def test_pending_results_cannot_be_claimed_as_prospectively_proven():
    report = p.assess_series([registered()], [])
    assert report["n"] == 0
    assert report["eligible"] is False
    assert report["e_value"] == 1.0
    assert report["pending_targets"] == [3071]


def test_even_fabricated_large_superiority_cannot_promote_without_official_https():
    regs = []
    fake_results = []
    for i in range(20):
        r = copy.deepcopy(registered())
        r["target_contest"] = 4000 + i
        r["cutoff_contest"] = 3999 + i
        r["baseline"]["numbers"] = [1, 2, 3, 4, 5, 6]
        r["candidate"]["numbers"] = [55, 56, 57, 58, 59, 60]
        r["registration_sha256"] = p.canonical_sha256({
            k: v for k, v in r.items() if k != "registration_sha256"
        })
        regs.append(r)
        fake_results.append(mock_official(4000 + i, [55, 56, 57, 58, 59, 60]))
    report = p.assess_series(regs, fake_results, fetched_directly_from_caixa=False)
    assert report["built_in_gate"]["eligible"] is True
    assert report["e_value"] >= 20
    assert report["eligible"] is False
    assert "official_https_independence_not_verified" in report["blockers"]


def test_non_contiguous_or_duplicate_registrations_rejected():
    a = registered()
    with pytest.raises(ValueError, match="duplicated"):
        p.assess_series([a, a], [])


def test_result_without_corresponding_preregistration_rejected():
    with pytest.raises(ValueError, match="more results"):
        p.assess_series([registered()], [mock_official(), mock_official()])
