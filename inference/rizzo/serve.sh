#!/usr/bin/env bash
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd -- "$here/../.." && pwd)"
gpu="${1:-}"
if [[ ! "$gpu" =~ ^[0-9]+$ ]]; then
  echo "Usage: bash inference/rizzo/serve.sh GPU_INDEX" >&2
  exit 2
fi
read -r used_mib utilization < <(nvidia-smi -i "$gpu" --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits | tr ',' ' ')
if (( used_mib > 1024 || utilization > 10 )); then
  echo "GPU $gpu is busy (${used_mib} MiB, ${utilization}%); choose another." >&2
  exit 2
fi
assets="${RIZZO_ASSETS:-/scratch/$(id -un)/jev-model-performance/rizzo}"
runtime="$assets/llama.cpp/build/bin"
weights="$assets/rizzo-flow-q8.gguf"
rizzo="$root/.cache/third_party/rizzo/.venv/bin/rizzo"
if [[ ! -f "$runtime/libllama.so" || ! -f "$weights" || ! -x "$rizzo" ]]; then
  echo "Run bash inference/rizzo/setup.sh first." >&2
  exit 2
fi
export CUDA_VISIBLE_DEVICES="$gpu"
export RIZZO_LLAMA_DIR="$runtime"
export LD_LIBRARY_PATH="$runtime:/usr/local/cuda-12.8/lib64:${LD_LIBRARY_PATH:-}"
export HF_HOME="${HF_HOME:-/scratch/$(id -un)/jev-model-performance/hf}"
exec "$rizzo" serve --device cuda --model "$weights" --host 127.0.0.1 --port 8017
