# Jev model performance

This repository holds a **250-case BFCL-conditioned Jev routing pilot** adapted from Berkeley Function Calling Leaderboard (BFCL) V1. BFCL V1 has 2,000 source examples; the review set uses a selected subset. Seven model runs are complete: Laya, Kev-0.8B, Nimble-9B, SemIf on frozen Qwen3.5-4B, Rizzo Flow 4B, Von, and NanoJev.

## Results and reruns

- [Evaluation results](results/README.md): all seven scores, per-stratum breakdowns, run identity, and links to every per-case selection log.
- [Comparison charts](charts/README.md): model size, observed latency, and gold-function probability against exact right-tool accuracy, with reproducible PNG and SVG figures.
- [Inference setup](inference/README.md): pinned environments and rerun instructions for each model.
- [Prompt and results viewer](data/bfcl_v1/viewer.html): compare every saved model selection alongside the user request and offered tools.

## View the prompts

- [Open the prompt viewer](data/bfcl_v1/viewer.html): offline, chat-style browsing of all 250 requests, offered functions, the expected routing choice, and each model's saved choice. Filter by model and correct/wrong tool selection, inspect option probabilities in a case's saved log, or import another result JSONL. Use the arrow buttons, hide or reveal the expected choice, and expand the original BFCL reference or raw Laya/MacJev payload. Each case has a stable `#case=<id>` link. The viewer is read only and does not run a model.
- [Review examples](data/bfcl_v1/review.md): rendered Laya choice prompts with the expected next action and original BFCL answer.
- [250 selected cases](data/bfcl_v1/cases.jsonl): one self-contained JSON object per selected source row, including Laya and MacJev inputs, offered tools, source documentation, and gold labels.
- [Case index](data/bfcl_v1/index.csv): a compact list to filter by category, routing stratum, and gold action.
- [Manifest](data/bfcl_v1/manifest.json): source commit, selection rules, file hashes, and category counts.
- [Tokenizer fit report](data/bfcl_v1/fit_report.json): checks every generated prompt against the locally pinned Laya and MacJev input budgets without running either model.

The converter uses BFCL V1 from the official [Gorilla v1.0 release](https://github.com/ShishirPatil/gorilla/releases/tag/v1.0), pinned to commit `9df5c346ee0556c8a7cb09fd7206a39aadd904c2`. The upstream [data card](https://github.com/ShishirPatil/gorilla/blob/v1.0/berkeley-function-call-leaderboard/data/README.md) identifies the data as Apache 2.0; its [license](data/bfcl_v1/UPSTREAM_LICENSE.txt) is included with the converted rows. This repository's MIT license covers our converter and other original code.

## What the conversion measures

For each BFCL question, the Jev prompt asks: **“Which capability should the assistant use for its next step?”** Its options are `no_tool`, `clarify`, `cannot_answer`, and the functions that BFCL offered for that question. **Jev chooses the function; the chat model reads its schema, supplies arguments, and can ask for missing values before execution.** A missing date or other argument is not grounds to reject a tool-selection label. The Laya input has the harness's first-step text state and choice question. The MacJev input has the equivalent JSON state and choice question. Both use concise function descriptions as router cards; the full BFCL function schemas remain in each case's `source` field.

| Selected stratum | Cases | What it checks |
| --- | ---: | --- |
| Multiple offered tools, one correct call | 150 | Choose the right function among 2–4 options |
| One offered tool, correct call | 50 | Choose the tool rather than `no_tool` |
| One irrelevant offered tool, no call | 50 | Choose `no_tool` rather than the irrelevant function |

The subset is selected reproducibly from source-grounded, single-call cases. It excludes parallel calls, REST cases without explicit call answers, rows with source-answer warnings, and one manually identified wrong-capability label. It also removes repeated normalized user questions. The one-tool cases are balanced between call and no-call labels; report performance separately for multiple-tool selection and one-tool call detection.

This is a **derived routing set**, not a BFCL leaderboard score or a universal judgment of the best autonomous action. Some BFCL positive questions could reasonably be answered without a tool; BFCL's no-call label does not distinguish Jev's `no_tool`, `clarify`, and `cannot_answer`. Review those judgments before using the set to score models. It does not test argument generation, execution, final answers, or multi-step completion. All selected prompts fit the currently pinned local Laya and MacJev tokenizers and 4,096/1,024-token budgets; the report records the model revisions and case hash. Recheck fit if the prompt format, model, or budget changes. BFCL questions, descriptions, and repository text are treated as source data, not instructions to the converter. Freeze this selection before comparing models; use separate development cases for prompt tuning.

BFCL V1 is public, so a model may already have encountered these questions during training. Treat results as a focused comparison on this set, not evidence of performance on unseen requests.

For an evaluation, send only a case's `jev.laya` or `jev.macjev` fields to the model. Keep `gold_next_action_ids` and `source` outside the model input; they are included for review and scoring. The seven saved runs used the same Jev choice state and offered actions. Model-specific adapters translated that input into each native decision interface; their details are in [inference](inference/README.md).

## Rebuild

The converter uses Python's standard library. Run these commands from this repository's root:

```sh
git clone --depth 1 --filter=blob:none --sparse --branch v1.0 https://github.com/ShishirPatil/gorilla.git .cache/bfcl-v1
git -C .cache/bfcl-v1 sparse-checkout set berkeley-function-call-leaderboard/data
python3 tools/convert_bfcl_v1.py --source-dir .cache/bfcl-v1/berkeley-function-call-leaderboard/data
python3 tools/select_eval_subset.py
python3 tools/build_prompt_viewer.py
python3 -m unittest discover -s tests
```

The full conversion goes to ignored `.cache/bfcl-v1-converted`. The selection command writes the 250 review cases in `data/bfcl_v1`. The viewer builder embeds those selected cases and available `results/bfcl_v1_*.jsonl` selection logs in a standalone HTML file, so you can open it without a server or network connection. Its metadata records the SHA-256 of `cases.jsonl`; rebuild it if the selected cases or saved results change. Both conversion and selection record hashes and rules so the selection can be reproduced. The upstream source and full conversion stay out of the review set.

To repeat the tokenizer check, run `tools/check_prompt_fit.py` with the Jev harness virtual environment and pass its root using `--harness-root`. The script loads tokenizers only, not model weights.
