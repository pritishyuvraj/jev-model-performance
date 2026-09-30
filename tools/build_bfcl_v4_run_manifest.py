#!/usr/bin/env python3
"""Build a reproducible checksum index for the completed V4 run, without inference."""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
from summarize_runs import ROOT, build_rows


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    metrics=build_rows(ROOT,'v4')
    data=json.loads((ROOT/'data/bfcl_v4/manifest.json').read_text())
    models={}
    for row in metrics:
        key=row['model_id'];p=ROOT/f'results/bfcl_v4_{key}.meta.json';m=json.loads(p.read_text());run=m['run']
        assert run['selection_review_sha256']==data['selection_review_sha256']
        assert run['meta_card_version']==data['meta_card_version']
        expected=hashlib.sha256(json.dumps(run,sort_keys=True,separators=(',',':')).encode()).hexdigest();assert m['run_id']==expected
        models[key]={'run_id':m['run_id'],'requested_model':run['requested_model'],
                     'declared_model_revision':run['declared_model_revision'],
                     'metadata_file':p.relative_to(ROOT).as_posix(),'metrics':row}
    checks=json.loads((ROOT/'results/runtime/bfcl_v4/final_validation.json').read_text())
    assert checks['dataset_sha256']==data['cases_sha256'] and checks['models_checked']==7
    assert checks['all_models_passed_log_and_gold_checks'] and checks['all_checkpoint_revisions_match_v1']
    files=[p for p in (ROOT/'results/runtime/bfcl_v4').rglob('*') if p.is_file() and p.suffix!='.pid']
    files += [ROOT/f'results/bfcl_v4_{key}.{suffix}' for key in models for suffix in ['jsonl','meta.json','summary.json']]
    files += [ROOT/'results/bfcl_v4_comparison.csv']
    code={name:digest(ROOT/name) for name in ['inference/evaluate.py','inference/nimble/run.py','inference/semif/run.py','inference/nanojev/bridge.py']}
    result={'schema':'bfcl-v4-seven-model-run-manifest/v1',
        'dataset':{'cases_sha256':data['cases_sha256'],'source_commit':data['source_commit'],
                   'selection_review_sha256':data['selection_review_sha256'],'meta_card_version':data['meta_card_version'],
                   'count':250,'category_counts':data['category_counts'],'normalized_v1_overlap_count':0},
        'execution':{'host':'vp-dgx-59','hostname':'dgxh100-059','gpu':'NVIDIA H100 80GB HBM3','driver':'570.195.03',
                     'gpu_assignment':{'laya':0,'kev':1,'nimble':2,'semif':3,'rizzo':4,'von':5,'nanojev':6},
                     'code_snapshot_commit':'aa4130c30e3146ec1d5e2b228ccc49923934139a','evaluation_code_sha256':code,
                     'requests':'Sequential per model; separate GPUs used by concurrently active models.',
                     'warmup':'Direct scorers and Rizzo/Nano resume scored smoke2; Laya/Kev/Von have separate smoke3.',
                     'all_owned_servers_stopped':True,'gpu_cleanup_observed':'All 8 GPUs: 0 MiB used, 0% utilization.'},
        'completed_predictions':1750,'request_errors':0,'http_retries':0,'native_inputs_pass_without_truncation':True,
        'independent_validation_file':'results/runtime/bfcl_v4/final_validation.json',
        'models':models,'artifact_sha256':{p.relative_to(ROOT).as_posix():digest(p) for p in sorted(files)}}
    output=ROOT/'results/bfcl_v4_run_manifest.json';output.write_text(json.dumps(result,indent=2)+'\n');print(output)
    viewer=ROOT/'data/bfcl_v4/viewer.html';html=viewer.read_text()
    embedded=json.loads(re.search(r'<script type="application/json" id="result-data">(.*?)</script>',html,re.S)[1]);assert len(embedded)==7
    for x in embedded:assert len(x['rows'])==250
    validation=ROOT/'data/bfcl_v4/validation_report.json';v=json.loads(validation.read_text())
    assert v['cases_sha256']==data['cases_sha256']
    v.update(viewer_sha256=digest(viewer),viewer_embedded_model_runs=7,model_inference_performed=True,
             dataset_creation_performed_inference=False,evaluation_run_manifest_file='results/bfcl_v4_run_manifest.json')
    validation.write_text(json.dumps(v,indent=2)+'\n')


if __name__=='__main__':main()
