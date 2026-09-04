from pathlib import Path
import json
import smart_promote_cartography_1000 as pc

ROOT=Path(__file__).resolve().parent

def test_promoted_p1p2_artifacts_are_bound_and_non_predictive():
    proof=json.loads((ROOT/'SMART_P1_P2_CARTOGRAPHY_PROOF.json').read_text(encoding='utf-8-sig'))
    manifest=json.loads((ROOT/'SMART_NULL_UNIVERSE_MANIFEST.json').read_text(encoding='utf-8-sig'))
    atlas=json.loads((ROOT/'SMART_RANDOMNESS_ATLAS.json').read_text(encoding='utf-8-sig'))
    assert proof['replications']==1000
    assert manifest['replications']==atlas['replications']==1000
    assert proof['p1_manifest_sha256']==pc.sha(ROOT/'SMART_NULL_UNIVERSE_MANIFEST.json')
    assert proof['p2_atlas_sha256']==pc.sha(ROOT/'SMART_RANDOMNESS_ATLAS.json')
    assert proof['freeze_3054_sha256']==pc.FREEZE_SHA
    assert proof['predictive_weight_authorized'] is False
    assert proof['terminal_6of6_proven'] is False
