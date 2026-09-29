#!/usr/bin/env bash
set -euo pipefail

# User-space bootstrap: the DGX system Python is 3.10, while Kev needs 3.12.
# The system has pip but not ensurepip/python3.10-venv, so do not use venv here.
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bootstrap_dir="$here/.cache/uv-bootstrap"
inference_venv="$here/.venv"
uv_version="0.12.20"
python_version="3.12.14"
bootstrap_python="${PYTHON_BOOTSTRAP:-python3}"

# pip --prefix uses local/bin on Ubuntu and bin on some other platforms.
select_uv_bin() {
  if [[ -x "$bootstrap_dir/local/bin/uv" ]]; then
    uv_bin="$bootstrap_dir/local/bin/uv"
  else
    uv_bin="$bootstrap_dir/bin/uv"
  fi
}
select_uv_bin

uv_is_pinned() {
  [[ -x "$uv_bin" ]] || return 1
  local name version platform
  read -r name version platform <<< "$("$uv_bin" --version)"
  [[ "$name" == "uv" && "$version" == "$uv_version" ]]
}

if ! uv_is_pinned; then
  "$bootstrap_python" -m pip install --ignore-installed --no-deps \
    --prefix "$bootstrap_dir" \
    --disable-pip-version-check --index-url https://pypi.org/simple \
    "uv==$uv_version"
  select_uv_bin
fi
if ! uv_is_pinned; then
  echo "Expected uv $uv_version at $uv_bin; found $("$uv_bin" --version)." >&2
  exit 1
fi

"$uv_bin" python install "$python_version"
if [[ ! -x "$inference_venv/bin/python" ]]; then
  "$uv_bin" venv --python "$python_version" "$inference_venv"
fi
actual_python="$("$inference_venv/bin/python" -c 'import platform; print(platform.python_version())')"
if [[ "$actual_python" != "$python_version" ]]; then
  echo "Expected Python $python_version in $inference_venv; found $actual_python." >&2
  echo "Move the existing environment aside, then rerun this script." >&2
  exit 1
fi

requirements_file="$here/requirements.resolved.txt"
if [[ ! -s "$requirements_file" ]]; then
  requirements_file="$here/requirements.txt"
fi
echo "Installing inference packages from $requirements_file"
"$uv_bin" pip install --python "$inference_venv/bin/python" -r "$requirements_file"
"$inference_venv/bin/python" - <<'PY'
import importlib.metadata as md
import torch

for package in ("laya", "kev", "torch", "transformers", "numpy", "peft"):
    print(f"{package} {md.version(package)}")
print(f"CUDA available: {torch.cuda.is_available()} ({torch.cuda.device_count()} visible GPUs)")
if not torch.cuda.is_available():
    raise SystemExit("PyTorch cannot see a CUDA GPU; check the driver and CUDA wheel.")
PY

# Keep the exact resolved transitive environment beside the install. Commit a
# verified copy if the evaluation is later used as a reproducible comparison.
"$uv_bin" pip freeze --python "$inference_venv/bin/python" > "$here/requirements.resolved.txt"
echo "Inference environment ready: $inference_venv"
echo "Resolved packages: $here/requirements.resolved.txt"
