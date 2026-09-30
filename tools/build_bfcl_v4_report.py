#!/usr/bin/env python3
"""Write the V4 results report from validated, frozen per-case logs; no inference."""
from __future__ import annotations
import json
from pathlib import Path
from summarize_runs import ROOT, MODELS, build_rows

MODEL_LINKS = {
    'laya': ('https://huggingface.co/convaiinnovations/laya-typed-decisions', 'Convai Innovations; NandhaKishorM (serving code)', 'https://github.com/NandhaKishorM/laya'),
    'kev': ('https://huggingface.co/jaredpalmer/kev-0.8b', 'Jared Palmer', 'https://github.com/jaredpalmer/kev'),
    'nimble': ('https://huggingface.co/bespokelabs/Bespoke-Nimble-9B', 'Bespoke Labs', 'https://github.com/bespokelabsai/nimble'),
    'semif': ('https://huggingface.co/Qwen/Qwen3.5-4B', 'TheoLeeCJ (SemIf method); Qwen team (base model)', 'https://github.com/TheoLeeCJ/SemIf-OpenJev'),
    'rizzo': ('https://huggingface.co/rizzoaiacademy/rizzo-flow', 'Rizzo AI Academy', 'https://github.com/Rizzo-AI-Academy/rizzo-flow'),
    'von': ('https://huggingface.co/wfzyx/von', 'wfzyx', 'https://github.com/wfzyx/von'),
    'nanojev': ('https://huggingface.co/C-Tianyu/NanoJev', 'TianyuCodings / C-Tianyu', 'https://github.com/TianyuCodings/NanoJev'),
}


def main():
    rows = build_rows(ROOT, 'v4')
    manifest = json.loads((ROOT/'data/bfcl_v4/manifest.json').read_text())
    lines = ['# BFCL V4 Live Jev routing pilot: seven model runs', '',
        'All seven systems completed the same **250 frozen V4 Live cases** on `vp-dgx-59` (`dgxh100-059`, NVIDIA H100 80GB, driver 570.195.03), with **zero request errors**. One model used each of GPUs 0–6; GPU 7 was left free. Requests were sequential within each model, while models ran on separate GPUs. Pinned checkpoints, native runner settings, and option serialization match those used for V1.', '',
        '[Inspect every model selection in the offline viewer](../data/bfcl_v4/viewer.html) · [Frozen data and review protocol](../data/bfcl_v4/README.md) · [CSV comparison](bfcl_v4_comparison.csv) · [Charts](../charts/bfcl_v4/README.md) · [Exact rerun commands](../inference/BFCL_V4.md)', '',
        '**Exact right tool** is the exact function ID on the 200 tool-required cases. **Routing accuracy** covers all 250 cases and accepts any of `no_tool`, `clarify`, or `cannot_answer` on the 50 no-tool cases. Function arguments, execution, final responses, and task completion are not scored.', '',
        '| Model | Approx. parameters | Exact right tool (200) | Routing accuracy (250) | Mean latency | Median | P95 | Mean correct-route probability |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:
        key=row['model_id'];url=MODEL_LINKS[key][0]
        lines.append(f"| [{row['model']}]({url}) | {row['parameter_label']} | **{row['exact_right_tool_correct']}/200 ({row['exact_right_tool_accuracy_pct']:.1f}%)** | {row['tool_selection_correct']}/250 ({row['tool_selection_accuracy_pct']:.1f}%) | {row['mean_wall_latency_ms']:.1f} ms | {row['median_wall_latency_ms']:.1f} ms | {row['p95_wall_latency_ms']:.1f} ms | {row['mean_correct_route_probability_pct']:.1f}% |")
    lines += ['', '## Breakdown and exact meta action', '',
        '| Model | Multiple tools (150) | One relevant tool (50) | One irrelevant tool (50) | Exact action (250) | Errors |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:
        s=json.loads((ROOT/f"results/bfcl_v4_{row['model_id']}.summary.json").read_text())
        assert s['is_complete'] and s['completed_count']==250 and s['overall']['errors']==0
        assert s['overall']['tool_selection_correct']==row['tool_selection_correct']
        b=s['by_stratum'];o=s['overall']
        lines.append(f"| {row['model']} | {b['multi_tool_call']['tool_selection_correct']} | {b['one_tool_call']['tool_selection_correct']} | {b['one_tool_no_call']['tool_selection_correct']} | {o['correct']}/250 ({100*o['accuracy_all_cases']:.1f}%) | {o['errors']} |")
    lines += ['', 'The exact-action column requires canonical `no_tool` on negatives. BFCL irrelevance does not establish whether responding, clarifying, or saying the capability is unavailable is the best disposition. Treat this as a label convention; the routing column is the primary router score.', '',
        'Von selected no function on all 50 negatives, but selected the correct tool on only 53/200 positives. On positive cases its saved choices include 117 `cannot_answer`, 28 `clarify`, and one `no_tool`; this is frequent rejection of offered capabilities, with no request errors or truncation. The independent NanoJev check found its input/option mapping unchanged from V1 and correctly reflected in saved responses. Its 7/200 positive score is retained. These observations do not establish why either checkpoint performs poorly on these prompts.', '',
        '## Timing and probability interpretation', '',
        '- Latency uses saved `wall_latency_ms` over all 250 scored responses, without removing outliers. Warmup is not uniform: Nimble/SemIf resumed their scored two-case smoke runs in new processes; Rizzo/NanoJev resumed scored smoke requests on warm servers; Laya/Kev/Von ran separate smoke requests before their scored 250. Any cold overhead in the saved rows remains included. Actual commands are retained in runtime evidence.',
        '- HTTP timings include client/server handling; direct scorers include their native prompt/scoring work. Runtimes, precision, prompts, and model sizes differ. Concurrent activity on the node can also affect timing. These are observed H100 response times, not a controlled throughput comparison or laptop measurements.',
        '- P95 uses linear interpolation at `0.95 × (n − 1)` in sorted times.',
        '- Mean correct-route probability averages the gold function probability on positives and summed probability of the three meta actions on negatives, across 250 cases. It is conditional on the offered options and is not calibrated confidence. Raw logits from Nimble/SemIf are retained in their logs, but are not directly comparable between models.',
        '- Parameter counts are rounded published backbone sizes; adapters and decision heads may add parameters.', '',
        '## Logs, native preflight, and lineage', '',
        f"All seven metadata files cite case SHA-256 `{manifest['cases_sha256']}`, BFCL source `{manifest['source_commit']}`, the same selection-review digest, and meta-card version `{manifest['meta_card_version']}`. Gold labels and original source records stayed outside model requests. All 250 native inputs passed each model-specific preflight without truncation.", '',
        '| Model | Decisions | Summary | Metadata |', '| --- | --- | --- | --- |']
    for row in rows:
        key=row['model_id'];lines.append(f"| {row['model']} | [JSONL](bfcl_v4_{key}.jsonl) | [JSON](bfcl_v4_{key}.summary.json) | [JSON](bfcl_v4_{key}.meta.json) |")
    lines += ['', '[Run manifest](bfcl_v4_run_manifest.json) records hardware, code and data hashes, settings, and result checksums. [Runtime evidence](runtime/bfcl_v4/README.md) includes native-input reports, asset hashes, package checks, and saved setup/server/evaluation console output.', '',
        '## V1 and V4 interpretation', '',
        'The V4 set has no exact or normalized request overlap with all 2,000 V1 source rows or the frozen V1 250. These are two different curated pilots. V4 uses complete source descriptions and revised neutral meta cards; V1 used compact cards. Differences in scores therefore do not isolate a benchmark-version effect. The Live categories also predate V4 and were carried into its corpus.', '',
        'This is an independent, short-context, single-step capability-routing adaptation, **not an official BFCL V4 function-calling/agentic score**. Public prompts may have been seen in training. Models were not tuned on this set. NanoJev uses its published game-trained checkpoint out of domain; SemIf is a scoring method over frozen Qwen weights; Rizzo uses its fine-tuned Q8_0 GGUF; Von chains are disabled.', '',
        '## Credits and references', '',
        'Dataset credit: [Berkeley Function Calling Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html), Shishir Patil and the Gorilla/BFCL contributors. Adapted source data retain the [Apache 2.0 license](../data/bfcl_v4/LICENSE).', '',
        '| System | Authors / maintainers | Model | Native implementation |', '| --- | --- | --- | --- |']
    for key,name,_,_ in MODELS:
        url,credit,source=MODEL_LINKS[key];lines.append(f'| {name} | {credit} | [Model card]({url}) | [Source]({source}) |')
    lines += ['', 'Pinned revisions and package snapshots are retained in the [inference documentation](../inference/README.md) and each model directory. Our original adaptation, evaluation support, and viewer code use the repository MIT license.', '',
        '## Rebuild reports', '', '```sh', 'python3 tools/summarize_runs.py --bfcl-version v4', 'python3 tools/build_prompt_viewer.py --bfcl-version v4 --dataset-name "BFCL V4 Live routing"', 'python3 tools/build_bfcl_v4_run_manifest.py', 'python3 tools/build_bfcl_v4_report.py', '.cache/charts-venv/bin/python charts/build_charts.py --bfcl-version v4', '```', '']
    path=ROOT/'results/bfcl_v4.md';path.write_text('\n'.join(lines));print(path)


if __name__=='__main__':main()
