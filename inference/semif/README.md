# SemIf on BFCL V1

This runner uses the [author's SemIf implementation](https://github.com/TheoLeeCJ/SemIf-OpenJev) at commit `23cf1f39fc9534fe81437200959b6dfc7106e45a` with the frozen `Qwen/Qwen3.5-4B` checkpoint at `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. SemIf reads the logits of allowed answer letters and generates no answer text. It is a baseline over a frozen model, not a separately trained SemIf checkpoint.

On a Linux NVIDIA GPU with a CUDA 12.8 compatible driver, from the repository root:

```bash
bash inference/setup.sh
inference/semif/setup.sh
CUDA_VISIBLE_DEVICES=3 HF_HOME=/scratch/$USER/jev-model-performance/hf \
  inference/semif/.venv/bin/python inference/semif/run.py
```

The setup creates `inference/semif/.venv`, installs the exact Python requirements in this folder, verifies the author's source commit, and records resolved packages. The run writes `results/bfcl_v1_semif.jsonl`, `.meta.json`, and `.summary.json`. It resumes after interruption and keeps one decision with option probabilities per case. Use `--limit 2` for a smoke run; the next invocation continues the remaining cases. Use `--rerun-errors` to retry recorded failures.

The adapter sends only the benchmark's Jev state, its next-step question, and offered options to SemIf. Each SemIf option description includes its option ID and explanatory text, because SemIf's native prompt otherwise hides option IDs. Gold labels and BFCL source records remain outside model inputs. Scores have the same exact-action and tool-selection meanings as the Laya/Kev runs.
