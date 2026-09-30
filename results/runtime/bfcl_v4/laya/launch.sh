#!/usr/bin/env bash
set -euo pipefail
export PYTHONNOUSERSITE=1
export TOKENIZERS_PARALLELISM=false
export HF_HOME=/data/home/pritish/.cache/jev-model-performance-dgx59/hf
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export CUDA_VISIBLE_DEVICES=0
export LAYA_DEVICE=cuda LAYA_HOST=127.0.0.1 LAYA_PORT=18007
export LAYA_MODELS=typed-decisions LAYA_PRELOAD=1 LAYA_REVISION=reviewed LAYA_CUDA_AMP=fp16
export LAYA_SHA256_DIGESTS='{"typed-decisions":{"model.safetensors":"4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e"}}'
exec /data/home/pritish/jev-model-performance/inference/.venv/bin/laya-serve
