#!/usr/bin/env bash
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
weights_revision="43bbca0fb17f424539416ee8eb3de33cfc3dacf3"
weights_dir="${VON_WEIGHTS_DIR:-/scratch/$(id -un)/jev-model-performance/von/$weights_revision}"
gpu="${1:-5}"
port="${2:-8014}"
runtime_dir="$here/.cache/runtime"
checkpoint_link="$runtime_dir/checkpoints/von-1.2"

if [[ ! -x "$here/.venv/bin/von" ]]; then
  echo "Run inference/von/setup.sh first." >&2
  exit 1
fi
for name in config.json model.safetensors option_marker.pt marker_calibration.json tokenizer.json; do
  if [[ ! -f "$weights_dir/$name" ]]; then
    echo "Missing pinned Von weight file: $weights_dir/$name" >&2
    exit 1
  fi
done
gpu_memory="$(nvidia-smi -i "$gpu" --query-gpu=memory.used --format=csv,noheader,nounits | tr -d '[:space:]')"
if [[ ! "$gpu_memory" =~ ^[0-9]+$ ]] || (( gpu_memory > 512 )); then
  echo "GPU $gpu is busy or unavailable ($gpu_memory MiB used)." >&2
  exit 1
fi

mkdir -p "$runtime_dir/checkpoints"
if [[ -e "$checkpoint_link" || -L "$checkpoint_link" ]]; then
  if [[ "$(readlink -f "$checkpoint_link")" != "$(readlink -f "$weights_dir")" ]]; then
    echo "Checkpoint link points to another weight revision: $checkpoint_link" >&2
    exit 1
  fi
else
  ln -s "$weights_dir" "$checkpoint_link"
fi

export CUDA_VISIBLE_DEVICES="$gpu"
export VON_DEVICE=cuda
export VON_ON_OVERFLOW=refuse
export HF_HOME="${HF_HOME:-/scratch/$(id -un)/jev-model-performance/hf}"
cd "$runtime_dir"
exec "$here/.venv/bin/von" serve --host 127.0.0.1 --port "$port" --model von-1.3 --device cuda --no-chains --on-overflow refuse
