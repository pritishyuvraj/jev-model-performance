# Bespoke Nimble 9B native CUDA BFCL run

This runs the latest pinned `bespokelabs/Bespoke-Nimble-9B` checkpoint on the same 250 BFCL routing choices used for Laya and Kev. The native CUDA scorer reads candidate logits; it does not generate tool-call text. Only the case state and offered action descriptions reach the model. The evaluator retains gold labels locally.

The [Nimble source](https://github.com/bespokelabsai/nimble) is pinned to `62076b4f2d365b5879dafcf7f6dd072a1fe76df7`. The model is pinned to `bd792f44ec8e265be861bfcdf4e05967ffe0e858`; its `schema_config.json` pins the Qwen base. `setup.sh` creates an isolated Python 3.12.14 virtual environment and writes the installed dependency snapshot to `requirements.resolved.txt`. The merged BF16 weights and Hugging Face cache live on `/scratch` by default, outside Git.

From the repository root on a CUDA machine:

```sh
bash inference/nimble/setup.sh
CUDA_VISIBLE_DEVICES=2 inference/nimble/.venv/bin/python inference/nimble/run.py --prepare-only
CUDA_VISIBLE_DEVICES=2 inference/nimble/.venv/bin/python inference/nimble/run.py
```

Choose a currently free GPU index. `run.py` writes a resumable prediction JSONL and adjacent metadata/summary files under `results/`. Each successful prediction records the selected action, all candidate probabilities and logits, token hash, latency, and run identity. The full-set accuracy counts errors as incorrect and follows the shared BFCL scoring rules. The result measures tool selection, not arguments or execution.
