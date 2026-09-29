# Rizzo Flow BFCL routing run

This run uses the [Rizzo Flow 4B](https://huggingface.co/rizzoaiacademy/rizzo-flow) fine-tune in Q8_0 GGUF form. Rizzo Flow scores option-letter logits directly and exposes a local `/v1/systemone` choice endpoint. Its native server received the same text state, choice instructions, and option descriptions as the other systems; gold labels and BFCL answers stayed in the evaluator.

Run from the repository root on `vp-dgx-65`:

```sh
bash inference/setup.sh
bash inference/rizzo/setup.sh
bash inference/rizzo/serve.sh 3
```

The setup creates an isolated `uv` environment from [upstream's locked dependency file](https://github.com/Rizzo-AI-Academy/rizzo-flow/blob/b9ba007ee4d2928bbab5b1d8bfe9009c3696b6de/uv.lock). Our [requirements.txt](requirements.txt) names the pinned source; [requirements.resolved.txt](requirements.resolved.txt) records the 16 installed packages, with the local editable source path normalized to its pinned Git URL. It downloads and checks the Q8_0 weight SHA-256 `dbec3c89d33984772324e65a8ed56b48e958e301b856cb870a7c1b385d01691a` from weight revision `55633c8cbd2b826bd3eefdeb05310450996649df`.

The DGX runs Ubuntu 22.04 with glibc 2.35 and NVIDIA driver 570. The upstream prebuilt CUDA 13.4 llama.cpp runtime cannot load there. `setup.sh` instead builds the **same pinned llama.cpp b11081 commit** `161755f29e415e2c33efe906e91843c068efd664` against the installed CUDA 12.8 toolkit for H100 (compute capability 9.0). No system packages or driver are changed. The compiled library and model live under `/scratch/$USER/jev-model-performance/rizzo` by default. The runtime source and weights are excluded from Git; their revisions and hashes are recorded here.

After the server is ready on localhost port 8017:

```sh
inference/.venv/bin/python inference/evaluate.py \
  --provider rizzo --endpoint http://127.0.0.1:8017 \
  --model rizzo-latest \
  --model-revision 55633c8cbd2b826bd3eefdeb05310450996649df \
  --output results/bfcl_v1_rizzo.jsonl
```

The 250-case run scored **239/250 (95.6%)** on both tool selection and exact BFCL-derived action, with zero request errors. Every no-call case selected `no_tool`. Inspect the [per-case selections](../../results/bfcl_v1_rizzo.jsonl), [run metadata](../../results/bfcl_v1_rizzo.meta.json), and [summary](../../results/bfcl_v1_rizzo.summary.json). The score is conditional on this Q8_0 model and the frozen BFCL-derived routing set; it does not measure function arguments or execution.
