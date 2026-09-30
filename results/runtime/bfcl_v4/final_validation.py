#!/usr/bin/env python3
import difflib, hashlib, importlib.util, json, math, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

root = Path('/data/home/pritish/jev-model-performance-v4-dgx59-20260929')
shared = Path('/data/home/pritish/jev-model-performance')
runtime = root / 'results/runtime/bfcl_v4'
expected = '2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8'
casepath = root / 'data/bfcl_v4/cases.jsonl'
assert hashlib.sha256(casepath.read_bytes()).hexdigest() == expected
cases = [json.loads(l) for l in casepath.read_text().splitlines() if l.strip()]
assert len(cases) == len({c['id'] for c in cases}) == 250
casebyid = {c['id']: c for c in cases}
manifest = json.loads((casepath.parent / 'manifest.json').read_text())
for c in cases:
    assert c['score_eligible'] is True and len(c['gold_next_action_ids']) == 1
    assert c['gold_next_action_ids'][0] in c['jev']['option_ids']
    assert list(c['jev']['laya']['questions']['next']['criteria']) == c['jev']['option_ids']
    assert [o['id'] for o in c['jev']['options']] == c['jev']['option_ids']

checks = {}
models = ['laya', 'kev', 'nimble', 'semif', 'rizzo', 'von', 'nanojev']
for provider in models:
    path = root / f'results/bfcl_v4_{provider}.jsonl'
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    meta = json.loads(path.with_suffix('.meta.json').read_text())
    summary = json.loads(path.with_suffix('.summary.json').read_text())
    oldmeta = json.loads((shared / f'results/bfcl_v1_{provider}.meta.json').read_text())
    run = meta['run']
    assert run['cases_sha256'] == expected
    for field in ['dataset_schema', 'meta_card_version', 'selection_review_sha256']:
        assert run[field] == manifest['schema' if field == 'dataset_schema' else field]
    rid = hashlib.sha256(json.dumps(run, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert rid == meta['run_id'] and summary['run'] == run
    for field in ['declared_model_revision', 'requested_model']:
        assert run[field] == oldmeta['run'][field]
    assert len(rows) == len({r['case_id'] for r in rows}) == 250
    assert set(r['case_id'] for r in rows) == set(casebyid)
    strata = ['multi_tool_call', 'one_tool_call', 'one_tool_no_call']
    groups = {s: {'count': 0, 'exact_correct': 0, 'route_correct': 0, 'selected_meta': Counter()} for s in strata}
    max_sum_error = 0
    rounding_ties = 0
    for row in rows:
        c = casebyid[row['case_id']]
        assert row['run_id'] == rid and row['attempt'] == 1 and row['status'] == 'ok'
        assert row.get('http_retries', 0) == 0  # SemIf is native, with no HTTP transport.
        assert row['category'] == c['category'] and row['gold_action'] == c['gold_next_action_ids'][0]
        tools = [o['id'] for o in c['jev']['options'] if o['kind'] == 'tool']
        stratum = 'one_tool_no_call' if c['kind'] == 'no_call' else ('one_tool_call' if len(tools) == 1 else 'multi_tool_call')
        assert row['stratum'] == stratum
        probs = row['probabilities']
        assert set(probs) == set(c['jev']['option_ids'])
        assert all(type(p) in [float, int] and math.isfinite(p) and 0 <= p <= 1 for p in probs.values())
        error = abs(math.fsum(probs.values()) - 1)
        max_sum_error = max(max_sum_error, error)
        assert error < .002
        chosen = row['predicted_action']
        assert chosen in probs
        if max(probs, key=probs.get) != chosen:
            assert max(probs.values()) - probs[chosen] <= .0001, (provider, row['case_id'])
            rounding_ties += 1
        exact = chosen == c['gold_next_action_ids'][0]
        assert row['correct'] == exact
        route = exact or (c['kind'] == 'no_call' and chosen in ['no_tool', 'clarify', 'cannot_answer'])
        g = groups[stratum]
        g['count'] += 1
        g['exact_correct'] += exact
        g['route_correct'] += route
        if chosen in ['no_tool', 'clarify', 'cannot_answer']:
            g['selected_meta'][chosen] += 1
    exact = sum(g['exact_correct'] for g in groups.values())
    route = sum(g['route_correct'] for g in groups.values())
    assert summary['overall']['correct'] == exact and summary['overall']['tool_selection_correct'] == route
    assert summary['overall']['errors'] == 0 and summary['completed_count'] == summary['expected_count'] == 250
    assert summary['is_complete']
    for s, g in groups.items():
        assert summary['by_stratum'][s]['total'] == g['count']
        assert summary['by_stratum'][s]['correct'] == g['exact_correct']
        assert summary['by_stratum'][s]['tool_selection_correct'] == g['route_correct']
        g['selected_meta'] = dict(g['selected_meta'])
    positives = groups['multi_tool_call']['exact_correct'] + groups['one_tool_call']['exact_correct']
    checks[provider] = dict(case_count=250, unique_cases=250, errors=0, attempts_per_case=1,
        transport_retries=0, run_id=rid, run_id_recomputed=True, gold_data_alignment=True,
        probabilities_valid=True, max_probability_sum_error=max_sum_error,
        selected_argmax_within_1e_4=True, rounding_tie_cases=rounding_ties,
        exact_action_correct=exact, route_correct=route, positive_tool_correct=positives,
        positive_tool_total=200, negative_exact_no_tool_correct=groups['one_tool_no_call']['exact_correct'],
        negative_no_function_correct=groups['one_tool_no_call']['route_correct'], groups=groups,
        checkpoint_revision_matches_v1=True, result_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    print(provider, exact, route, positives, groups['one_tool_no_call']['exact_correct'], groups['one_tool_no_call']['route_correct'])

# Verify every model's exact native input preflight.
preflights = {}
for provider in models:
    if provider in ['laya', 'kev', 'von']:
        pre = json.loads((runtime / provider / 'preflight.json').read_text())
        assert pre['cases_sha256'] == expected and pre['checked_count'] == 250 and not pre['failures']
        preflights[provider] = dict(count=250, failures=0, max_input_tokens=pre['max_input_tokens'])
    elif provider in ['nimble', 'semif']:
        pre = json.loads((runtime / f'{provider}_input_preflight.json').read_text())
        assert pre['cases_sha256'] == expected and pre['case_count'] == 250 and pre['no_truncation']
        preflights[provider] = dict(count=250, failures=0, max_input_tokens=pre['max_input_tokens'], limit=pre['token_limit'])
    else:
        pre = json.loads((runtime / f'{provider}_native_preflight.json').read_text())
        assert pre['dataset_sha256'] == expected and pre['cases'] == 250 and pre['truncated_cases'] == 0
        preflights[provider] = dict(count=250, failures=0, max_input_tokens=pre['max_native_tokens'], limit=8192)

# NanoJev bridge preserves payload and identity; mapping is tested against a recorded native response.
bridgepath = root / 'inference/nanojev/bridge.py'
spec = importlib.util.spec_from_file_location('validation_nano_bridge', bridgepath)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
assert bridgepath.read_bytes() == (shared / 'inference/nanojev/bridge.py').read_bytes()
pre = json.loads((runtime / 'nanojev_native_preflight.json').read_text())
for c, r in zip(cases, pre['records']):
    native = bridge.native_request({'model': bridge.MODEL, **c['jev']['laya']})
    assert native['states'][0]['state'] == c['jev']['laya']['state']
    assert native['states'][0]['questions'] == c['jev']['laya']['questions']
    assert list(native['states'][0]['questions']['next']['criteria']) == c['jev']['option_ids']
    assert r['case_id'] == c['id'] and r['candidate_count'] == len(c['jev']['option_ids'])
probe = json.loads((runtime / 'nanojev_native_execution_probe.json').read_text())
converted = bridge.systemone_response(probe, Path('/data/home/pritish/.cache/jev-model-performance-dgx59/nanojev/checkpoint'))
firstrow = json.loads((root / 'results/bfcl_v4_nanojev.jsonl').read_text().splitlines()[0])
assert converted['answers']['next']['probabilities'] == probe['states'][0]['answers']['next']['probabilities']
assert converted['answers']['next']['choice'] == firstrow['predicted_action']
delta = max(abs(p - firstrow['probabilities'][k]) for k, p in converted['answers']['next']['probabilities'].items())
assert delta < 1e-6
execution = probe['execution']
assert execution['parameter_storage'] == 'float32' and execution['forward_autocast'] == 'bfloat16'
assert execution['disable_native_triton'] is False and execution['max_length'] == 8192
assert execution['batch_questions_limit'] == 'all' and probe['temperature']['value'] == 1.0
nano = dict(bridge_byte_identical_to_v1=True, all_250_state_questions_and_option_keys_preserved=True,
    native_candidate_count_matches_every_case=True, native_response_mapping_unchanged=True,
    post_run_probe_choice_matches_first_record=True, post_run_probability_delta=delta,
    actual_forward_storage='float32', actual_forward_autocast='bfloat16', disable_native_triton=False,
    context_limit=8192, temperature=1.0, finding='No adapter or option mapping defect found in checked paths; low positive routing score preserved without retraining or selection-dependent changes.')

# V1 comparison uses executed shared source and existing V1 manifests.
diffs = {}
for provider in ['nimble', 'semif']:
    a = shared / f'inference/{provider}/run.py'
    b = root / f'inference/{provider}/run.py'
    diff = list(difflib.unified_diff(a.read_text().splitlines(keepends=True), b.read_text().splitlines(keepends=True)))
    diffs[provider] = dict(shared_v1_sha256=hashlib.sha256(a.read_bytes()).hexdigest(),
        v4_sha256=hashlib.sha256(b.read_bytes()).hexdigest(),
        changed_lines=[l.strip() for l in diff if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))],
        review='Only imports, run metadata/schema and SemIf docstring differ. Native prompt, readout, token limit and precision unchanged.')
for provider in ['laya', 'kev', 'nanojev']:
    old = json.loads((shared / f'results/bfcl_v1_{provider}.meta.json').read_text())['server_identity']
    new = json.loads((root / f'results/bfcl_v4_{provider}.meta.json').read_text())['server_identity']
    assert old == new
old = json.loads((shared / 'results/bfcl_v1_rizzo.meta.json').read_text())['server_identity']['health_model']
new = json.loads((runtime / 'rizzo_health.json').read_text())['model']
for k in ['fingerprint', 'precision', 'llama_cpp_commit', 'source_files', 'prompt_version', 'context_cells']:
    assert old[k] == new[k]
for provider in ['nimble', 'semif']:
    old = json.loads((shared / f'results/bfcl_v1_{provider}.meta.json').read_text())['run']
    new = json.loads((root / f'results/bfcl_v4_{provider}.meta.json').read_text())['run']
    for k in ['dtype', 'temperature', 'runtime', 'mode', 'backend', 'max_input_tokens', 'source_revision', 'base_revision', 'adapter_sha256', 'upstream_revision']:
        if k in old:
            assert old[k] == new[k], (provider, k)
vonenv = json.loads((runtime / 'von/environment.json').read_text())
assert vonenv['no_chains'] is True and vonenv['on_overflow'] == 'refuse'
assert vonenv['independent_options'] is True and vonenv['digit_split'] is False
assert '--no-chains' in (shared / 'inference/von/serve.sh').read_text()

# Scan for credential-shaped values, never their literals or generic token field names.
patterns = {
    'hugging_face': r'\bhf_[A-Za-z0-9]{25,}\b',
    'github': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{25,})\b',
    'openai_style': r'\bsk-[A-Za-z0-9_-]{25,}\b',
    'slack': r'\bxox[baprs]-[A-Za-z0-9-]{20,}\b',
    'aws_access_key': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'private_key_block': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'credential_assignment': r'(?i)\b(?:HF_TOKEN|HUGGING_FACE_HUB_TOKEN|GITHUB_TOKEN|GH_TOKEN|OPENAI_API_KEY|AWS_SECRET_ACCESS_KEY)\s*[=:]\s*["\']?[A-Za-z0-9_/-]{20,}',
}
files = [p for p in runtime.rglob('*') if p.is_file() and p.suffix in ['.json', '.log', '.txt']]
files += list((root / 'results').glob('bfcl_v4_*.meta.json')) + list((root / 'results').glob('bfcl_v4_*.summary.json'))
files = list(dict.fromkeys(files))
counts = {k: 0 for k in patterns}
matched_files = 0
for p in files:
    content = p.read_text(errors='replace')
    found = False
    for name, pattern in patterns.items():
        count = len(re.findall(pattern, content))
        counts[name] += count
        found = found or count > 0
    matched_files += found
scan = dict(files_scanned=len(files), match_counts=counts, files_with_matches=matched_files,
    values_recorded_or_printed=False,
    note='Package names such as tokenizers and source literals such as access_token are not credential patterns. This is a bounded pattern scan, not proof about arbitrary secrets.')
validation = dict(schema='bfcl-v4-final-independent-validation/v1',
    verified_at_utc=datetime.now(timezone.utc).isoformat(), dataset_sha256=expected,
    dataset_count=250, models_checked=7, all_models_passed_log_and_gold_checks=True,
    all_checkpoint_revisions_match_v1=True,
    groups=dict(multi_tool_call=150, one_tool_call=50, one_tool_no_call=50),
    model_checks=checks, native_preflights=preflights, nanojev_adapter_review=nano,
    v1_runtime_parity=dict(laya_kev_nanojev_identities_equal=True,
        rizzo_runtime_fingerprint_equal=True, nimble_semif_scoring_config_equal=True,
        von_no_chains=True, von_overflow='refuse', von_independent_options=True, von_digit_split=False,
        von_precision='FP32 native default'),
    adapter_metadata_only_diffs=diffs, credential_pattern_scan=scan,
    notes=['Each model retained its native published prompt/readout adapter; token preflights covered all 250 inputs without truncation.',
        'Nano native runtime probe followed the benchmark and is excluded from result rows.',
        'This checks frozen dataset and prediction integrity; it does not re-audit every source label or evaluate arguments.'])
(runtime / 'final_validation.json').write_text(json.dumps(validation, indent=2) + '\n')
print('Final validation saved. Credential pattern counts:', counts)
assert sum(counts.values()) == 0, 'Credential-shaped strings require review before publication'
