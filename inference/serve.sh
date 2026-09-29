#!/usr/bin/env bash
set -euo pipefail

# Run one pinned native System One server on one currently idle NVIDIA GPU.
# Usage: bash inference/serve.sh laya 0   (or: kev 1)
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
venv="$here/.venv"
provider="${1:-}"
gpu_index="${2:-}"

if [[ "$provider" != "laya" && "$provider" != "kev" ]]; then
  echo "Usage: $0 {laya|kev} GPU_INDEX" >&2
  exit 2
fi
if [[ ! "$gpu_index" =~ ^[0-9]+$ ]]; then
  echo "GPU_INDEX must be a nonnegative integer." >&2
  exit 2
fi
if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing $venv; run bash inference/setup.sh first." >&2
  exit 2
fi

if ! gpu_state="$(nvidia-smi -i "$gpu_index" --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits)"; then
  echo "Cannot inspect GPU $gpu_index." >&2
  exit 2
fi
read -r used_mib utilization < <(printf '%s\n' "$gpu_state" | tr ',' ' ')
if (( used_mib > 1024 || utilization > 10 )); then
  echo "GPU $gpu_index is busy (${used_mib} MiB, ${utilization}%); choose another GPU." >&2
  exit 2
fi

export CUDA_VISIBLE_DEVICES="$gpu_index"
export PYTHONNOUSERSITE=1
export TOKENIZERS_PARALLELISM=false
export HF_HOME="${HF_HOME:-/scratch/$(id -un)/jev-model-performance/hf}"
mkdir -p "$HF_HOME"
echo "Starting $provider on GPU $gpu_index; HF cache: $HF_HOME" >&2

if [[ "$provider" == "laya" ]]; then
  export LAYA_DEVICE=cuda
  export LAYA_HOST=127.0.0.1
  export LAYA_PORT=8007
  export LAYA_MODELS=typed-decisions
  export LAYA_PRELOAD=1
  export LAYA_REVISION=reviewed
  export LAYA_CUDA_AMP=fp16
  export LAYA_SHA256_DIGESTS='{"typed-decisions":{"model.safetensors":"4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e"}}'
  exec "$venv/bin/laya-serve"
fi

export KEV_DTYPE=fp32
export KEV_FUSED=0
export KEV_CUDA_GRAPHS=0
kev_run="jaredpalmer/kev-0.8b@9a45d25eb2ab761841196625383fa1dff0e56c1e"
exec "$venv/bin/python" -m kev.serve --run "$kev_run" --host 127.0.0.1 --port 8008
