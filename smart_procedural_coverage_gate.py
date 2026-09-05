from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT=Path('.')
MANIFEST=ROOT/'runtime/procedural_sources/CRONOGRAM_ARCHIVE_MANIFEST.json'
DATASET=ROOT/'runtime/procedural_sources/MEGA_PROCEDURAL_CRONOGRAM_DATASET.json'
YOUTUBE=ROOT/'runtime/procedural_sources/YOUTUBE_PROCEDURAL_RECENT.json'
VENUE=ROOT/'runtime/historical_training_shadow/PROCEDURAL_VENUE_EXPERIMENT.json'
OUT=ROOT/'runtime/procedural_sources/PROCEDURAL_COVERAGE_GATE.json'

NOISY_LOCATION_TOKENS=('DATA ','FERIADO','SORTEIOS (','INFORMAÇÕES','INFORMACOES','PAIXÃO DE CRISTO','PAIXAO DE CRISTO','CORPUS CHRISTI','CONSCIÊNCIA','CONSCIENCIA')

def noisy_location(value):
    if not value: return True
    u=str(value).upper()
    return any(t in u for t in NOISY_LOCATION_TOKENS)

def build():
    man=json.loads(MANIFEST.read_text(encoding='utf-8-sig'))
    ds=json.loads(DATASET.read_text(encoding='utf-8-sig'))
    yt=json.loads(YOUTUBE.read_text(encoding='utf-8-sig'))
    venue=json.loads(VENUE.read_text(encoding='utf-8-sig'))
    docs=man['documents']; rows=ds['rows']; yrows=yt['rows']
    found=sum(x.get('status')=='FOUND' for x in docs)
    verified=[r for r in rows if r.get('evidence_status')=='VERIFIED_CONTEST_DATE_IN_OFFICIAL_CRONOGRAM']
    loc_clean=[r for r in verified if not noisy_location(r.get('location_candidate_raw'))]
    ypass=[r for r in yrows if r.get('status')=='PASS']
    case_ids=Counter(r.get('ball_case_identifier') for r in ypass if r.get('ball_case_identifier'))
    seals=sum(bool(r.get('opening_seal_identifier')) for r in ypass)
    venue_eval=venue.get('evaluation_venue_counts') or {}
    venue_supported=[k for k,v in venue_eval.items() if k!='UNKNOWN' and v>=20]
    checks={
      'official_archive_retrieval_ge_70pct': found/max(1,len(docs))>=0.70,
      'contest_date_verification_ge_90pct': len(verified)/max(1,len(rows))>=0.90,
      'location_field_clean_ge_90pct': len(loc_clean)/max(1,len(verified))>=0.90,
      'two_venues_supported_in_untouched_evaluation': len(venue_supported)>=2,
      'physical_identifier_variation_recent': len(case_ids)>=2,
      'physical_metadata_actionable_before_bet_close': False,
    }
    report={
      'schema':'SMART_PROCEDURAL_COVERAGE_GATE_V1',
      'documents_total':len(docs),'documents_found':found,'documents_missing':len(docs)-found,
      'archive_retrieval_fraction':found/max(1,len(docs)),
      'dataset_rows':len(rows),'verified_contest_date_rows':len(verified),
      'contest_date_verification_fraction':len(verified)/max(1,len(rows)),
      'location_clean_rows':len(loc_clean),'location_clean_fraction':len(loc_clean)/max(1,len(verified)),
      'youtube_recent_rows':len(yrows),'youtube_pass_rows':len(ypass),'recent_case_ids':dict(case_ids),'recent_seals_present':seals,
      'untouched_evaluation_venue_counts':venue_eval,
      'checks':checks,
      'actionable_same_contest_fields':['official_draw_date','official_schedule','prepublished_location_when_clean_and_verified'],
      'scientific_only_fields':['ball_case_identifier','opening_seal_identifier','auditor_mentions','broadcast_pre_draw_procedure_observed_after_bet_close'],
      'predictive_weight_authorized':all(checks.values()),
      'decision':'BLOCK_PREDICTIVE_PROMOTION' if not all(checks.values()) else 'ELIGIBLE_FOR_SHADOW_PREDICTIVE_TEST',
      'reason':'procedural coverage is useful for mechanism study but lacks clean recurring venue contrast and actionable physical variation before bet close' if not all(checks.values()) else 'all coverage gates passed'
    }
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return report

if __name__=='__main__': print(json.dumps(build(),indent=2,ensure_ascii=False))
