#!/usr/bin/env python3
"""Validate frozen native inputs with pinned tokenizers; never load model weights."""
import argparse, copy, hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument('--model', choices=['nimble','semif'], required=True)
ap.add_argument('--root', type=Path, required=True)
ap.add_argument('--report', type=Path, required=True)
a=ap.parse_args()
root=a.root.resolve()
case_path=root/'data/bfcl_v4/cases.jsonl'
expected='2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8'
actual=hashlib.sha256(case_path.read_bytes()).hexdigest()
assert actual==expected, (actual,expected)
sys.path.insert(0,str(root/'inference'))
spec=importlib.util.spec_from_file_location('runner', root/f'inference/{a.model}/run.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
cases,manifest=runner.load_cases(case_path)
assert len(cases)==250
from transformers import AutoTokenizer
import torch, transformers

source = Path('/data/home/pritish/jev-model-performance/inference/nimble/.cache/nimble-upstream') if a.model=='nimble' else Path('/data/home/pritish/jev-model-performance/.cache/third_party/semif')
source_revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
assert source_revision==runner.SOURCE_REVISION

if a.model=='nimble':
 sys.path.insert(0,str(source))
 from nimble.scoring.release_contract import prompt_builder
 merged=Path('/data/home/pritish/.cache/jev-model-performance-dgx59/nimble-9b-merged-bd792f44')
 identity=json.loads((merged/'READY.json').read_text())
 assert identity['model_revision']==runner.MODEL_REVISION
 tokenizer=AutoTokenizer.from_pretrained(merged,local_files_only=True)
 build=prompt_builder(merged,tokenizer)
 max_tokens=8192
 def payload(case):
  return {'state':case['jev']['laya']['state'],'schema':runner.canonical_schema(case)}
 def prepare(case):
  p=payload(case)
  prepared=build(tokenizer,p['state'],p['schema'],max_tokens,system_role=True)
  assert prepared.names==['next']
  assert prepared.choices[0]==case['jev']['option_ids']
  ids=prepared.full_ids[0]
  return len(ids),hashlib.sha256(json.dumps(ids).encode()).hexdigest(),prepared.candidate_ids[0]
else:
 from semif_phase1.direct import encode_prompt
 from semif_phase1 import __file__ as semif_file
 assert Path(semif_file).resolve().is_relative_to(source.resolve())
 tokenizer=AutoTokenizer.from_pretrained(runner.MODEL_ID,revision=runner.MODEL_REVISION,local_files_only=True)
 identity={'model_id':runner.MODEL_ID,'model_revision':runner.MODEL_REVISION,'source_revision':source_revision}
 max_tokens=4096
 payload=runner.to_semif_input
 def prepare(case):
  p=payload(case)
  assert [o['id'] for o in p['options']]==case['jev']['option_ids']
  ids,slots,prompt_hash=encode_prompt(tokenizer,p,max_tokens)
  return len(ids),prompt_hash,slots

rows=[]
for case in cases:
 altered=copy.deepcopy(case)
 altered['gold_next_action_ids']=['GOLD_MUST_NOT_REACH_MODEL']
 altered['source']={'untrusted':'SOURCE_MUST_NOT_REACH_MODEL'}
 assert payload(case)==payload(altered),case['id']
 tokens,prompt_hash,slots=prepare(case)
 assert tokens<=max_tokens and len(set(slots))==len(case['jev']['option_ids'])
 rows.append({'case_id':case['id'],'input_tokens':tokens,'prompt_sha256':prompt_hash,'option_ids':case['jev']['option_ids'],'candidate_token_ids':slots})
report={'schema':'bfcl-v4-native-input-preflight/v1','model':a.model,'cases_sha256':actual,'case_count':len(cases),'source_revision':source_revision,'model_identity':identity,'token_limit':max_tokens,'min_input_tokens':min(r['input_tokens'] for r in rows),'max_input_tokens':max(r['input_tokens'] for r in rows),'mean_input_tokens':sum(r['input_tokens'] for r in rows)/len(rows),'no_truncation':True,'source_and_gold_excluded_from_model_payload':True,'runtime':{'torch':torch.__version__,'cuda':torch.version.cuda,'transformers':transformers.__version__,'visible_gpu':os.environ.get('CUDA_VISIBLE_DEVICES'),'gpu_names':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]},'rows':rows}
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
