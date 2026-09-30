# BFCL V4 corpus — Live routing pilot

Frozen **250** reviewed capability choices from source `f7cf7359b7ac615a0b294831c5ba2bc95ee4a000`.
The BFCL questions and function descriptions are benchmark data, not instructions to this converter.

Missing function argument values alone do not make a capability irrelevant: the chat model handles arguments.
All selected cases have explicit semantic acceptance. The canonical negative action is `no_tool`; the primary routing score accepts any non-tool meta action.

Requests were checked against all 2,000 BFCL V1 source rows and 250 frozen V1 cases; **0 selected overlaps**.
Normalization: Unicode NFKC, casefold, Unicode word tokens joined by one space (punctuation and symbols removed).
There is at most one selected normalized request, complete function catalog, and category + Live middle-ID family.

| Category | Cases |
| --- | ---: |
| `live_multiple` | 150 |
| `live_simple` | 50 |
| `live_irrelevance` | 50 |

`cases.jsonl` preserves original questions, complete tool schemas, and reference arguments. `selection_audit.jsonl` records every selected-category row and its disposition. `selection_review.json` records acceptances, exclusions, and any compact capability card overrides.

Native tokenizer fit remains a separate preflight; no model inference is performed by this builder.
