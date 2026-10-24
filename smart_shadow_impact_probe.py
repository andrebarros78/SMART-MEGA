"""Read-only influence measurement for verified but incompletely covered rescue evidence."""
import json
from pathlib import Path

from smart_false_negative_rescue import build_profile_from_reports, apply_rescue
from smart_primary_card_selector import select_primary_card
import smart_v2_engine as engine
import freeze_next_research as champion_engine


def measure(root: Path) -> dict:
    root = root.resolve()
    draws, contests = engine.load_draws(root / "Mega-Sena.xlsx")
    cutoff = int(contests[-1])
    champion = champion_engine.current_policy(draws, start=1000)
    profile = build_profile_from_reports(root, through_contest=cutoff)
    base_scores, audit = apply_rescue(champion["aggregate_scores"], profile)
    base_ranking = sorted(range(1, 61), key=lambda n: (-float(base_scores[str(n)]), n))
    baseline = select_primary_card(base_scores, ranking60=base_ranking)
    shadow_delta = audit.get("shadow_nonzero_deltas") or {}
    simulated = {str(n): float(base_scores[str(n)]) + float(shadow_delta.get(str(n), 0.0))
                 for n in range(1, 61)}
    shadow_ranking = sorted(range(1, 61), key=lambda n: (-float(simulated[str(n)]), n))
    shadow = select_primary_card(simulated, ranking60=shadow_ranking)
    return {
        "schema": "SMART_RESCUE_EFFECT_SHADOW_MEASUREMENT_1",
        "cutoff": cutoff,
        "target": cutoff + 1,
        "observations": profile["observations"],
        "quarantined_reports": profile["quarantined_reports"],
        "recovered_verified_evidence": profile["recovered_verified_evidence"],
        "evidence_coverage": profile["evidence_coverage"],
        "production_rescue_status": audit["status"],
        "production_nonzero_adjustments": len(audit.get("nonzero_deltas") or {}),
        "shadow_nonzero_adjustments": len(shadow_delta),
        "shadow_l1_score_effect": sum(abs(float(v)) for v in shadow_delta.values()),
        "shadow_ranking_positions_changed": sum(a != b for a,b in zip(base_ranking, shadow_ranking)),
        "baseline_top6": sorted(champion["top6"]),
        "baseline_selected_card": baseline["selected_numbers"],
        "verified_feedback_shadow_card": shadow["selected_numbers"],
        "shadow_card_differs": baseline["selected_numbers"] != shadow["selected_numbers"],
        "shadow_scores_promoted": False,
        "predictive_weight_authority": False,
        "freeze_generated": False,
    }


if __name__ == "__main__":
    print(json.dumps(measure(Path(__file__).resolve().parent), sort_keys=True, ensure_ascii=False))
