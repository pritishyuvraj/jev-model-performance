# Von BFCL routing run

This folder reproduces the native Von 1.3.1 `/v1/systemone` server on one CUDA GPU. It uses [Von source](https://github.com/wfzyx/von) commit `a930f9d5709e62388cd4d3bd45675aaaf323b973` and [wfzyx/von weights](https://huggingface.co/wfzyx/von) revision `43bbca0fb17f424539416ee8eb3de33cfc3dacf3`. Von 1.3 changes the inference engine; the model card says its weights are unchanged from Von 1.2. The server uses `--no-chains` so its deterministic chain-of-options controller does not preprocess BFCL cases, and refuses oversize states rather than truncating them.

Run from the repository root on a CUDA machine. `setup.sh` creates an isolated `inference/von/.venv`, installs pinned packages from `requirements.txt`, checks out the source revision, downloads the exact checkpoint to `/scratch/$USER/jev-model-performance/von/<revision>`, verifies the key weight files against `weights.sha256.txt`, and records `requirements.resolved.txt`. Set `VON_WEIGHTS_DIR` to another directory if needed.

```sh
bash inference/setup.sh                   # once, for the project-local uv binary
bash inference/von/setup.sh
bash inference/von/serve.sh 5 8014         # GPU index and localhost port
```

From another shell, use the same frozen 250-case evaluator as Laya and Kev:

```sh
python3 inference/evaluate.py --provider von \
  --endpoint http://127.0.0.1:8014 --model von-1.3 \
  --model-revision 43bbca0fb17f424539416ee8eb3de33cfc3dacf3 \
  --output results/bfcl_v1_von.jsonl
```

The evaluator sends only the case's `jev.laya.state` and `jev.laya.questions`, never the BFCL answer or gold label. Each output JSONL row stores the selected action, status, probabilities, timing, and case ID. The `.meta.json` and `.summary.json` sidecars hold the run identity and aggregate score. The server binds to localhost; it can be reached over an SSH tunnel when needed.

## Recorded run

On `vp-dgx-65` GPU 5, Von returned 250 decisions with zero request errors. It selected the correct function or correctly selected no function on **228/250 cases (91.2%)**. The stricter exact-action score was **179/250 (71.6%)**. On 49 of the 50 no-call cases it selected no function, but it chose `cannot_answer` 38 times and `clarify` 11 times rather than the BFCL-derived `no_tool` label. This explains the large gap between the two scores; BFCL does not distinguish those no-function subtypes.

See [per-case selections](../../results/bfcl_v1_von.jsonl), [summary](../../results/bfcl_v1_von.summary.json), and [run metadata](../../results/bfcl_v1_von.meta.json). The run metadata records the no-chains flag, CUDA device, pinned source and checkpoint revisions, and verified weight hashes.
