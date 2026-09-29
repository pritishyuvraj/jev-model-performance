# BFCL V1 Jev routing pilot: seven model runs

All seven models completed the same [250 selected BFCL V1 cases](../data/bfcl_v1/cases.jsonl) on `vp-dgx-65` (`dgxh100-065`, NVIDIA H100). Each case asked a model to select the assistant's next capability from the offered actions. The saved rows record the selected action and option probabilities; the BFCL answer and gold label stayed outside model requests. No model generated function arguments or executed a tool.

**Tool selection** is the primary score for Jev's router role. On 200 positive BFCL cases, the model must choose the exact function ID. On 50 BFCL no-call cases, `no_tool`, `clarify`, and `cannot_answer` all count as selecting no function. **Exact action** is stricter: it requires the BFCL-derived action ID, including `no_tool` rather than another no-function action. Failed requests count as wrong in both scores.

| Model and checkpoint | Multiple tools (150) | One tool, call (50) | One tool, no call (50) | Tool selection (250) | Exact action (250) | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Laya typed-decisions | 147 | 50 | 43 | **240 (96.0%)** | 228 (91.2%) | 0 |
| Kev-0.8B | 142 | 50 | 49 | **241 (96.4%)** | 224 (89.6%) | 0 |
| Bespoke Nimble 9B | 150 | 50 | 48 | **248 (99.2%)** | 245 (98.0%) | 0 |
| SemIf / frozen Qwen3.5-4B | 149 | 49 | 50 | **248 (99.2%)** | 245 (98.0%) | 0 |
| Rizzo Flow 4B Q8_0 | 143 | 46 | 50 | **239 (95.6%)** | 239 (95.6%) | 0 |
| Von 1.3, chains off | 133 | 46 | 49 | **228 (91.2%)** | 179 (71.6%) | 0 |
| NanoJev `unified-games-v1` | 25 | 13 | 50 | **88 (35.2%)** | 66 (26.4%) | 0 |

The three middle columns use the primary tool-selection rule and show correct selections out of that column's case count. Nimble and SemIf tied at 248/250 on this set. Their predictions and native prompt encodings differ, so the equal totals are not interchangeable behavior. The 50 one-tool-call cases are easy for several models; inspect the multiple-tool and no-call columns before comparing overall totals.

## Function choice, response time, and probability

The table below is generated from the seven saved per-case JSONL logs by [`tools/summarize_runs.py`](../tools/summarize_runs.py); its machine-readable source is [`bfcl_v1_comparison.csv`](bfcl_v1_comparison.csv). **Exact right tool** checks the precise function ID on the 200 cases that require a call. It excludes the 50 no-call cases and does not check function arguments. **Tool selection** uses all 250 cases and credits any no-function choice on a no-call case. These are different denominators from the **exact action** column above.

| Model | Approx. parameters | Exact right tool (200 calls) | Tool selection (250 cases) | Mean latency | Median latency | P95 latency | Mean correct-route probability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Laya typed-decisions | ~421M | 197/200 (98.5%) | 240/250 (96.0%) | 23.4 ms | 17.0 ms | 32.8 ms | 72.7% |
| Kev-0.8B | ~0.8B | 192/200 (96.0%) | 241/250 (96.4%) | 75.3 ms | 73.8 ms | 79.9 ms | 71.0% |
| Bespoke Nimble 9B | ~9B | 200/200 (100.0%) | 248/250 (99.2%) | 69.2 ms | 60.3 ms | 69.4 ms | 98.6% |
| SemIf / frozen Qwen3.5-4B | ~4B | 198/200 (99.0%) | 248/250 (99.2%) | 61.6 ms | 56.0 ms | 74.6 ms | 96.2% |
| Rizzo Flow 4B Q8_0 | ~4B | 189/200 (94.5%) | 239/250 (95.6%) | 39.2 ms | 38.3 ms | 45.9 ms | 87.1% |
| Von 1.3, chains off | ~395M | 179/200 (89.5%) | 228/250 (91.2%) | 31.2 ms | 13.0 ms | 14.4 ms | 64.6% |
| NanoJev `unified-games-v1` | ~0.6B | 38/200 (19.0%) | 88/250 (35.2%) | 27.0 ms | 27.4 ms | 36.0 ms | 33.0% |

The parameter labels are rounded sizes of the tested backbones; adapters and decision heads can add parameters. Latency is the saved `wall_latency_ms` over all 250 sequential responses, including first-request warmup. P95 uses linear interpolation on sorted times at `0.95 × (n − 1)`. These runs used different inference paths and precision, so the timings are observed response times rather than a controlled throughput comparison. Von's 4.49-second first response raises its mean well above its median.

Mean correct-route probability is the mean probability assigned to the exact gold function on call cases. On no-call cases it sums the probabilities of `no_tool`, `clarify`, and `cannot_answer`. It is neither calibrated confidence nor the probability that the assistant completes the task. Saved raw logits exist for Nimble and SemIf, but their scales differ; the table uses probabilities for all seven. Regenerate or verify the CSV with `python3 tools/summarize_runs.py` or `python3 tools/summarize_runs.py --check`.

Von illustrates the difference between the two scores: it selected no function on 49/50 no-call rows, but its chosen no-function action was `clarify` or `cannot_answer` rather than the BFCL-derived `no_tool` on every one of those rows. BFCL does not label those subtypes. NanoJev's published checkpoint was trained on games, so this BFCL run is an out-of-domain probe, not a test of its game performance. SemIf is direct-logit scoring over a frozen Qwen checkpoint rather than a separately trained SemIf model. Rizzo used its fine-tuned Q8_0 GGUF; other run-specific precision and revisions are recorded below.

## Inspect every selection

[Open the offline prompt and results viewer](../data/bfcl_v1/viewer.html). It embeds all seven saved logs and shows, for each case, the user request, offered functions, expected route, and each model's selected action. Filter by model and wrong/correct tool selection, inspect a model's full saved row and probabilities, or import another result JSONL. Rebuild it with `python3 tools/build_prompt_viewer.py` after changing logs.

| Model | Per-case selection log | Summary | Run metadata | Rerun instructions |
| --- | --- | --- | --- | --- |
| Laya | [JSONL](bfcl_v1_laya.jsonl) | [JSON](bfcl_v1_laya.summary.json) | [JSON](bfcl_v1_laya.meta.json) | [Shared setup](../inference/README.md) |
| Kev-0.8B | [JSONL](bfcl_v1_kev.jsonl) | [JSON](bfcl_v1_kev.summary.json) | [JSON](bfcl_v1_kev.meta.json) | [Shared setup](../inference/README.md) |
| Nimble 9B | [JSONL](bfcl_v1_nimble.jsonl) | [JSON](bfcl_v1_nimble.summary.json) | [JSON](bfcl_v1_nimble.meta.json) | [Nimble](../inference/nimble/README.md) |
| SemIf | [JSONL](bfcl_v1_semif.jsonl) | [JSON](bfcl_v1_semif.summary.json) | [JSON](bfcl_v1_semif.meta.json) | [SemIf](../inference/semif/README.md) |
| Rizzo Flow | [JSONL](bfcl_v1_rizzo.jsonl) | [JSON](bfcl_v1_rizzo.summary.json) | [JSON](bfcl_v1_rizzo.meta.json) | [Rizzo](../inference/rizzo/README.md) |
| Von | [JSONL](bfcl_v1_von.jsonl) | [JSON](bfcl_v1_von.summary.json) | [JSON](bfcl_v1_von.meta.json) | [Von](../inference/von/README.md) |
| NanoJev | [JSONL](bfcl_v1_nanojev.jsonl) | [JSON](bfcl_v1_nanojev.summary.json) | [JSON](bfcl_v1_nanojev.meta.json) | [NanoJev](../inference/nanojev/README.md) |

Each JSONL row includes a case ID, selected action, status, complete option probability distribution, and timing or error data. The `.meta.json` file identifies the checkpoint and runtime; the `.summary.json` file reports scores overall and by stratum/category. Some adapters also retain raw logits or a prompt hash. Use the log for case-level review and the metadata to reproduce its model and environment.

## Shared source and interpretation

Every run's metadata records the same selected-case SHA-256, `68868277c9f10c56706a5d8a1a79a78720582dd731fef414a4b7c4ae366cc602`, from Gorilla/BFCL V1 tag `v1.0`, commit `9df5c346ee0556c8a7cb09fd7206a39aadd904c2`. The selected set contains 150 multiple-tool call cases, 50 one-tool call cases, and 50 one-tool no-call cases. Native adapters preserve that state and the offered action meanings, but their prompt serialization, precision, scoring heads, and model training differ. The linked run metadata and [inference instructions](../inference/README.md) identify representative checkpoints used here rather than every available variant of each model family.

This is a derived, selected routing set, **not an official BFCL leaderboard result**. It does not score argument correctness, execution, final answers, or multi-step task completion. Some positive BFCL questions could be answered without a tool, and public BFCL material may have appeared in model training. The [Kev-0.8B model card](https://huggingface.co/jaredpalmer/kev-0.8b) cautions against relying on that checkpoint for tool-call routing based on a separate evaluation. These scores support inspection of this frozen set; evaluate untouched assistant requests and complete-task outcomes before choosing a deployment model.
