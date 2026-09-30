#!/usr/bin/env bash
set -euo pipefail
export PYTHONNOUSERSITE=1
export TOKENIZERS_PARALLELISM=false
export HF_HOME=/data/home/pritish/.cache/jev-model-performance-dgx59/hf
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export CUDA_VISIBLE_DEVICES=5 VON_DEVICE=cuda VON_ON_OVERFLOW=refuse
cd /data/home/pritish/jev-model-performance-v4-dgx59-20260929/results/runtime/bfcl_v4/von/runtime
exec /data/home/pritish/jev-model-performance/inference/von/.venv/bin/von serve --host 127.0.0.1 --port 18014 --model von-1.3 --device cuda --no-chains --on-overflow refuse
