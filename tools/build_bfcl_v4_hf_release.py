#!/usr/bin/env python3
"""Build/check a flat, deterministic BFCL V4 routing dataset Hub release.

Uses only the standard library. Reads committed benchmark files, never credentials,
and never uploads. Run from the GitHub checkout; this is not an HF-clone rebuild.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urljoin

REPO_ID = 'pyuvraj/bfcl-v4-jev-routing'
CASE_SHA = '2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8'
SOURCE_SHA = 'f7cf7359b7ac615a0b294831c5ba2bc95ee4a000'
GITHUB_SHA = '043cb627cd09a74f3c8eb462e916211de61e0293'
GITHUB = 'https://github.com/pritishyuvraj/jev-model-performance'
GH_PIN = f'{GITHUB}/blob/{GITHUB_SHA}/'
GH_MAIN = f'{GITHUB}/blob/main/'
HF = f'https://huggingface.co/datasets/{REPO_ID}/'
MODELS = ('laya', 'kev', 'nimble', 'semif', 'rizzo', 'von', 'nanojev')
META_IDS = ('no_tool', 'clarify', 'cannot_answer')
MODEL_URLS = {
    'laya': 'convaiinnovations/laya-typed-decisions', 'kev': 'jaredpalmer/kev-0.8b',
    'nimble': 'bespokelabs/Bespoke-Nimble-9B', 'semif': 'Qwen/Qwen3.5-4B',
    'rizzo': 'rizzoaiacademy/rizzo-flow', 'von': 'wfzyx/von', 'nanojev': 'C-Tianyu/NanoJev',
}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def rows(value: bytes) -> list[dict]:
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def project(case: dict, manifest: dict) -> dict:
    q = case['jev']['laya']['questions']['next']
    s = case['source']
    return {
        'id': case['id'], 'stratum': case['stratum'], 'user_request': s['question'],
        'state': case['jev']['laya']['state'], 'instruction': q['instructions'],
        'options': case['jev']['options'], 'gold_action_id': case['gold_next_action_ids'][0],
        'gold_tool_names': case['gold_call_names'],
        'expected_route_kind': 'tool_call' if case['kind'] == 'single_call' else 'no_function',
        'gold_route_action_ids': case['gold_route_action_ids'],
        'full_schemas_json': json.dumps(s['functions'], ensure_ascii=False, separators=(',', ':')),
        'original_reference_json': json.dumps(s['ground_truth'], ensure_ascii=False, separators=(',', ':')),
        'source_id': s['source_id'], 'source_category': case['category'],
        'source_row_number': s['row_number'], 'source_question_file': s['question_file'],
        'source_answer_file': s['answer_file'], 'source_repository': manifest['source_repository'],
        'source_revision': manifest['source_commit'], 'label_source': case['label_source'],
        'meta_card_version': manifest['meta_card_version'],
    }


def rewrite_links(text: str, original_path: str, mapping: dict[str, str]) -> str:
    """Resolve Markdown relative links to flat HF files or pinned GitHub sources."""
    def replace(match):
        target = match.group(2)
        if re.match(r'^(?:https?://|mailto:|#)', target):
            return match.group(0)
        resolved = urljoin('https://local.invalid/' + original_path, target).split('local.invalid/', 1)[1]
        dest = HF + 'blob/main/' + mapping[resolved] if resolved in mapping else GH_PIN + resolved
        if match.group(1).startswith('!') and resolved in mapping:
            dest = HF + 'resolve/main/' + mapping[resolved]
        return match.group(1) + '(' + dest + ')'
    return re.sub(r'(!?\[[^\]]*\])\(([^\s)]+)\)', replace, text)


def result_table(root: Path, metrics: list[dict]) -> str:
    lines = ['| Model | Approx. parameters | Exact right tool (200) | Routing (250) | Exact action (250) | Mean latency | Median | P95 | Mean correct-route probability |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for m in metrics:
        p = m['model_id']
        summary = json.loads((root / f'results/bfcl_v4_{p}.summary.json').read_text())
        exact = summary['overall']['correct']
        lines.append(f"| [{m['model']}](https://huggingface.co/{MODEL_URLS[p]}) | {m['parameter_label']} | **{m['exact_right_tool_correct']}/200 ({float(m['exact_right_tool_accuracy_pct']):.1f}%)** | {m['tool_selection_correct']}/250 ({float(m['tool_selection_accuracy_pct']):.1f}%) | {exact}/250 ({exact/250*100:.1f}%) | {float(m['mean_wall_latency_ms']):.1f} ms | {float(m['median_wall_latency_ms']):.1f} ms | {float(m['p95_wall_latency_ms']):.1f} ms | {float(m['mean_correct_route_probability_pct']):.1f}% |")
    return '\n'.join(lines)


def card(root: Path, metrics: list[dict]) -> str:
    return f'''---
pretty_name: BFCL V4 Live Jev Capability Routing Pilot
license: apache-2.0
language:
  - en
  - zh
  - vi
  - pl
task_categories:
  - text-classification
tags:
  - bfcl
  - tool-selection
  - decision-models
  - jev
  - evaluation
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files:
      - split: test
        path: test.jsonl
---

# BFCL V4 Live Jev routing pilot

**250 frozen prompts for capability selection**, with saved decisions and probabilities from seven systems. Jev-style decision models choose the tool; a separate chat model supplies its arguments and asks for missing values before execution. This set scores **one routing decision**. It does not score function arguments, tool execution, final answers, or complete tasks, and is **not an official BFCL V4 function-calling or agentic score**.

Adaptation and evaluation: **Pritish Yuvraj**. Source data: **Shishir Patil and the Gorilla / Berkeley Function Calling Leaderboard contributors**. [Source repository](https://github.com/ShishirPatil/gorilla/tree/{SOURCE_SHA}/berkeley-function-call-leaderboard/bfcl_eval/data) · [BFCL leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html) · [GitHub release](https://github.com/pritishyuvraj/jev-model-performance/tree/{GITHUB_SHA}) · [Earlier V1 pilot](https://huggingface.co/datasets/pyuvraj/bfcl-v1-jev-routing).

## Inspect or download

- [Browse the 250-row test split]({HF}viewer/default/test).
- [Download the offline chat-style viewer]({HF}resolve/main/viewer.html). Save it locally and open it in a browser; it embeds every prompt, all seven models' selections/probabilities, original schemas, and review material. The Hub file browser is not an HTML app host.
- [Complete results report]({HF}blob/main/results_report.md) · [Comparison CSV]({HF}resolve/main/comparison.csv) · [All release files and hashes]({HF}blob/main/release_manifest.json).
- [Schema]({HF}blob/main/SCHEMA.md) · [Usage and exact rerun commands]({HF}blob/main/USAGE.md) · [Credits and checkpoint pins]({HF}blob/main/CREDITS.md).

```python
from datasets import load_dataset

ds = load_dataset("{REPO_ID}", "default", split="test")
assert len(ds) == 250

row = ds[0]
# Only these fields are inference inputs. Preserve option order and descriptions.
payload = {{
    "state": row["state"],
    "questions": {{"next": {{
        "type": "choice",
        "instructions": row["instruction"],
        "criteria": {{o["id"]: o["description"] for o in row["options"]}},
    }}}},
}}
# Send payload through the model's native adapter, then score its returned ID.
```

**Prevent gold leakage:** never serialize the whole dataset row to the model. `gold_*`, `expected_route_kind`, `original_reference_json`, source fields, review notes, model logs, and `full_schemas_json` are inspection/scoring material. The published runs sent only the frozen state, decision instruction, and offered option descriptions. The full schemas are retained for provenance; they were not added to those inference payloads.

The YAML config explicitly selects only **test.jsonl**. Frozen provenance and model-selection JSONL files are downloadable artifacts, not additional dataset splits. `frozen_cases.jsonl` is the byte-identical canonical evaluation file; `test.jsonl` is its flat Dataset Viewer projection.

## Composition, source and selection

| BFCL Live category | Stratum | Cases | Target |
| --- | --- | ---: | --- |
| `live_multiple` | `multi_tool_call` | 150 | One relevant function among 2–4 offered tools |
| `live_simple` | `one_tool_call` | 50 | The one relevant offered function |
| `live_irrelevance` | `one_tool_no_call` | 50 | No applicable offered function |

These three source categories contain **2,195 rows** (1,053 / 258 / 884). They originated before V4 and remain in its corpus. This selection excludes parallel calls, multi-turn execution, web search, memory, and other V4 task families. It is a curated pilot, not a random representative sample of all BFCL V4.

Source commit: `{SOURCE_SHA}`. Frozen canonical case SHA-256: `{CASE_SHA}`. Seed: `bfcl-v4-live-routing-250-20260929`. Original source file hashes, row IDs, positive references, schemas, semantic-review reasons, all candidate dispositions, exclusions, and diversity checks are provided in the `frozen_*` files.

Accepted candidates were reviewed using the complete request, descriptions, schemas and positive reference function before evaluation. Missing argument values alone do not make a tool irrelevant: argument clarification is the chat model's responsibility. Negatives require a capability mismatch or a request needing none of the offered functions. Review is agent-assisted and published for inspection; residual label ambiguity is possible.

Within each stratum, selection ranks accepted rows by `SHA256(seed + NUL + source_id)` and caps normalized request, complete unordered tool catalog, and category + Live middle-ID family. The family cap is a conservative diversity heuristic, not a documented upstream universal family definition.

**V1 request overlap is zero** under both exact and normalized comparison with all **2,000 V1 source rows** and the frozen V1 250. Normalization uses Unicode NFKC, case folding and Unicode word tokens joined with spaces. Four additional high-similarity candidates were explicitly excluded. This is not a guarantee against every semantic paraphrase or model training contamination.

V4 preserves full original tool descriptions with **zero card overrides and zero automatic truncations**. Frozen state text collapses request whitespace; `user_request` retains original source text. V4 uses versioned neutral meta cards (`bfcl-v4-neutral-meta-cards/v1`); V1 used compact cards and meta descriptions containing blanket capability limitations. Score differences between these two curated sets do not isolate a benchmark-version effect.

Requests include English, Chinese, Vietnamese and Polish; cards/instructions are predominantly English. For example, `live_multiple_7-3-2` is Chinese, `live_irrelevance_109-6-0` is Vietnamese and `live_irrelevance_484-138-1` is Polish. This small mix does not support per-language rankings.

## Metrics and recorded results

- **Exact right tool:** correct function ID on the **200 positive cases**.
- **Routing accuracy (primary):** correct function on positives; any of `no_tool`, `clarify`, `cannot_answer` on **50 negatives**.
- **Exact action:** exact function on positives and canonical `no_tool` on negatives. That negative meta target is a convention; BFCL irrelevance does not determine the best no-function disposition.
- **Mean correct-route probability:** gold function probability on positives and summed probability of the three meta actions on negatives, averaged over all 250 cases. This is option-conditional probability, not calibrated confidence or comparable raw logits.

All models completed **250/250**, with **zero request errors or retries**. No model was tuned on this set. Checkpoint revisions and native scorer settings match the V1 runs; inputs use each model's own published prompt/readout adapter. All native input preflights passed without truncation.

{result_table(root, metrics)}

The low Von and NanoJev results are retained. Von selected no function on all 50 negatives but frequently rejected offered capabilities on positives. An independent NanoJev check found no adapter/option mapping defect in the checked paths. Its game-trained checkpoint is evaluated out of domain. SemIf is a scoring method over frozen Qwen weights, Rizzo uses Q8_0 GGUF weights, and Von chains are disabled. These results do not establish the cause of either poor score.

## Charts

![Observed wall latency and exact right tool accuracy]({HF}resolve/main/chart__latency_vs_right_tool_accuracy.png)

![Approximate model size and exact right tool accuracy]({HF}resolve/main/chart__size_vs_right_tool_accuracy.png)

![Exact right tool accuracy and probability assigned to the correct function]({HF}resolve/main/chart__accuracy_vs_gold_function_probability.png)

The probability chart averages the correct **function** probability on the 200 positives; the table's correct-**route** probability also includes the 50 negatives. SVG versions and exact metric definitions are in [CHARTS.md]({HF}blob/main/CHARTS.md) and [chart_metrics.json]({HF}blob/main/chart_metrics.json).

## Timing and limitations

Runs used **NVIDIA H100 80GB GPUs** on `vp-dgx-59` (`dgxh100-059`, driver 570.195.03), one model on each of GPUs 0–6. Models ran concurrently on separate GPUs; requests within each model were sequential. Parameter counts are rounded published backbone sizes; adapters/decision heads can add parameters.

All reported table latencies use saved **wall_latency_ms over 250 responses**, without outlier removal. P95 interpolates at `0.95 × (n − 1)`. HTTP and native direct scorers have different timing boundaries and runtimes/precisions. Warmup differs: Nimble/SemIf resumed scored two-case smoke runs in new processes; Rizzo/NanoJev resumed scored smoke on warm servers; Laya/Kev/Von used separate smoke requests before the scored run. Cold overhead present in saved rows is retained. Node concurrency can affect timings. These are descriptive H100 response times, not controlled throughput or laptop measurements.

The public prompts may have appeared in training. The set is short-context and single-step, contains curated rather than random cases, and measures only routing among the offered cards. Avoid treating 100% on this set as general agent reliability. Keep these prompts frozen for evaluation and use separate development cases for tuning.

## Files, reproducibility and licensing

Seven original decision logs plus original `.meta.json` / `.summary.json` sidecars are retained byte for byte as `results__bfcl_v4_*`. Charts, metrics, the report, CSV, and the [original run manifest]({HF}blob/main/run_manifest.json) accompany them. Complete runtime consoles, assets/library hashes, package snapshots, native preflights, and independent validation remain in [GitHub runtime evidence]({GH_PIN}results/runtime/bfcl_v4/README.md); they are linked, not duplicated here.

See [USAGE.md]({HF}blob/main/USAGE.md) for loading a local JSONL, safe payload construction, hash checks, source reconstruction and exact per-model inference commands. Rebuilding the canonical evaluation requires the **GitHub repository and pinned BFCL source checkouts**; the flat HF clone is a release artifact, not a standalone inference checkout.

Adapted BFCL data retain **Apache 2.0** licensing: [LICENSE]({HF}blob/main/LICENSE), [upstream license copy]({HF}blob/main/frozen_LICENSE), [NOTICE]({HF}blob/main/NOTICE). Original adaptation/evaluation/viewer code is **MIT**: [CODE_LICENSE]({HF}blob/main/CODE_LICENSE). Model weights and native implementations retain their own upstream licenses. [CREDITS.md]({HF}blob/main/CREDITS.md) attributes every model, implementation and checkpoint revision.
'''


SCHEMA = '''# Dataset schema

The default `test` split contains exactly 250 rows. JSONL order matches the frozen canonical cases.

| Field | Meaning | Send to model? |
| --- | --- | --- |
| `id`, `stratum` | Stable source-derived ID and curated stratum | No |
| `user_request` | Exact source request string | Inspection; use frozen `state` for reproduction |
| `state` | Exact frozen state text | Yes |
| `instruction` | Exact choice instruction | Yes |
| `options` | Ordered list of `{id,label,description,kind}` | IDs/descriptions only, preserving order |
| `gold_action_id` | One canonical exact-action ID | No |
| `gold_route_action_ids` | Accepted primary-routing choices (three meta IDs on negatives) | No |
| `gold_tool_names` | Reference function names, empty for negatives | No |
| `expected_route_kind` | `tool_call` or `no_function`; same positive enum as the V1 HF projection | No |
| `full_schemas_json` | JSON string of original complete function schemas | No, not part of published inference payload |
| `original_reference_json` | JSON string of original positive reference or negative source label | No |
| `source_id`, `source_category`, `source_row_number` | Original lineage | No |
| `source_question_file`, `source_answer_file` | Original files; answer may be null | No |
| `source_repository`, `source_revision` | Pinned original source | No |
| `label_source`, `meta_card_version` | Review/label convention and card version | No |

Nested JSON strings preserve schemas and references without forcing inconsistent source schemas into Arrow columns. Tool IDs are case-sensitive. The canonical bytes are `frozen_cases.jsonl`; the Viewer projection does not replace them for exact reproduction. All `frozen_*` files are provenance; their original internal relative filenames are interpreted in the original GitHub tree, not as additional Hub splits.
'''


def usage() -> str:
    return f'''# Loading and reproducing

The public dataset load uses the README YAML whitelist:

```python
from datasets import load_dataset
ds = load_dataset("{REPO_ID}", "default", split="test")
```

For a downloaded package, load only its projected file explicitly:

```python
ds = load_dataset("json", data_files={{"test": "/absolute/path/to/test.jsonl"}}, split="test")
```

Use README's payload snippet. Never pass a whole row, gold IDs, schemas, references, review notes or prior model results to a model. Score the returned ID using `gold_route_action_ids`; on positive cases this is one exact function. `gold_action_id` is the stricter convention requiring `no_tool` on negatives. Neither metric assesses arguments/execution.

## Verify canonical data and package

```sh
shasum -a 256 frozen_cases.jsonl
# Expected: {CASE_SHA}
```

`release_manifest.json` lists every payload file's SHA-256, bytes and source/derivation. It excludes its own recursive hash by design. `run_manifest.json` records original run identities and GitHub runtime-artifact hashes.

## Reconstruct source and inference

Use the GitHub checkout at `{GITHUB_SHA}` for the original data/evaluation snapshot:

```sh
git clone https://github.com/pritishyuvraj/jev-model-performance.git
cd jev-model-performance
git checkout --detach {GITHUB_SHA}
```

Follow the exact source-checkout and data-rebuild commands in [data/bfcl_v4/README.md]({GH_PIN}data/bfcl_v4/README.md). Those commands download pinned BFCL source commits and use the checked-in semantic review. Follow the per-model setup/launch/evaluation commands in [inference/BFCL_V4.md]({GH_PIN}inference/BFCL_V4.md). Environments, requirements, checkpoint revisions and assets are documented in [inference/README.md]({GH_PIN}inference/README.md) and each model directory. The [results report]({HF}blob/main/results_report.md) gives report/chart rebuild commands; [GitHub runtime evidence]({GH_PIN}results/runtime/bfcl_v4/README.md) records the actual H100 run settings.

The new release builder is delivered separately from the historical evaluation snapshot. From a GitHub checkout containing `tools/build_bfcl_v4_hf_release.py`, run:

```sh
python3 tools/build_bfcl_v4_hf_release.py
python3 tools/build_bfcl_v4_hf_release.py --check
```

It writes `.cache/hf-bfcl-v4-release`, verifies rows/logs/card/hashes, and never authenticates or uploads. The builder uses only Python's standard library. An HF clone alone does not contain the source reconstruction or model-serving checkout; no offline HF-clone inference command is claimed.

Download `viewer.html` and open it locally to browse all 250 prompts and seven model logs offline. The PNG/SVG chart payloads are the exact published GitHub chart files; `chart_metrics.json` records their metric definitions and values.
'''


def validate_sources(root: Path) -> tuple[list[dict], dict, list[dict]]:
    raw = (root / 'data/bfcl_v4/cases.jsonl').read_bytes()
    assert digest(raw) == CASE_SHA, 'Canonical data hash changed'
    cases = rows(raw)
    assert len(cases) == len({c['id'] for c in cases}) == 250
    manifest = json.loads((root / 'data/bfcl_v4/manifest.json').read_text())
    assert manifest['source_commit'] == SOURCE_SHA and manifest['cases_sha256'] == CASE_SHA
    ids = {c['id']: c for c in cases}
    for p in MODELS:
        meta = json.loads((root / f'results/bfcl_v4_{p}.meta.json').read_text())
        log = rows((root / f'results/bfcl_v4_{p}.jsonl').read_bytes())
        assert meta['run']['cases_sha256'] == CASE_SHA
        assert len(log) == len({r['case_id'] for r in log}) == 250 and {r['case_id'] for r in log} == set(ids)
        assert meta['run_id'] == digest(json.dumps(meta['run'], sort_keys=True, separators=(',', ':')).encode())
        for row in log:
            c = ids[row['case_id']]
            assert row['run_id'] == meta['run_id'] and row['status'] == 'ok' and row['attempt'] == 1
            assert row.get('http_retries', 0) == 0 and row['gold_action'] == c['gold_next_action_ids'][0]
            probs = row['probabilities']
            assert set(probs) == set(c['jev']['option_ids'])
            assert all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in probs.values())
            assert abs(math.fsum(probs.values()) - 1) < .002
            assert row['predicted_action'] in probs
            assert row['correct'] == (row['predicted_action'] == row['gold_action'])
    with (root / 'results/bfcl_v4_comparison.csv').open(newline='') as f:
        metrics = list(csv.DictReader(f))
    assert [m['model_id'] for m in metrics] == list(MODELS)
    return cases, manifest, metrics


def build_payload(root: Path) -> tuple[dict[str, bytes], dict[str, dict]]:
    cases, manifest, metrics = validate_sources(root)
    payload: dict[str, bytes] = {}
    provenance: dict[str, dict] = {}
    mapping: dict[str, str] = {}
    def copy(source: str, target: str):
        payload[target] = (root / source).read_bytes()
        provenance[target] = {'source_path': source, 'source_sha256': digest(payload[target]), 'transformation': 'byte-identical copy'}
        mapping[source] = target
    for path in sorted((root / 'data/bfcl_v4').iterdir()):
        if path.is_file() and path.name != 'viewer.html':
            copy('data/bfcl_v4/' + path.name, 'frozen_' + path.name)
    copy('data/bfcl_v4/viewer.html', 'viewer.html')
    for p in MODELS:
        for suffix in ['jsonl', 'meta.json', 'summary.json']:
            name = f'bfcl_v4_{p}.{suffix}'
            copy('results/' + name, 'results__' + name)
    copy('results/bfcl_v4_comparison.csv', 'comparison.csv')
    copy('results/bfcl_v4_run_manifest.json', 'run_manifest.json')
    for path in sorted((root / 'charts/bfcl_v4').iterdir()):
        if path.suffix in ('.png', '.svg'):
            copy('charts/bfcl_v4/' + path.name, 'chart__' + path.name)
    copy('charts/bfcl_v4/metrics.json', 'chart_metrics.json')
    copy('charts/bfcl_v4/requirements.resolved.txt', 'chart_requirements.resolved.txt')
    copy('data/bfcl_v4/LICENSE', 'LICENSE')
    copy('LICENSE', 'CODE_LICENSE')
    mapping.update({'data/bfcl_v4/README.md': 'DATASET_README.md', 'results/bfcl_v4.md': 'results_report.md', 'charts/bfcl_v4/README.md': 'CHARTS.md'})
    for source, target in [('results/bfcl_v4.md', 'results_report.md'), ('data/bfcl_v4/README.md', 'DATASET_README.md'), ('charts/bfcl_v4/README.md', 'CHARTS.md')]:
        original = (root / source).read_bytes()
        payload[target] = rewrite_links(original.decode(), source, mapping).encode()
        provenance[target] = {'source_path': source, 'source_sha256': digest(original), 'transformation': 'Markdown relative links resolved to flat HF files or pinned GitHub snapshot'}
    projected = [project(c, manifest) for c in cases]
    payload['test.jsonl'] = ''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n' for r in projected).encode()
    payload['README.md'] = card(root, metrics).encode()
    payload['SCHEMA.md'] = SCHEMA.encode()
    payload['USAGE.md'] = usage().encode()
    report = (root / 'results/bfcl_v4.md').read_text()
    credits = report.split('## Credits and references\n', 1)[1].split('## Rebuild reports', 1)[0]
    pins = ['\n## Exact recorded model pins\n\n| System | Requested model | Declared checkpoint revision |\n| --- | --- | --- |']
    for p in MODELS:
        run = json.loads((root / f'results/bfcl_v4_{p}.meta.json').read_text())['run']
        pins.append(f"| {p} | `{run['requested_model']}` | `{run['declared_model_revision']}` |")
    pins.append(f'\nLaya uses the standalone typed-decisions tokenizer at its declared revision and the matching scored bundle `convaiinnovations/laya@55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851/typed-decisions`. All native implementation/base pins, calibration, precision and serving settings are recorded in [GitHub inference documentation]({GH_PIN}inference/README.md) and [the original run manifest]({HF}blob/main/run_manifest.json).\n')
    payload['CREDITS.md'] = ('# Credits and upstream references\n\n' + rewrite_links(credits, 'results/bfcl_v4.md', mapping) + '\n'.join(pins)).encode()
    payload['NOTICE'] = f'''BFCL V4 Live Jev Capability Routing Pilot

Derived from Berkeley Function Calling Leaderboard data in ShishirPatil/gorilla,
commit {SOURCE_SHA}, under the Apache License, Version 2.0.
Credit: Shishir Patil and the Gorilla/BFCL contributors.
Upstream: https://github.com/ShishirPatil/gorilla

Modifications: curated 250-case capability-routing subset; Jev-style prompts,
neutral meta options, semantic review, flat dataset projection and evaluation
artifacts by Pritish Yuvraj. Original user text, complete schemas and references
remain available. Original adaptation/evaluation/viewer code is MIT licensed.
Model weights and implementations retain their upstream authorship/licenses.
See CREDITS.md for all seven systems and exact checkpoint pins.
'''.encode()
    for name in payload:
        provenance.setdefault(name, {'source_path': None, 'transformation': 'deterministic generation from frozen data, committed results and release builder'})
    return payload, provenance


def check_payload(root: Path, output: Path, expected_payload: dict[str, bytes]) -> dict:
    cases, source_manifest, _ = validate_sources(root)
    packaged = rows((output / 'test.jsonl').read_bytes())
    assert packaged == [project(c, source_manifest) for c in cases]
    assert digest((output / 'frozen_cases.jsonl').read_bytes()) == CASE_SHA
    for name, data in expected_payload.items():
        assert (output / name).read_bytes() == data, f'Release content differs: {name}'
        assert Path(name).name == name, 'All release filenames must be flat'
    release = json.loads((output / 'release_manifest.json').read_text())
    assert set(release['files']) == set(expected_payload)
    assert set(p.name for p in output.iterdir()) == set(expected_payload) | {'release_manifest.json'}
    for name, spec in release['files'].items():
        assert spec['sha256'] == digest((output / name).read_bytes()) and spec['bytes'] == (output / name).stat().st_size
    text = (output / 'README.md').read_text()
    assert 'split: test\n        path: test.jsonl' in text
    header = text.split('---', 2)[1]
    assert header.count('path:') == 1 and 'frozen_' not in header and 'results__' not in header
    viewer = (output / 'viewer.html').read_text()
    embedded_cases = json.loads(re.search(r'<script type="application/json" id="case-data">(.*?)</script>', viewer, re.S).group(1))
    embedded_results = json.loads(re.search(r'<script type="application/json" id="result-data">(.*?)</script>', viewer, re.S).group(1))
    assert [c['id'] for c in embedded_cases] == [c['id'] for c in cases]
    assert len(embedded_results) == 7
    for result in embedded_results:
        assert len(result['rows']) == 250 and {r['case_id'] for r in result['rows']} == {c['id'] for c in cases}
    return {'files': len(expected_payload) + 1, 'projected_rows': 250, 'models': 7, 'canonical_case_sha256': CASE_SHA, 'check': 'passed'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, help='Default: ROOT/.cache/hf-bfcl-v4-release')
    parser.add_argument('--check', action='store_true', help='Check an existing release without writing')
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / '.cache/hf-bfcl-v4-release').resolve()
    payload, provenance = build_payload(root)
    release = {'schema': 'bfcl-v4-hf-flat-release/v1', 'repo_id': REPO_ID,
        'canonical_case_sha256': CASE_SHA, 'bfcl_source_revision': SOURCE_SHA,
        'github_evaluation_snapshot': GITHUB_SHA, 'test_rows': 250, 'models': list(MODELS),
        'builder': {'repository_path': 'tools/build_bfcl_v4_hf_release.py',
                    'sha256': digest(Path(__file__).read_bytes()), 'stdlib_only': True},
        'selection_seed': 'bfcl-v4-live-routing-250-20260929',
        'meta_card_version': 'bfcl-v4-neutral-meta-cards/v1',
        'language_tags': ['en', 'zh', 'vi', 'pl'],
        'split_whitelist': {'default': {'test': 'test.jsonl'}},
        'runtime_evidence': GH_PIN + 'results/runtime/bfcl_v4/README.md',
        'manifest_self_hash': 'Excluded to avoid a recursive checksum; every other payload file is hashed.',
        'files': {name: {'sha256': digest(payload[name]), 'bytes': len(payload[name]), **provenance[name]} for name in sorted(payload)}}
    if not args.check:
        output.mkdir(parents=True, exist_ok=True)
        extras = {p.name for p in output.iterdir()} - set(payload) - {'release_manifest.json'}
        if extras:
            raise ValueError(f'Output has unrelated files; use a clean release directory: {sorted(extras)}')
        for name, data in payload.items():
            (output / name).write_bytes(data)
        (output / 'release_manifest.json').write_bytes(json_bytes(release))
    else:
        assert (output / 'release_manifest.json').read_bytes() == json_bytes(release), 'Release manifest differs from deterministic rebuild'
    print(json.dumps({'output': str(output), **check_payload(root, output, payload)}, indent=2))


if __name__ == '__main__':
    main()
