# NanoJev BFCL routing run

This run uses [NanoJev's published `unified-games-v1` checkpoint](https://github.com/TianyuCodings/NanoJev) and native CUDA decision server. It is a game-trained checkpoint, so BFCL tool routing is an out-of-domain test. It receives the same text state, choice question, and descriptions as Laya and Kev. [`bridge.py`](bridge.py) translates only the HTTP envelope between NanoJev's `/api/evaluate` and the evaluator's `/v1/systemone`; it does not alter the state or options.

The [shared pinned environment](../README.md) supplies Python 3.12.14, PyTorch 2.8.0 (CUDA 12.8), Transformers 5.17.0, and Hugging Face Hub. NanoJev upstream documents PyTorch 2.14.0; this run used the earlier shared environment successfully, so use these pinned versions to reproduce *this* score. [`requirements.txt`](requirements.txt) points to the exact installed package snapshot.

From the repository root on the DGX:

```sh
bash inference/setup.sh
bash inference/nanojev/setup.sh
bash inference/nanojev/serve.sh 6
```

The setup pins source commit `76fdfc9ecdca45a9bcef17991a07d3041a87685a` and weights commit `047b927b30882a1138fc504821b82ac145a4b81a`; it checks `best.safetensors` SHA-256 `f68c47d66998231b86b7e91b4ed5e82ae23acf104c8b7cd6d165c3ac7b7ffe1b`. The model uses its `attention` set head, BF16 forward pass, and no generated tokens. The local bridge listens on port 8015; its native server listens on port 8765. Choose a free GPU index when starting it.

In another terminal:

```sh
inference/.venv/bin/python inference/evaluate.py \
  --provider nanojev --endpoint http://127.0.0.1:8015 \
  --model nanojev-unified-games-v1 \
  --model-revision 047b927b30882a1138fc504821b82ac145a4b81a \
  --output results/bfcl_v1_nanojev.jsonl
```

The saved [selection log](../../results/bfcl_v1_nanojev.jsonl), [run metadata](../../results/bfcl_v1_nanojev.meta.json), and [summary](../../results/bfcl_v1_nanojev.summary.json) record all 250 cases and zero request failures.
