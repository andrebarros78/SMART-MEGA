from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import smart_randomness_cartography as rc
from smart_v2_engine import load_draws

SCHEMA='SMART_MONTE_CARLO_CONVERGENCE_V2'
CHECKPOINTS=(20,50,100,200)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract(atlas: dict[str,Any]) -> dict[str,Any]:
    out={}
    for family,metrics in atlas['null_comparisons'].items():
        out[family]={}
        for metric,row in metrics.items():
            out[family][metric]={
                'null_mean':float(row['null_mean']),
                'null_std':float(row['null_std']),
                'empirical_two_sided_p':float(row['empirical_two_sided_p']),
            }
    return out


def _summarize_rows(rows: list[dict[str,Any]]) -> dict[str,Any]:
    stable=[row for row in rows if not row.get('degenerate_final_null',False)]
    degenerate=[row for row in rows if row.get('degenerate_final_null',False)]
    return {
        'max_p_abs_delta':max((row['p_abs_delta'] for row in stable),default=0.0),
        'median_p_abs_delta':float(np.median([row['p_abs_delta'] for row in stable])) if stable else 0.0,
        'max_mean_delta_in_final_null_sd':max((row['mean_delta_in_final_null_sd'] for row in stable),default=0.0),
        'degenerate_metric_count':len(degenerate),
        'max_degenerate_mean_abs_delta':max((row['mean_abs_delta'] for row in degenerate),default=0.0),
        'rows':rows,
    }


def _compare_checkpoint(current: dict[str,Any], final: dict[str,Any]) -> dict[str,Any]:
    rows=[]
    for family in sorted(final):
        for metric in sorted(final[family]):
            a=current[family][metric]; b=final[family][metric]
            final_sd=abs(float(b['null_std']))
            degenerate=final_sd < 1e-12
            denom=max(final_sd,1e-12)
            rows.append({
                'family':family,
                'metric':metric,
                'p_abs_delta':abs(float(a['empirical_two_sided_p'])-float(b['empirical_two_sided_p'])),
                'mean_abs_delta':abs(float(a['null_mean'])-float(b['null_mean'])),
                'final_null_std':final_sd,
                'degenerate_final_null':degenerate,
                'mean_delta_in_final_null_sd':abs(float(a['null_mean'])-float(b['null_mean']))/denom,
            })
    return _summarize_rows(rows)


def repair_existing(root: Path) -> dict[str,Any]:
    path=root/'SMART_MONTE_CARLO_CONVERGENCE_1000.json'
    doc=json.loads(path.read_text(encoding='utf-8'))
    final_atlas=json.loads((root/'SMART_RANDOMNESS_ATLAS_1000.json').read_text(encoding='utf-8'))
    final=_extract(final_atlas)
    for cp in doc['checkpoint_results'].values():
        rows=cp['comparison_to_final_1000']['rows']
        for row in rows:
            b=final[row['family']][row['metric']]
            final_sd=abs(float(b['null_std']))
            row['final_null_std']=final_sd
            row['degenerate_final_null']=final_sd < 1e-12
            row['mean_delta_in_final_null_sd']=row['mean_abs_delta']/max(final_sd,1e-12)
        cp['comparison_to_final_1000']=_summarize_rows(rows)
    last=doc['checkpoint_results'][str(max(int(x) for x in doc['checkpoint_results']))]['comparison_to_final_1000']
    doc['schema']=SCHEMA
    doc['stability_summary']={
        'reference_checkpoint':max(int(x) for x in doc['checkpoint_results']),
        'max_p_abs_delta_vs_1000':float(last['max_p_abs_delta']),
        'median_p_abs_delta_vs_1000':float(last['median_p_abs_delta']),
        'max_mean_delta_in_final_null_sd_vs_1000':float(last['max_mean_delta_in_final_null_sd']),
        'degenerate_metric_count':int(last['degenerate_metric_count']),
        'max_degenerate_mean_abs_delta':float(last['max_degenerate_mean_abs_delta']),
        'interpretation':'descriptive Monte Carlo convergence diagnostic; degenerate null metrics are audited as invariants and excluded from p-delta stability aggregates',
    }
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return doc


def build(root: Path, checkpoints=CHECKPOINTS, seed=rc.DEFAULT_SEED) -> dict[str,Any]:
    data=root/'Mega-Sena_through_3053_v2.xlsx'
    final_path=root/'SMART_RANDOMNESS_ATLAS_1000.json'
    if not final_path.exists():
        raise FileNotFoundError('SMART_RANDOMNESS_ATLAS_1000.json is required')
    final_atlas=json.loads(final_path.read_text(encoding='utf-8'))
    if int(final_atlas.get('replications',0)) != 1000:
        raise ValueError('final atlas must contain 1000 replications')
    draws,contests=load_draws(data)
    final=_extract(final_atlas)
    checkpoint_results={}
    for replications in checkpoints:
        atlas=rc.build_atlas(draws,contests,replications=int(replications),seed=int(seed))
        extracted=_extract(atlas)
        checkpoint_results[str(replications)]={
            'replications':int(replications),
            'comparison_to_final_1000':_compare_checkpoint(extracted,final),
        }
    last=checkpoint_results[str(max(checkpoints))]['comparison_to_final_1000']
    return {
        'schema':SCHEMA,
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'data_file':data.name,
        'data_sha256':sha(data),
        'cutoff_contest':int(final_atlas['contest_max']),
        'seed':int(seed),
        'checkpoints':[int(x) for x in checkpoints],
        'final_replications':1000,
        'final_atlas_sha256':sha(final_path),
        'checkpoint_results':checkpoint_results,
        'stability_summary':{
            'reference_checkpoint':max(checkpoints),
            'max_p_abs_delta_vs_1000':float(last['max_p_abs_delta']),
            'median_p_abs_delta_vs_1000':float(last['median_p_abs_delta']),
            'max_mean_delta_in_final_null_sd_vs_1000':float(last['max_mean_delta_in_final_null_sd']),
            'interpretation':'descriptive Monte Carlo convergence diagnostic only; thresholds are not predictive promotion criteria',
        },
        'predictive_weight_authorized':False,
        'terminal_6of6_proven':False,
    }


def write(root: Path) -> dict[str,Any]:
    doc=build(root)
    (root/'SMART_MONTE_CARLO_CONVERGENCE_1000.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return doc


if __name__=='__main__':
    import sys
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
    doc=write(root)
    print(json.dumps({'final_replications':doc['final_replications'],**doc['stability_summary']},ensure_ascii=False))
