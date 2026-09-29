#!/usr/bin/env bash
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd -- "$here/../.." && pwd)"
gpu="${1:-}"
if [[ ! "$gpu" =~ ^[0-9]+$ ]]; then
  echo "Usage: bash inference/nanojev/serve.sh GPU_INDEX" >&2
  exit 2
fi
read -r used_mib utilization < <(nvidia-smi -i "$gpu" --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits | tr ',' ' ')
if (( used_mib > 1024 || utilization > 10 )); then
  echo "GPU $gpu is busy (${used_mib} MiB, ${utilization}%); choose another." >&2
  exit 2
fi
assets="${NANOJEV_ASSETS:-/scratch/$(id -un)/jev-model-performance/nanojev}"
source_dir="$root/.cache/third_party/nanojev"
python="$root/inference/.venv/bin/python"
if [[ ! -f "$assets/checkpoint/best.safetensors" || ! -f "$source_dir/scripts/serve_decisions.py" || ! -x "$python" ]]; then
  echo "Run bash inference/nanojev/setup.sh first." >&2
  exit 2
fi
printf '%s  %s\n' \
  'f68c47d66998231b86b7e91b4ed5e82ae23acf104c8b7cd6d165c3ac7b7ffe1b' \
  "$assets/checkpoint/best.safetensors" | sha256sum --check --status
for port in 8765 8015; do
  if "$python" - "$port" <<'PY'
import socket, sys
with socket.socket() as connection:
    connection.settimeout(1)
    sys.exit(0 if connection.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
  then
    echo "Port $port is already in use; stop the existing server first." >&2
    exit 2
  fi
done
export CUDA_VISIBLE_DEVICES="$gpu"
"$python" "$source_dir/scripts/serve_decisions.py" \
  --checkpoint-dir "$assets/checkpoint" --web-root "$source_dir/web" \
  --host 127.0.0.1 --port 8765 &
native_pid=$!
trap 'kill "$native_pid" 2>/dev/null || true' EXIT
ready=0
for _ in {1..120}; do
  if curl --silent --fail --max-time 2 http://127.0.0.1:8765/api/health > /dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$native_pid" 2>/dev/null; then
    echo "NanoJev native server exited before becoming ready." >&2
    exit 1
  fi
  sleep 1
done
if (( ready != 1 )); then
  echo "NanoJev native server did not become ready within 120 seconds." >&2
  exit 1
fi
"$python" "$here/bridge.py" --upstream http://127.0.0.1:8765 \
  --checkpoint-dir "$assets/checkpoint" --port 8015
