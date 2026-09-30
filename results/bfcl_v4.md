# BFCL V4 Live Jev routing pilot: seven model runs

All seven systems completed the same **250 frozen V4 Live cases** on `vp-dgx-59` (`dgxh100-059`, NVIDIA H100 80GB, driver 570.195.03), with **zero request errors**. One model used each of GPUs 0–6; GPU 7 was left free. Requests were sequential within each model, while models ran on separate GPUs. Pinned checkpoints, native runner settings, and option serialization match those used for V1.

[Inspect every model selection in the offline viewer](../data/bfcl_v4/viewer.html) · [Frozen data and review protocol](../data/bfcl_v4/README.md) · [CSV comparison](bfcl_v4_comparison.csv) · [Charts](../charts/bfcl_v4/README.md) · [Exact rerun commands](../inference/BFCL_V4.md)

**Exact right tool** is the exact function ID on the 200 tool-required cases. **Routing accuracy** covers all 250 cases and accepts any of `no_tool`, `clarify`, or `cannot_answer` on the 50 no-tool cases. Function arguments, execution, final responses, and task completion are not scored.

| Model | Approx. parameters | Exact right tool (200) | Routing accuracy (250) | Mean latency | Median | P95 | Mean correct-route probability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Laya typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions) | ~421M | **186/200 (93.0%)** | 224/250 (89.6%) | 21.5 ms | 17.1 ms | 30.6 ms | 61.1% |
| [Kev-0.8B](https://huggingface.co/jaredpalmer/kev-0.8b) | ~0.8B | **180/200 (90.0%)** | 230/250 (92.0%) | 58.0 ms | 57.3 ms | 61.6 ms | 59.2% |
| [Bespoke Nimble 9B](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B) | ~9B | **200/200 (100.0%)** | 249/250 (99.6%) | 57.8 ms | 47.6 ms | 67.6 ms | 98.2% |
| [SemIf / frozen Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) | ~4B | **196/200 (98.0%)** | 244/250 (97.6%) | 57.3 ms | 50.3 ms | 61.3 ms | 91.9% |
| [Rizzo Flow 4B Q8_0](https://huggingface.co/rizzoaiacademy/rizzo-flow) | ~4B | **195/200 (97.5%)** | 241/250 (96.4%) | 41.8 ms | 40.4 ms | 52.5 ms | 92.6% |
| [Von 1.3, chains off](https://huggingface.co/wfzyx/von) | ~395M | **53/200 (26.5%)** | 103/250 (41.2%) | 13.0 ms | 12.9 ms | 13.8 ms | 38.8% |
| [NanoJev unified-games-v1](https://huggingface.co/C-Tianyu/NanoJev) | ~0.6B | **7/200 (3.5%)** | 56/250 (22.4%) | 28.8 ms | 25.9 ms | 34.7 ms | 30.3% |

## Breakdown and exact meta action

| Model | Multiple tools (150) | One relevant tool (50) | One irrelevant tool (50) | Exact action (250) | Errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Laya typed-decisions | 137 | 49 | 38 | 192/250 (76.8%) | 0 |
| Kev-0.8B | 137 | 43 | 50 | 199/250 (79.6%) | 0 |
| Bespoke Nimble 9B | 150 | 50 | 49 | 222/250 (88.8%) | 0 |
| SemIf / frozen Qwen3.5-4B | 147 | 49 | 48 | 229/250 (91.6%) | 0 |
| Rizzo Flow 4B Q8_0 | 145 | 50 | 46 | 232/250 (92.8%) | 0 |
| Von 1.3, chains off | 39 | 14 | 50 | 56/250 (22.4%) | 0 |
| NanoJev unified-games-v1 | 2 | 5 | 49 | 35/250 (14.0%) | 0 |

The exact-action column requires canonical `no_tool` on negatives. BFCL irrelevance does not establish whether responding, clarifying, or saying the capability is unavailable is the best disposition. Treat this as a label convention; the routing column is the primary router score.

Von selected no function on all 50 negatives, but selected the correct tool on only 53/200 positives. On positive cases its saved choices include 117 `cannot_answer`, 28 `clarify`, and one `no_tool`; this is frequent rejection of offered capabilities, with no request errors or truncation. The independent NanoJev check found its input/option mapping unchanged from V1 and correctly reflected in saved responses. Its 7/200 positive score is retained. These observations do not establish why either checkpoint performs poorly on these prompts.

## Timing and probability interpretation

- Latency uses saved `wall_latency_ms` over all 250 scored responses, without removing outliers. Warmup is not uniform: Nimble/SemIf resumed their scored two-case smoke runs in new processes; Rizzo/NanoJev resumed scored smoke requests on warm servers; Laya/Kev/Von ran separate smoke requests before their scored 250. Any cold overhead in the saved rows remains included. Actual commands are retained in runtime evidence.
- HTTP timings include client/server handling; direct scorers include their native prompt/scoring work. Runtimes, precision, prompts, and model sizes differ. Concurrent activity on the node can also affect timing. These are observed H100 response times, not a controlled throughput comparison or laptop measurements.
- P95 uses linear interpolation at `0.95 × (n − 1)` in sorted times.
- Mean correct-route probability averages the gold function probability on positives and summed probability of the three meta actions on negatives, across 250 cases. It is conditional on the offered options and is not calibrated confidence. Raw logits from Nimble/SemIf are retained in their logs, but are not directly comparable between models.
- Parameter counts are rounded published backbone sizes; adapters and decision heads may add parameters.

## Logs, native preflight, and lineage

All seven metadata files cite case SHA-256 `2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8`, BFCL source `f7cf7359b7ac615a0b294831c5ba2bc95ee4a000`, the same selection-review digest, and meta-card version `bfcl-v4-neutral-meta-cards/v1`. Gold labels and original source records stayed outside model requests. All 250 native inputs passed each model-specific preflight without truncation.

| Model | Decisions | Summary | Metadata |
| --- | --- | --- | --- |
| Laya typed-decisions | [JSONL](bfcl_v4_laya.jsonl) | [JSON](bfcl_v4_laya.summary.json) | [JSON](bfcl_v4_laya.meta.json) |
| Kev-0.8B | [JSONL](bfcl_v4_kev.jsonl) | [JSON](bfcl_v4_kev.summary.json) | [JSON](bfcl_v4_kev.meta.json) |
| Bespoke Nimble 9B | [JSONL](bfcl_v4_nimble.jsonl) | [JSON](bfcl_v4_nimble.summary.json) | [JSON](bfcl_v4_nimble.meta.json) |
| SemIf / frozen Qwen3.5-4B | [JSONL](bfcl_v4_semif.jsonl) | [JSON](bfcl_v4_semif.summary.json) | [JSON](bfcl_v4_semif.meta.json) |
| Rizzo Flow 4B Q8_0 | [JSONL](bfcl_v4_rizzo.jsonl) | [JSON](bfcl_v4_rizzo.summary.json) | [JSON](bfcl_v4_rizzo.meta.json) |
| Von 1.3, chains off | [JSONL](bfcl_v4_von.jsonl) | [JSON](bfcl_v4_von.summary.json) | [JSON](bfcl_v4_von.meta.json) |
| NanoJev unified-games-v1 | [JSONL](bfcl_v4_nanojev.jsonl) | [JSON](bfcl_v4_nanojev.summary.json) | [JSON](bfcl_v4_nanojev.meta.json) |

[Run manifest](bfcl_v4_run_manifest.json) records hardware, code and data hashes, settings, and result checksums. [Runtime evidence](runtime/bfcl_v4/README.md) includes native-input reports, asset hashes, package checks, and saved setup/server/evaluation console output.

## V1 and V4 interpretation

The V4 set has no exact or normalized request overlap with all 2,000 V1 source rows or the frozen V1 250. These are two different curated pilots. V4 uses complete source descriptions and revised neutral meta cards; V1 used compact cards. Differences in scores therefore do not isolate a benchmark-version effect. The Live categories also predate V4 and were carried into its corpus.

This is an independent, short-context, single-step capability-routing adaptation, **not an official BFCL V4 function-calling/agentic score**. Public prompts may have been seen in training. Models were not tuned on this set. NanoJev uses its published game-trained checkpoint out of domain; SemIf is a scoring method over frozen Qwen weights; Rizzo uses its fine-tuned Q8_0 GGUF; Von chains are disabled.

## Credits and references

Dataset credit: [Berkeley Function Calling Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html), Shishir Patil and the Gorilla/BFCL contributors. Adapted source data retain the [Apache 2.0 license](../data/bfcl_v4/LICENSE).

| System | Authors / maintainers | Model | Native implementation |
| --- | --- | --- | --- |
| Laya typed-decisions | Convai Innovations; NandhaKishorM (serving code) | [Model card](https://huggingface.co/convaiinnovations/laya-typed-decisions) | [Source](https://github.com/NandhaKishorM/laya) |
| Kev-0.8B | Jared Palmer | [Model card](https://huggingface.co/jaredpalmer/kev-0.8b) | [Source](https://github.com/jaredpalmer/kev) |
| Bespoke Nimble 9B | Bespoke Labs | [Model card](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B) | [Source](https://github.com/bespokelabsai/nimble) |
| SemIf / frozen Qwen3.5-4B | TheoLeeCJ (SemIf method); Qwen team (base model) | [Model card](https://huggingface.co/Qwen/Qwen3.5-4B) | [Source](https://github.com/TheoLeeCJ/SemIf-OpenJev) |
| Rizzo Flow 4B Q8_0 | Rizzo AI Academy | [Model card](https://huggingface.co/rizzoaiacademy/rizzo-flow) | [Source](https://github.com/Rizzo-AI-Academy/rizzo-flow) |
| Von 1.3, chains off | wfzyx | [Model card](https://huggingface.co/wfzyx/von) | [Source](https://github.com/wfzyx/von) |
| NanoJev unified-games-v1 | TianyuCodings / C-Tianyu | [Model card](https://huggingface.co/C-Tianyu/NanoJev) | [Source](https://github.com/TianyuCodings/NanoJev) |

Pinned revisions and package snapshots are retained in the [inference documentation](../inference/README.md) and each model directory. Our original adaptation, evaluation support, and viewer code use the repository MIT license.

## Rebuild reports

```sh
python3 tools/summarize_runs.py --bfcl-version v4
python3 tools/build_prompt_viewer.py --bfcl-version v4 --dataset-name "BFCL V4 Live routing"
python3 tools/build_bfcl_v4_run_manifest.py
python3 tools/build_bfcl_v4_report.py
.cache/charts-venv/bin/python charts/build_charts.py --bfcl-version v4
```
