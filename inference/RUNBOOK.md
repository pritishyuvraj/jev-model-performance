# Run the seven BFCL V1 routing evaluations again

Run these commands from the repository root on a Linux NVIDIA CUDA host. The recorded runs used `vp-dgx-65` with H100 GPUs. Check `nvidia-smi` and substitute free GPU indices for the examples below. Run models sequentially if you reuse an index; the server commands stay in the foreground, so launch the evaluator in another terminal. Setup downloads pinned code and weights into the documented caches, primarily under `/scratch/$USER/jev-model-performance`.

The committed `results/bfcl_v1_*.jsonl` files are complete, resumable runs. Every command here writes to a **fresh**, Git-ignored `.cache/reruns/` path, preserving the published logs. Each runner writes `.meta.json` and `.summary.json` beside its new JSONL. Gold labels and original BFCL answers remain in the evaluator, outside the model request.

## Shared setup

```sh
nvidia-smi
bash inference/setup.sh
```

The shared setup creates `inference/.venv` with the pinned Laya/Kev evaluator dependencies. It is also required before SemIf, Rizzo, Von, and NanoJev setup. Nimble has its own environment. See [the environment and checkpoint pins](README.md) and each model's linked instructions below.

## Laya typed-decisions

Terminal A:

```sh
bash inference/serve.sh laya 0
```

Terminal B, after the localhost server is ready:

```sh
inference/.venv/bin/python inference/evaluate.py \
  --provider laya --endpoint http://127.0.0.1:8007 \
  --cases data/bfcl_v1/cases.jsonl \
  --output .cache/reruns/bfcl_v1_laya.jsonl
```

## Kev-0.8B

Terminal A:

```sh
bash inference/serve.sh kev 1
```

Terminal B:

```sh
inference/.venv/bin/python inference/evaluate.py \
  --provider kev --endpoint http://127.0.0.1:8008 \
  --cases data/bfcl_v1/cases.jsonl \
  --output .cache/reruns/bfcl_v1_kev.jsonl
```

## Bespoke Nimble 9B

```sh
bash inference/nimble/setup.sh
CUDA_VISIBLE_DEVICES=2 inference/nimble/.venv/bin/python inference/nimble/run.py --prepare-only
CUDA_VISIBLE_DEVICES=2 inference/nimble/.venv/bin/python inference/nimble/run.py \
  --output .cache/reruns/bfcl_v1_nimble.jsonl
```

Nimble's [native scorer details](nimble/README.md) explain its candidate logits and merged BF16 weights.

## SemIf on frozen Qwen3.5-4B

```sh
bash inference/semif/setup.sh
CUDA_VISIBLE_DEVICES=3 HF_HOME=/scratch/$USER/jev-model-performance/hf \
  inference/semif/.venv/bin/python inference/semif/run.py \
  --output .cache/reruns/bfcl_v1_semif.jsonl
```

The shared setup above is required before SemIf setup because it supplies the pinned local `uv` binary. [SemIf details](semif/README.md) describe the frozen checkpoint and direct-logit method.

## Rizzo Flow 4B Q8_0

```sh
bash inference/rizzo/setup.sh
```

Terminal A:

```sh
bash inference/rizzo/serve.sh 3
```

Terminal B:

```sh
inference/.venv/bin/python inference/evaluate.py \
  --provider rizzo --endpoint http://127.0.0.1:8017 \
  --model rizzo-latest \
  --model-revision 55633c8cbd2b826bd3eefdeb05310450996649df \
  --output .cache/reruns/bfcl_v1_rizzo.jsonl
```

The [Rizzo instructions](rizzo/README.md) include its pinned Q8_0 weight hash and CUDA build details.

## Von 1.3, chains off

```sh
bash inference/von/setup.sh
```

Terminal A:

```sh
bash inference/von/serve.sh 5 8014
```

Terminal B:

```sh
inference/.venv/bin/python inference/evaluate.py \
  --provider von --endpoint http://127.0.0.1:8014 \
  --model von-1.3 \
  --model-revision 43bbca0fb17f424539416ee8eb3de33cfc3dacf3 \
  --output .cache/reruns/bfcl_v1_von.jsonl
```

The [Von instructions](von/README.md) explain why this run disables its option-chain controller.

## NanoJev `unified-games-v1`

```sh
bash inference/nanojev/setup.sh
```

Terminal A:

```sh
bash inference/nanojev/serve.sh 6
```

Terminal B:

```sh
inference/.venv/bin/python inference/evaluate.py \
  --provider nanojev --endpoint http://127.0.0.1:8015 \
  --model nanojev-unified-games-v1 \
  --model-revision 047b927b30882a1138fc504821b82ac145a4b81a \
  --output .cache/reruns/bfcl_v1_nanojev.jsonl
```

The [NanoJev instructions](nanojev/README.md) explain the native server and local HTTP bridge.

## Inspect a fresh run

Open [`data/bfcl_v1/viewer.html`](../data/bfcl_v1/viewer.html) and import a fresh `.cache/reruns/bfcl_v1_<model>.jsonl` file. The viewer's embedded logs remain the published runs. Fresh scores appear in the new `.summary.json` files. To regenerate the published comparison from the committed logs without model inference, run `python3 tools/summarize_runs.py --check` and follow [the chart commands](../README.md#reproduce-the-saved-table-and-charts).
