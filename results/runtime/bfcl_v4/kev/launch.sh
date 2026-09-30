#!/usr/bin/env bash
set -euo pipefail
export PYTHONNOUSERSITE=1
export TOKENIZERS_PARALLELISM=false
export HF_HOME=/data/home/pritish/.cache/jev-model-performance-dgx59/hf
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export CUDA_VISIBLE_DEVICES=1
export KEV_DTYPE=fp32 KEV_FUSED=0 KEV_CUDA_GRAPHS=0 KEV_DATE_FACTS=0
exec /data/home/pritish/jev-model-performance/inference/.venv/bin/python -m kev.serve --run jaredpalmer/kev-0.8b@9a45d25eb2ab761841196625383fa1dff0e56c1e --host 127.0.0.1 --port 18008
