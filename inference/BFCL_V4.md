# Rerun all seven models on BFCL V4

Run from the repository root on a Linux NVIDIA CUDA host. This evaluates the frozen [250-case BFCL V4 Live routing set](../data/bfcl_v4/README.md): 150 multiple-tool positives, 50 single-tool positives, and 50 no-call cases. It scores the next capability choice; the chat model supplies arguments later.

The frozen `data/bfcl_v4/cases.jsonl` SHA-256 is `2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8`. Upstream BFCL is pinned to `f7cf7359b7ac615a0b294831c5ba2bc95ee4a000`; the [manifest](../data/bfcl_v4/manifest.json) records selection review and prompt-card identities.

## Prepare the pinned environments

Use currently free GPUs. The recorded host was an H100 DGX with driver 570.195.03 and CUDA 12.8 wheels. Rizzo's supplied build also requires Git, CMake, a C++ compiler, and `/usr/local/cuda-12.8/bin/nvcc`; its setup targets H100 compute capability 9.0. See its [setup details](rizzo/README.md) before using another GPU architecture.

Run these cache exports in **each** server or scoring terminal. They keep downloads and runtime assets in an owner-controlled directory and avoid the default `/scratch` dependency:

```sh
export JEV_EVAL_CACHE="$HOME/.cache/jev-model-performance"
export HF_HOME="$JEV_EVAL_CACHE/hf"
export RIZZO_ASSETS="$JEV_EVAL_CACHE/rizzo"
export VON_WEIGHTS_DIR="$JEV_EVAL_CACHE/von/43bbca0fb17f424539416ee8eb3de33cfc3dacf3"
export NANOJEV_ASSETS="$JEV_EVAL_CACHE/nanojev"
mkdir -p "$HF_HOME"
nvidia-smi
printf '%s  %s\n' '2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8' 'data/bfcl_v4/cases.jsonl' | sha256sum --check
```

Run setup once in a fresh checkout:

```sh
bash inference/setup.sh
bash inference/nimble/setup.sh
bash inference/semif/setup.sh
bash inference/rizzo/setup.sh
bash inference/von/setup.sh
bash inference/nanojev/setup.sh
```

These scripts pin Python 3.12.14, source commits, dependencies, and checkpoint identities. Laya, Kev, NanoJev, and the HTTP evaluator use `inference/.venv`; Nimble, SemIf, and Von have separate `.venv` directories. Rizzo uses `.cache/third_party/rizzo/.venv` and upstream's pinned `uv.lock`. Keep the committed `requirements.txt` / `requirements.resolved.txt` files with the run; environments, downloaded weights, and compiled libraries are excluded from Git. No system Python change is needed. Fresh setup downloads weights; set `HF_HUB_OFFLINE=1` only after every required pinned asset is cached.

| Model / setup reference | GPU | Recorded precision and native path | Canonical port |
| --- | ---: | --- | --- |
| [Laya typed-decisions](README.md#shared-layakev-environment) | 0 | FP16 CUDA autocast; native choice head | 8007 |
| [Kev-0.8B](README.md#shared-layakev-environment) | 1 | FP32; pointer head; fused kernels / CUDA graphs off | 8008 |
| [Nimble 9B](nimble/README.md) | 2 | BF16; merged adapter; native candidate logits | none |
| [SemIf / Qwen3.5-4B](semif/README.md) | 3 | BF16; direct allowed-letter logits | none |
| [Rizzo Flow](rizzo/README.md) | 4 | Q8_0 GGUF; pinned llama.cpp CUDA | 8017 |
| [Von](von/README.md) | 5 | Native FP32; option chains disabled; overflow refused | 8014 |
| [NanoJev](nanojev/README.md) | 6 | BF16 forward; game-trained attention decision head | 8015 bridge / 8765 native |

Checkpoint and implementation authors are credited in [model credits and references](../README.md#model-credits-and-references). SemIf is a scoring method over frozen Qwen weights here. These native paths preserve the tested decision heads; serving only a generative base model with vLLM or SGLang would evaluate a different system.

## Start the five HTTP servers

Run **one command per terminal**, after the cache exports above. Keep each terminal open. The launchers bind to localhost and check GPU availability; NanoJev starts both its native server and bridge.

```sh
bash inference/serve.sh laya 0
```

```sh
KEV_DATE_FACTS=0 bash inference/serve.sh kev 1
```

```sh
bash inference/rizzo/serve.sh 4
```

```sh
bash inference/von/serve.sh 5 8014
```

```sh
bash inference/nanojev/serve.sh 6
```

## Score all 250 cases

In the evaluator terminal, create a **fresh** output directory. Published `results/bfcl_v4_*.jsonl` files are already complete; they resume existing work and do not create a new independent run. Keep this same `JEV_RESULTS` value for every command and any later resume.

```sh
export JEV_RESULTS=".cache/reruns/bfcl_v4-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$JEV_RESULTS"
```

After each HTTP server is ready, run:

```sh
inference/.venv/bin/python inference/evaluate.py \
  --provider laya --endpoint http://127.0.0.1:8007 \
  --model convaiinnovations/laya-typed-decisions \
  --model-revision 1a793eb568e6718f15941d08f85432581df534e3 \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_laya.jsonl"

inference/.venv/bin/python inference/evaluate.py \
  --provider kev --endpoint http://127.0.0.1:8008 --model kev-latest \
  --model-revision 9a45d25eb2ab761841196625383fa1dff0e56c1e \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_kev.jsonl"

inference/.venv/bin/python inference/evaluate.py \
  --provider rizzo --endpoint http://127.0.0.1:8017 --model rizzo-latest \
  --model-revision 55633c8cbd2b826bd3eefdeb05310450996649df \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_rizzo.jsonl"

inference/.venv/bin/python inference/evaluate.py \
  --provider von --endpoint http://127.0.0.1:8014 --model von-1.3 \
  --model-revision 43bbca0fb17f424539416ee8eb3de33cfc3dacf3 \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_von.jsonl"

inference/.venv/bin/python inference/evaluate.py \
  --provider nanojev --endpoint http://127.0.0.1:8015 --model nanojev-unified-games-v1 \
  --model-revision 047b927b30882a1138fc504821b82ac145a4b81a \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_nanojev.jsonl"
```

To match the recorded Laya/Kev/Von warmup protocol, first run each corresponding evaluator command with `--limit 3` and a **separate** output such as `"$JEV_RESULTS/smoke/bfcl_v4_laya.jsonl"`, then run the full command above while keeping its server alive. Those three smoke rows are outside the scored 250. Rizzo/NanoJev instead used `--limit 2` in their final output file, then resumed that same file without `--limit`; their first two rows remain in the score.

Nimble and SemIf run directly, without HTTP servers. Cache exports must also be set in their scoring terminals. Nimble's first preparation merges the pinned adapter on CPU; the ready manifest prevents reuse of mismatched merged weights.

```sh
CUDA_VISIBLE_DEVICES=2 inference/nimble/.venv/bin/python inference/nimble/run.py \
  --prepare-only --merged-dir "$JEV_EVAL_CACHE/nimble-9b-merged-bd792f44"

CUDA_VISIBLE_DEVICES=2 inference/nimble/.venv/bin/python inference/nimble/run.py \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_nimble.jsonl" \
  --merged-dir "$JEV_EVAL_CACHE/nimble-9b-merged-bd792f44" --limit 2
CUDA_VISIBLE_DEVICES=2 inference/nimble/.venv/bin/python inference/nimble/run.py \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_nimble.jsonl" \
  --merged-dir "$JEV_EVAL_CACHE/nimble-9b-merged-bd792f44"

CUDA_VISIBLE_DEVICES=3 inference/semif/.venv/bin/python inference/semif/run.py \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_semif.jsonl" \
  --max-tokens 4096 --limit 2
CUDA_VISIBLE_DEVICES=3 inference/semif/.venv/bin/python inference/semif/run.py \
  --cases data/bfcl_v4/cases.jsonl --output "$JEV_RESULTS/bfcl_v4_semif.jsonl" \
  --max-tokens 4096
```

Nimble is pinned to `bespokelabs/Bespoke-Nimble-9B@bd792f44ec8e265be861bfcdf4e05967ffe0e858`, with Qwen3.5-9B base revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. SemIf uses `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. Both runners hardcode these pins. Their two-case smoke and subsequent resume reload the model; all 250 rows, including initial cold inference in both processes, contribute to reported latency. Model loading itself occurs outside per-case latency.

## Input checks and saved evidence

The recorded run checked each model's **actual native input construction** on all 250 cases before scoring. All fitted without truncation, including Laya's separate head/option limits. These are saved audit results, not an automatic preflight step shared by the seven setup scripts.

| Model | Largest native input / path | Preflight evidence |
| --- | ---: | --- |
| Laya | 312 tokens | [Audit](../results/runtime/bfcl_v4/laya/preflight.json) |
| Kev | 301 tokens | [Audit](../results/runtime/bfcl_v4/kev/preflight.json) |
| Nimble | 470 tokens | [Audit](../results/runtime/bfcl_v4/nimble_input_preflight.json) |
| SemIf | 393 tokens | [Audit](../results/runtime/bfcl_v4/semif_input_preflight.json) |
| Rizzo | 445 tokens | [Audit](../results/runtime/bfcl_v4/rizzo_native_preflight.json) |
| Von | 291 tokens | [Audit](../results/runtime/bfcl_v4/von/preflight.json) |
| NanoJev | 258 tokens | [Audit](../results/runtime/bfcl_v4/nanojev_native_preflight.json) |

Native token counts use different encoders and prompt formats. Only the Jev state, choice instructions, and offered capability descriptions reach models. Original BFCL schemas/reference calls and gold labels stay in the case/evaluator; they are never part of model input. Missing argument values remain the chat model's responsibility.

Each JSONL records case ID, selection, probabilities, status, attempts, and timing. Nimble/SemIf also record native option logits and prompt hashes. Adjacent `.meta.json` and `.summary.json` files bind results to dataset/review hashes, prompt-card version, checkpoint/source revisions, runtime identity, and completion counts. Rerunning identical commands resumes pending cases; `--rerun-errors` retries errors. Changed paths, endpoints, or model identity require a fresh output file. Preserve raw logs and sidecars before comparing runs.

- **Exact right tool:** exact function ID on the 200 positive cases.
- **Tool routing:** exact function on positives; any `no_tool`, `clarify`, or `cannot_answer` on the 50 negatives, because no function was selected.
- **Exact action:** exact gold ID on all 250, requiring `no_tool` on negatives. BFCL does not establish gold distinctions among the three no-function subtypes.

Errors count as incorrect. None of these scores evaluates arguments, execution, or final task completion; this is a derived routing pilot, not an official BFCL V4 leaderboard score. Probabilities are conditional option scores and are not calibrated across these models.

## Recorded DGX-59 execution

The saved run used SSH alias `vp-dgx-59` / hostname `dgxh100-059`, with exported code snapshot `aa4130c30e3146ec1d5e2b228ccc49923934139a` under `/data/home/pritish/jev-model-performance-v4-dgx59-20260929`. It reused pinned environments and upstream source checkouts in `/data/home/pritish/jev-model-performance`, with task-owned weights/runtime assets in `/data/home/pritish/.cache/jev-model-performance-dgx59`. `/scratch/pritish` was unavailable on this host. The environment audits record the packages and source/weight identities actually used.

Actual localhost endpoints were **18007 Laya, 18008 Kev, 18017 Rizzo, 18014 Von, 18015 NanoJev bridge, and 18765 NanoJev native**. The GPU mapping was the same as the table above. Canonical launchers in this guide use their standard 8000-family ports; the published metadata retains the actual 18000-family endpoints.

[Runtime evidence](../results/runtime/bfcl_v4/) contains environment/package audits, launches, exact evaluation arguments, smoke/full console logs, native input checks, weight verification, and output validation. In particular, see [Nimble/SemIf arguments](../results/runtime/bfcl_v4/nimble_semif_runtime_audit.json), [Rizzo arguments](../results/runtime/bfcl_v4/rizzo_eval_commands.json), [NanoJev arguments](../results/runtime/bfcl_v4/nanojev_eval_commands.json), and each HTTP model's launch audit. Responses were measured serially per model on separate GPUs, with different inference paths and warmup protocols; recorded latency is an observed run statistic, not a controlled speed ranking.

Open the [V4 viewer](../data/bfcl_v4/viewer.html) and import a fresh `bfcl_v4_<model>.jsonl` to inspect its selections beside the prompts. The published comparison and charts are rebuilt from saved logs; see the [results report](../results/README.md).
