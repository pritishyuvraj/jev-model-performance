import os,sys,json,hashlib,subprocess,types,threading
from pathlib import Path
from importlib import metadata
provider=sys.argv[1]
runroot=Path('/data/home/pritish/jev-model-performance-v4-dgx59-20260929')
cache=Path('/data/home/pritish/.cache/jev-model-performance-dgx59')
out=runroot/'results/runtime/bfcl_v4'/provider
out.mkdir(parents=True,exist_ok=True)
os.environ['HF_HOME']=str(cache/'hf')
os.environ['HF_HUB_OFFLINE']='1'
casepath=runroot/'data/bfcl_v4/cases.jsonl'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert digest(casepath)=='2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8'
cases=[json.loads(s) for s in casepath.read_text().splitlines() if s.strip()]
assert len(cases)==250
import torch
from transformers import AutoTokenizer
packages={d.metadata['Name']: {'version':d.version,'direct_url':json.loads(d.read_text('direct_url.json')) if d.read_text('direct_url.json') else None} for d in metadata.distributions()}
audit={'provider':provider,'python':sys.version,'packages':packages,'torch':torch.__version__,'cuda':torch.version.cuda,'cuda_available':torch.cuda.is_available(),'hostname':subprocess.check_output(['hostname'],text=True).strip(),'gpu_inventory':subprocess.check_output(['nvidia-smi','--query-gpu=index,name,uuid,driver_version,memory.total','--format=csv,noheader'],text=True),'cases_sha256':digest(casepath)}
rows=[]
if provider=='laya':
 from laya.common import build_sequence,render_options
 snapshot=cache/'hf/hub/models--convaiinnovations--laya/snapshots/55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851/typed-decisions'
 tokpath=snapshot/'tokenizer';tok=AutoTokenizer.from_pretrained(tokpath,local_files_only=True)
 audit['weight_sha256']={'model.safetensors':digest(snapshot/'model.safetensors')}
 assert audit['weight_sha256']['model.safetensors']=='4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e'
 assert digest(tokpath/'tokenizer.json')=='6c8aaa9a542084f2457eab775d4eeb51f92a70c0fd9de28d5edb0ddec3c08d30'
 audit.update({'checkpoint_revision':'55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851','source_revision':'9d955671415fc19f069b9cc998928075c1f255ec','dtype':'fp16 CUDA autocast','gpu_index':0,'port':18007,'limits':{'max_len':1024,'head_max_len':256,'per_option':48},'checkpoint_config':json.loads((snapshot/'rl_agent_config.json').read_text())})
 assert audit['checkpoint_config']['max_len']==1024 and audit['checkpoint_config']['head_max_len']==256
 for case in cases:
  p=case['jev']['laya'];q=p['questions']['next'];q={'t':q['type'],'ins':q['instructions'],'crit':q['criteria']}
  clean=lambda s:s.replace(tok.mask_token,' ')
  encode=lambda s:tok(s,add_special_tokens=False)['input_ids']
  instruction=encode('choice question: '+clean(q['ins']))
  optionids=[encode(' '+clean(text)) for text in render_options(q)]
  expected=[tok.cls_token_id]+instruction+[tok.sep_token_id]
  for option in optionids:expected += [tok.mask_token_id]+option
  expected += [tok.sep_token_id]+encode(clean(p['state']))+[tok.sep_token_id]
  native,markers,stats=build_sequence(tok,p['state'],q,max_len=1024,head_max_len=256,return_stats=True)
  assert native==expected,case['id']
  assert stats['options']==stats['options_distinct']==len(q['crit']),case['id']
  rows.append({'id':case['id'],'input_tokens':len(native),'head_tokens':len(instruction)+sum(1+len(i) for i in optionids),'longest_option_tokens':max(map(len,optionids)),'fits_without_truncation':True})
 audit['tokenizer_sha256']=digest(tokpath/'tokenizer.json')
elif provider=='kev':
 from kev.api import SystemOneRequest,to_record
 from kev.model import encode,SERVE_MAX_STATE,SERVE_MAX_BRANCH,SERVE_MAX_PACKED
 snapshot=cache/'hf/hub/models--jaredpalmer--kev-0.8b/snapshots/9a45d25eb2ab761841196625383fa1dff0e56c1e'
 base=cache/'hf/hub/models--Qwen--Qwen3.5-0.8B-Base/snapshots/dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68'
 tok=AutoTokenizer.from_pretrained(base,local_files_only=True)
 audit.update({'checkpoint_revision':'9a45d25eb2ab761841196625383fa1dff0e56c1e','base_revision':'dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68','source_revision':'461b5eac35d96e95c7dede21b9e0402b4cf7092d','dtype':'fp32','fused':False,'cuda_graphs':False,'gpu_index':1,'port':18008,'limits':{'max_state':SERVE_MAX_STATE,'max_branch':SERVE_MAX_BRANCH,'max_packed':SERVE_MAX_PACKED},'tokenizer_sha256':digest(base/'tokenizer.json')})
 audit['weight_sha256']={str(p.relative_to(snapshot)):digest(p) for p in snapshot.rglob('*') if p.is_file() and p.suffix in ['.pt','.safetensors']}
 for case in cases:
  rec,_=to_record(SystemOneRequest(**case['jev']['laya']))
  enc=encode(tok,rec,max_state=SERVE_MAX_STATE,max_branch=SERVE_MAX_BRANCH,strict=True)
  assert not enc['state_truncated'] and len(enc['ids'])<=SERVE_MAX_PACKED,case['id']
  rows.append({'id':case['id'],'input_tokens':len(enc['ids']),'fits_without_truncation':True})
elif provider=='von':
 from von.models.option_marker import OptionMarkerModel,split_digits
 from von.backends.option_marker_backend import OptionMarkerBackend
 snapshot=cache/'von/43bbca0fb17f424539416ee8eb3de33cfc3dacf3'
 tok=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,model_max_length=8192)
 hashes={'model.safetensors':'af57d5d2ab15715a753a1eb4add4271d1aecce7e76f3365f629c082df329297a','option_marker.pt':'3faf27f88d30aaf9aa37860d4cdef99f1d05450cf40364f6236ac892d4d139ed','marker_calibration.json':'9b32949dcd0cfd122db509c9bd5be67f0cfe35696153aa93d667caf0aae147c9'}
 audit['weight_sha256']={name:digest(snapshot/name) for name in hashes}
 assert audit['weight_sha256']==hashes
 calib=json.loads((snapshot/'marker_calibration.json').read_text())
 model=types.SimpleNamespace(tokenizer=tok,digit_split=bool(calib.get('digit_split',False)),encoder=types.SimpleNamespace(config=types.SimpleNamespace(max_position_embeddings=8192)))
 model.pack_sequence=types.MethodType(OptionMarkerModel.pack_sequence,model)
 backend=OptionMarkerBackend.__new__(OptionMarkerBackend);backend.max_state_tokens=8192;backend.on_overflow='refuse';backend._trunc_local=threading.local()
 audit.update({'checkpoint_revision':'43bbca0fb17f424539416ee8eb3de33cfc3dacf3','source_revision':'a930f9d5709e62388cd4d3bd45675aaaf323b973','dtype':'fp32 native default','gpu_index':5,'port':18014,'no_chains':True,'on_overflow':'refuse','independent_options':bool(calib.get('independent_options',False)),'digit_split':model.digit_split,'tokenizer_sha256':digest(snapshot/'tokenizer.json'),'limits':{'max_state_tokens':8192,'encoder_window':8192}})
 for case in cases:
  p=case['jev']['laya'];q=p['questions']['next'];desc=[v.strip() if v else k.strip() for k,v in q['criteria'].items()]
  fitted=backend._fit_state(model,p['state'],q['instructions'],desc)
  assert fitted==p['state'],case['id']
  packed=model.pack_sequence(fitted,q['instructions'],desc)
  ids=tok(packed)['input_ids']
  assert len(ids)<=8192 and ids.count(tok.mask_token_id)==len(desc),case['id']
  rows.append({'id':case['id'],'input_tokens':len(ids),'fits_without_truncation':True})
else:raise ValueError(provider)
preflight={'provider':provider,'cases_sha256':digest(casepath),'checked_count':len(rows),'failures':[],'max_input_tokens':max(r['input_tokens'] for r in rows),'method':'Exact native input construction/tokenization only; no model inference.','per_case':rows}
(out/'environment.json').write_text(json.dumps(audit,indent=2)+'\n')
(out/'preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
print(json.dumps({k:v for k,v in preflight.items() if k!='per_case'},indent=2),flush=True)
