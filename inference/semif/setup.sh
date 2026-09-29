#!/usr/bin/env bash
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd -- "$here/../.." && pwd)"
source_dir="$root/.cache/third_party/semif"
source_url="https://github.com/TheoLeeCJ/SemIf-OpenJev.git"
source_revision="23cf1f39fc9534fe81437200959b6dfc7106e45a"
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
  echo "SemIf source must be $source_revision; found $actual_revision at $source_dir." >&2
  exit 1
fi

"$uv_bin" python install 3.12.14
if [[ ! -x "$venv/bin/python" ]]; then
  "$uv_bin" venv --python 3.12.14 "$venv"
fi
"$uv_bin" pip install --python "$venv/bin/python" -r "$here/requirements.txt"
"$uv_bin" pip install --python "$venv/bin/python" --no-deps -e "$source_dir"
"$venv/bin/python" - <<'PY'
import torch, transformers, semif_phase1
assert torch.version.cuda == "12.8", torch.version.cuda
assert torch.cuda.is_available(), "CUDA is unavailable"
print(f"torch={torch.__version__} cuda={torch.version.cuda} transformers={transformers.__version__}")
PY
"$uv_bin" pip freeze --python "$venv/bin/python" > "$here/requirements.resolved.txt"
echo "SemIf environment ready: $venv"
