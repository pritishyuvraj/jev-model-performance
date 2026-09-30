# BFCL V4 corpus — Live routing pilot

**250 new Jev capability-selection prompts**, with **zero normalized request matches** against all 2,000 original BFCL V1 rows and our frozen 250-case V1 subset. Open [the chat-style viewer](viewer.html) to inspect the user request, expected assistant choice, offered capabilities, and original schemas.

| Category | Cases | Decision |
| --- | ---: | --- |
| `live_multiple` | 150 | Select one relevant tool among 2–4 offered tools |
| `live_simple` | 50 | Select the one relevant offered tool |
| `live_irrelevance` | 50 | Select no offered tool |

The canonical evaluation input is [cases.jsonl](cases.jsonl). Send only `jev.laya` or `jev.macjev` to a model. Gold labels, review notes, and `source` are for scoring and inspection and must stay outside the model input. **Jev selects the capability; the chat model supplies arguments and asks for missing values before execution.** Missing dates, addresses, or other argument values alone do not invalidate a positive tool label.

All seven models have completed this set with zero request errors. The viewer embeds their V4 per-case selections, probabilities, and saved logs. See the [results report](../../results/bfcl_v4.md), [charts](../../charts/bfcl_v4/README.md), and [exact rerun commands](../../inference/BFCL_V4.md). Rebuilding the viewer embeds `results/bfcl_v4_*.jsonl` logs; V1 logs are excluded.

## Source and selection

Credits: [Berkeley Function Calling Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html), Shishir Patil and the Gorilla/BFCL contributors. The source is the official [Gorilla repository at `f7cf735`](https://github.com/ShishirPatil/gorilla/tree/f7cf7359b7ac615a0b294831c5ba2bc95ee4a000/berkeley-function-call-leaderboard/bfcl_eval/data). The consumed question/answer files and license are verified byte for byte against that commit. The local checkout's newer HEAD is recorded separately.

The three source categories contain **2,195 rows** (1,053 multiple, 258 simple, 884 irrelevance). These Live categories originated before V4 and remain in its corpus. This pilot does not cover all V4 tasks: parallel calls, multi-turn execution, web search, memory, and format-sensitivity tasks are outside this selection.

Selection is frozen before model evaluation:

1. Require one user turn, the selected tool count, and exactly one reference tool on positive rows.
2. Exclude V1 matches using Unicode NFKC, case folding, and Unicode word tokens joined with spaces. This ignores punctuation, capitalization, and spacing. Four additional high-similarity V1 candidates were explicitly excluded during review.
3. Require recorded semantic acceptance based on the full request, descriptions, schemas, and positive reference tool. Ambiguous tool labels and true capability mismatches are excluded. This is agent-assisted review, provided for your inspection.
4. Rank accepted candidates by `SHA256(seed + NUL + source_id)` and fill the 150/50/50 quotas. Use at most one normalized request, complete catalog (tool order ignored), and category + Live middle-ID family. The family rule is a conservative diversity heuristic; the upstream ID component has no documented universal semantic meaning.

Seed: `bfcl-v4-live-routing-250-20260929`. All original user text and full tool descriptions are retained; **zero card overrides or automatic truncations** are used. The model state collapses request whitespace only. The original nested messages, full schemas, and reference arguments remain available in each case.

V4 uses neutral `no_tool`, `clarify`, and `cannot_answer` descriptions. This removes V1's blanket claim that payment/messaging capabilities are unavailable, which would conflict with some offered V4 tools. The change is versioned in the manifest; V1 results used different meta cards.

## Scoring and limits

- **Positive tool accuracy:** exact relevant function ID on the 200 tool-required cases. Neither parameters nor execution are scored.
- **Primary routing accuracy:** correct function on positives; any of `no_tool`, `clarify`, or `cannot_answer` on the 50 negatives.
- **Exact action:** canonical `no_tool` on negatives. BFCL irrelevance labels do not establish which meta disposition is best, so this is a convention rather than a separately validated negative-action target.

This is a curated, short-context, single-step routing pilot, **not an official BFCL V4 score** or a random representative sample of its full corpus. Public BFCL prompts may have appeared in model training. The overlap guarantee concerns exact and normalized user requests; it does not claim that every possible semantic paraphrase has been detected. Keep this set frozen and use separate development prompts for tuning.

The [native Laya fit report](fit_report.json) checks all 250 complete rendered inputs with the pinned tokenizer: **250/250 fit**, maximum 312 total tokens, 217 head tokens, and 48 tokens in an option, under limits of 1,024/256/48. This check loads no model weights. All six other native adapters also passed their own input checks before evaluation; their reports are preserved in [runtime evidence](../../results/runtime/bfcl_v4/README.md). Native formats and budgets differ between models.

## Files

- [manifest.json](manifest.json): source pins, file hashes, counts, and target semantics.
- [validation_report.json](validation_report.json): final source preservation, duplicate checks, viewer contents, tokenizer report hash, and byte-identical rebuild verification.
- [selection_manifest.json](selection_manifest.json): seed, selected IDs, overlap and diversity checks, and exclusion counts.
- [selection_review.json](selection_review.json): accepted and excluded cases with reasons.
- [selection_audit.jsonl](selection_audit.jsonl): disposition of every row in the three selected source categories.
- [exclusions.jsonl](exclusions.jsonl): non-selected rows and their reasons.
- [index.csv](index.csv): compact prompt index with gold actions and identity hashes.
- [LICENSE](LICENSE): upstream Apache 2.0 license for adapted data. Repository MIT licensing covers original code.

## Rebuild

From the repository root, with Python 3 and Git, prepare the pinned source checkouts in a fresh workspace:

```sh
git clone --filter=blob:none https://github.com/ShishirPatil/gorilla.git .cache/bfcl-gorilla
git -C .cache/bfcl-gorilla checkout --detach f7cf7359b7ac615a0b294831c5ba2bc95ee4a000
git clone --filter=blob:none https://github.com/ShishirPatil/gorilla.git .cache/bfcl-v1
git -C .cache/bfcl-v1 checkout --detach 9df5c346ee0556c8a7cb09fd7206a39aadd904c2

python3 tools/build_bfcl_v4_set.py \
  --source-dir .cache/bfcl-gorilla/berkeley-function-call-leaderboard/bfcl_eval/data \
  --v1-source-dir .cache/bfcl-v1/berkeley-function-call-leaderboard/data \
  --v1-cases data/bfcl_v1/cases.jsonl \
  --review-file tools/bfcl_v4_selection_review.json \
  --output-dir data/bfcl_v4

python3 tools/build_prompt_viewer.py \
  --bfcl-version v4 --dataset-name 'BFCL V4 Live routing'

python3 -m unittest discover -s tests -p 'test_build*'
```

The builder and viewer use only Python's standard library. For the optional tokenizer check, use the [pinned inference environment](../../inference/README.md), download the standalone Laya tokenizer at the recorded revision, and supply its local directory:

```sh
inference/.venv/bin/python tools/check_bfcl_v4_fit.py \
  --cases data/bfcl_v4/cases.jsonl \
  --tokenizer-path /absolute/path/to/laya-typed-decisions/tokenizer \
  --output data/bfcl_v4/fit_report.json
```

Tokenizer revision: `convaiinnovations/laya-typed-decisions@1a793eb568e6718f15941d08f85432581df534e3`. The script verifies the tokenizer file digest before checking inputs. Native Laya rendering follows [`NandhaKishorM/laya@9d955671`](https://github.com/NandhaKishorM/laya/tree/9d955671415fc19f069b9cc998928075c1f255ec); the matching scored bundled checkpoint is `convaiinnovations/laya@55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851/typed-decisions`.
