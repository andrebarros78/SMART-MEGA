"""Exact redundant signal vectors cannot receive independent research votes."""
from pathlib import Path

import pytest

from smart_native_signal_research import make_contribution, build_research_challenger


def test_distinct_alias_producers_with_identical_scores_are_rejected(tmp_path: Path):
    cutoff = tmp_path / "cutoff.bin"
    cutoff.write_bytes(b"controlled N-1 data, no target result")
    vector = {str(i): float(i / 60) for i in range(1, 61)}
    a = make_contribution(
        "frontier_gap_hazard", vector,
        data_path=cutoff, target_contest=602, epoch_id="REPLAY-602",
    )
    b = make_contribution(
        "frontier_recent_lift", dict(vector),
        data_path=cutoff, target_contest=602, epoch_id="REPLAY-602",
    )
    with pytest.raises(ValueError, match="redundan|duplicate"):
        build_research_challenger(
            [a,b],
            {"frontier_gap_hazard": 0.1, "frontier_recent_lift": 0.1},
        )


def test_inverted_distinct_information_is_not_exact_duplicate(tmp_path: Path):
    cutoff = tmp_path / "cutoff.bin"
    cutoff.write_bytes(b"controlled causal data")
    a = make_contribution(
        "frontier_gap_hazard",
        {str(i): float(i / 60) for i in range(1, 61)},
        data_path=cutoff, target_contest=602, epoch_id="REPLAY-602",
    )
    b = make_contribution(
        "frontier_recent_lift",
        {str(i): float((61 - i) / 60) for i in range(1, 61)},
        data_path=cutoff, target_contest=602, epoch_id="REPLAY-602",
    )
    candidate = build_research_challenger(
        [a,b],
        {"frontier_gap_hazard": 0.05, "frontier_recent_lift": 0.1},
    )
    assert candidate["research_only"] is True
    assert candidate["production_authority"] is False
    assert len(candidate["ranking60"]) == 60



def test_affine_rescaled_same_information_is_not_two_votes(tmp_path: Path):
    cutoff = tmp_path / "cutoff.bin"
    cutoff.write_bytes(b"controlled causal data only")
    a = make_contribution(
        "frontier_gap_hazard",
        {str(i): float(i / 60) for i in range(1, 61)},
        data_path=cutoff, target_contest=603, epoch_id="REPLAY-603",
    )
    b = make_contribution(
        "frontier_recent_lift",
        {str(i): float((i / 60) * 3 + 7) for i in range(1, 61)},
        data_path=cutoff, target_contest=603, epoch_id="REPLAY-603",
    )
    with pytest.raises(ValueError, match="redundant duplicate"):
        build_research_challenger(
            [a, b],
            {"frontier_gap_hazard": 0.05, "frontier_recent_lift": 0.10},
        )
