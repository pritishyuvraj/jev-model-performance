#!/usr/bin/env bash
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd -- "$here/../.." && pwd)"
source_dir="$root/.cache/third_party/von"
source_url="https://github.com/wfzyx/von.git"
source_revision="a930f9d5709e62388cd4d3bd45675aaaf323b973"
weights_revision="43bbca0fb17f424539416ee8eb3de33cfc3dacf3"
weights_dir="${VON_WEIGHTS_DIR:-/scratch/$(id -un)/jev-model-performance/von/$weights_revision}"
venv="$here/.venv"

uv_bin="$root/inference/.cache/uv-bootstrap/local/bin/uv"
if [[ ! -x "$uv_bin" ]]; then
  uv_bin="$root/inference/.cache/uv-bootstrap/bin/uv"
fi
if [[ ! -x "$uv_bin" ]]; then
  echo "First run inference/setup.sh to install the project-local uv binary." >&2
  exit 1
fi

if [[ ! -d "$source_dir/.git" ]]; then
  mkdir -p "$(dirname "$source_dir")"
  git clone "$source_url" "$source_dir"
  git -C "$source_dir" checkout --detach "$source_revision"
fi
actual_revision="$(git -C "$source_dir" rev-parse HEAD)"
if [[ "$actual_revision" != "$source_revision" ]]; then
  echo "Von source must be $source_revision; found $actual_revision at $source_dir." >&2
  exit 1
fi

"$uv_bin" python install 3.12.14
if [[ ! -x "$venv/bin/python" ]]; then
  "$uv_bin" venv --python 3.12.14 "$venv"
fi
"$uv_bin" pip install --python "$venv/bin/python" -r "$here/requirements.txt"
"$uv_bin" pip install --python "$venv/bin/python" --no-deps -e "$source_dir"

mkdir -p "$weights_dir"
"$venv/bin/python" - "$weights_dir" "$weights_revision" <<'PY'
from pathlib import Path
import sys
from huggingface_hub import snapshot_download
import torch
import transformers
import von

weights_dir, revision = Path(sys.argv[1]), sys.argv[2]
snapshot_download(
    repo_id="wfzyx/von",
    revision=revision,
    local_dir=weights_dir,
    allow_patterns=[
        "config.json", "model.safetensors", "option_marker.pt",
        "marker_calibration.json", "tokenizer.json", "tokenizer_config.json",
        "special_tokens_map.json", "added_tokens.json",
    ],
)
required = ("config.json", "model.safetensors", "option_marker.pt", "marker_calibration.json", "tokenizer.json")
missing = [name for name in required if not (weights_dir / name).is_file()]
if missing:
    raise SystemExit(f"Pinned Von checkpoint missing: {missing}")
if not torch.cuda.is_available():
    raise SystemExit("PyTorch cannot see a CUDA GPU")
print(f"Von {von.__version__}; torch {torch.__version__}; transformers {transformers.__version__}")
print(f"Pinned weights: wfzyx/von@{revision} -> {weights_dir}")
PY
(cd "$weights_dir" && sha256sum --check "$here/weights.sha256.txt")
"$uv_bin" pip freeze --python "$venv/bin/python" > "$here/requirements.resolved.txt"
echo "Von environment ready: $venv"
