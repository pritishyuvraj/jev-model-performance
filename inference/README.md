# Laya and Kev on an NVIDIA DGX

This folder runs the two **decision models** on the selected BFCL V1 routing cases. The score is exact next-tool choice; it does not measure argument generation or tool execution. Both models receive the same `jev.laya` state and choice question from each row in [`cases.jsonl`](../data/bfcl_v1/cases.jsonl). The original BFCL answer and `gold_next_action_ids` stay outside the model request.

Use the models' native PyTorch/CUDA `/v1/systemone` servers. [Laya typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions) is a non-generative ModernBERT decision model. [Kev-0.8B](https://huggingface.co/jaredpalmer/kev-0.8b) uses a Qwen3.5 base, LoRA adapter and option-pointer head, also without text generation. A generic [vLLM pooling classifier](https://docs.vllm.ai/en/stable/models/pooling_models/) or [SGLang model server](https://docs.sglang.ai/) does not implement these checkpoint-specific choice heads and question handling. Hosting their base architectures alone would score a different model. Native serving also avoids adding an inference layer for only 250 examples.

## Reproducible environment

On `vp-dgx-65`, start in this repository's root. The setup uses the existing system Python and pip only to install pinned `uv` into the ignored `inference/.cache/uv-bootstrap`; `uv` then installs Python 3.12.14 and creates `inference/.venv`. It does not need sudo, system `venv`, or a system Python change, and leaves other user-installed `uv` versions alone.

```sh
bash inference/setup.sh
```

[`requirements.txt`](requirements.txt) pins PyTorch 2.8.0, Transformers 5.17.0 and the exact Laya and Kev serving-code commits. The scored run's full dependency snapshot is [`requirements.resolved.txt`](requirements.resolved.txt). `setup.sh` installs from that snapshot when it is present, then writes the installed package set back to the same file. If the snapshot is absent, it installs the top-level requirements instead. The `.venv` contains binaries and is deliberately not committed. `setup.sh` checks that PyTorch sees CUDA; if an existing `.venv` has another Python version, it stops without replacing it.

The model weights are pinned separately from Python packages:

| Model | Weight revision used here | Runtime code |
| --- | --- | --- |
| Laya typed-decisions | `convaiinnovations/laya` bundle `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, subfolder `typed-decisions`; its weight SHA-256 `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e` matches standalone `convaiinnovations/laya-typed-decisions@1a793eb568e6718f15941d08f85432581df534e3` | `NandhaKishorM/laya@9d955671415fc19f069b9cc998928075c1f255ec` |
| Kev-0.8B | `jaredpalmer/kev-0.8b@9a45d25eb2ab761841196625383fa1dff0e56c1e`; checkpoint metadata pins `Qwen/Qwen3.5-0.8B-Base@dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68` | `jaredpalmer/kev@461b5eac35d96e95c7dede21b9e0402b4cf7092d` |

The first server start downloads its pinned weights into the Hugging Face cache. [`serve.sh`](serve.sh) defaults `HF_HOME` to `/scratch/$USER/jev-model-performance/hf`; set `HF_HOME` yourself before both launches to use another owner-controlled location. Keep the same value for later reruns.

## Start the servers

Check current GPU use with `nvidia-smi` first. Choose free GPU indices for the two commands below; `0` and `1` are examples, not reservations. Each model fits on one H100, so tensor parallelism and all eight GPUs are unnecessary. [`serve.sh`](serve.sh) checks the selected GPU again, rejects one using more than 1 GiB or over 10% utilization, and starts the pinned native runtime on localhost.

Terminal A:

```sh
bash inference/serve.sh laya 0
```

Terminal B:

```sh
bash inference/serve.sh kev 1
```

Use another terminal or SSH tunnel to query the servers. The launcher sets the model, runtime, precision, and localhost settings below; the native commands are included for inspection or a manual restart. Set `HF_HOME` yourself when using them directly.

Laya on port 8007:

```sh
CUDA_VISIBLE_DEVICES=0 \
LAYA_DEVICE=cuda LAYA_HOST=127.0.0.1 LAYA_PORT=8007 \
LAYA_MODELS=typed-decisions LAYA_PRELOAD=1 \
LAYA_REVISION=reviewed LAYA_CUDA_AMP=fp16 \
LAYA_SHA256_DIGESTS='{"typed-decisions":{"model.safetensors":"4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e"}}' \
inference/.venv/bin/laya-serve
```

`LAYA_REVISION=reviewed` makes Laya's server load its reviewed bundled checkpoint revision; the digest check verifies the actual typed-decisions weights. The explicit `model` field in the evaluator selects typed-decisions rather than Laya's general English checkpoint. FP16 matches the existing Jev harness's Laya precision; record it with the score.

Kev on port 8008:

```sh
CUDA_VISIBLE_DEVICES=1 \
KEV_DTYPE=fp32 KEV_FUSED=0 KEV_CUDA_GRAPHS=0 \
inference/.venv/bin/python -m kev.serve \
  --run jaredpalmer/kev-0.8b@9a45d25eb2ab761841196625383fa1dff0e56c1e \
  --host 127.0.0.1 --port 8008
```

Kev's FP32 path matches its reference evaluation. Optional fused kernels and CUDA graphs are disabled for the initial accuracy run; no extra acceleration package is installed. Both native servers return a `choice` and probability distribution rather than generating a tool call.

## Evaluate

With both servers ready, run from the repository root:

```sh
inference/.venv/bin/python inference/evaluate.py --provider laya \
  --endpoint http://127.0.0.1:8007 \
  --cases data/bfcl_v1/cases.jsonl \
  --output results/laya-predictions.jsonl

inference/.venv/bin/python inference/evaluate.py --provider kev \
  --endpoint http://127.0.0.1:8008 \
  --cases data/bfcl_v1/cases.jsonl \
  --output results/kev-predictions.jsonl
```

The evaluator records each case's predicted choice and reports two accuracies overall and by subset stratum:

- **Exact BFCL-derived action:** the choice must equal the case's gold action ID, including `no_tool` on no-call rows.
- **Tool selection:** the choice must name the right function on call rows; on BFCL no-call rows, any of `no_tool`, `clarify`, or `cannot_answer` gets credit because no function was selected. This is the primary measure for Jev's tool-only role.

It writes `.meta.json` and `.summary.json` beside each prediction file and resumes completed cases on rerun; `--rerun-errors` retries failed requests. Keep the prediction files, summaries, dataset hash, package snapshot, source commits, weight revisions, GPU model, and precision together. A failed request counts as incorrect in both metrics. Neither metric scores arguments or execution. This derived 250-case routing score is not an official BFCL leaderboard result.

Sources: [Laya serving and revision controls](https://github.com/NandhaKishorM/laya/blob/9d955671415fc19f069b9cc998928075c1f255ec/laya/revisions.py), [Laya router checkpoint map](https://github.com/NandhaKishorM/laya/blob/9d955671415fc19f069b9cc998928075c1f255ec/laya/router.py), [Kev local serving](https://github.com/jaredpalmer/kev/blob/461b5eac35d96e95c7dede21b9e0402b4cf7092d/README.md), [uv-managed Python](https://docs.astral.sh/uv/guides/install-python/).
