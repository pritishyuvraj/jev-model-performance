#!/usr/bin/env python3
import argparse, ctypes, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--provider',choices=['rizzo','nanojev'],required=True)
p.add_argument('--cases',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
EXPECTED='2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8'
raw=a.cases.read_bytes()
digest=hashlib.sha256(raw).hexdigest()
assert digest==EXPECTED,(digest,EXPECTED)
cases=[json.loads(l) for l in raw.splitlines() if l.strip()]
assert len(cases)==250
shared=Path('/data/home/pritish/jev-model-performance')
cache=Path('/data/home/pritish/.cache/jev-model-performance-dgx59')
records=[]
if a.provider=='rizzo':
    sys.path.insert(0,str(shared/'.cache/third_party/rizzo/src'))
    from rizzo_flow.llama_cpp import Library, Session
    from rizzo_flow.backend_llama import LlamaTokenizer
    from rizzo_flow.compat import SystemOneRequest, to_native
    from rizzo_flow.prompts import compile_request
    library=Library.open(cache/'rizzo/llama.cpp/build/bin')
    params=library.llama_model_default_params()
    params.vocab_only=True
    params.n_gpu_layers=0
    targets=(ctypes.c_void_p*2)(None,None)
    params.devices=targets
    model=library.llama_model_load_from_file(str(cache/'rizzo/rizzo-flow-q8.gguf').encode(),params)
    assert model,'Cannot load native GGUF tokenizer'
    session=Session.__new__(Session)
    session.library=library
    session.model=model
    session.vocab=library.llama_model_get_vocab(model)
    try:
        tokenizer=LlamaTokenizer(session,session.chat_template())
        for case in cases:
            wire=SystemOneRequest.model_validate({'model':'rizzo-latest',**case['jev']['laya']})
            native,_=to_native(wire)
            prefix,compiled=compile_request(tokenizer,native,8192)
            assert len(compiled)==1
            question=compiled[0]
            records.append({'case_id':case['id'],'max_native_tokens':len(question.tokens),'shared_prefix_tokens':len(prefix),'prompt_sha256':question.prompt_sha256,'candidate_count':len(question.slots),'context_limit':8192,'truncated':False})
    finally:
        library.llama_model_free(model)
else:
    sys.path.insert(0,str(shared/'.cache/third_party/nanojev/scripts'))
    sys.path.insert(0,str(shared/'.cache/third_party/nanojev'))
    from transformers import AutoTokenizer
    from predict_toy_decisions import prepare_examples
    checkpoint=cache/'nanojev/checkpoint'
    tokenizer=AutoTokenizer.from_pretrained(checkpoint/'tokenizer',local_files_only=True,trust_remote_code=False)
    if tokenizer.pad_token is None:tokenizer.pad_token=tokenizer.eos_token
    limit=json.loads((checkpoint/'config.json').read_text())['max_length']
    for case in cases:
        wire=case['jev']['laya']
        native={'states':[{'id':'case','state':wire['state'],'questions':wire['questions']}]}
        examples=prepare_examples(native,tokenizer,limit)
        assert len(examples)==1
        ex=examples[0]
        token_lengths=list(map(len,ex['leaf_tokens']))
        rendered_segments=[f"State:\n{wire['state']}\n",f"Question type: choice\nQuestion:\n{wire['questions']['next']['instructions']}\n"]
        rendered_candidates=[f"Candidate:\n{t}\nDecision:" for t in ex['candidate_texts']]
        records.append({'case_id':case['id'],'max_native_tokens':max(token_lengths),'candidate_path_tokens':token_lengths,'native_segments_sha256':hashlib.sha256(json.dumps([rendered_segments,rendered_candidates],ensure_ascii=False).encode()).hexdigest(),'candidate_count':len(ex['candidate_ids']),'context_limit':limit,'truncated':False})
summary={'schema':'bfcl-v4-native-token-preflight/v1','provider':a.provider,'completed_at_utc':datetime.now(timezone.utc).isoformat(),'dataset_sha256':digest,'cases':len(records),'truncated_cases':0,'max_native_tokens':max(r['max_native_tokens'] for r in records),'records':records}
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
