#!/usr/bin/env bash
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
uv_version="0.12.20"
python_version="3.12.14"
source_revision="62076b4f2d365b5879dafcf7f6dd072a1fe76df7"
bootstrap_dir="$here/.cache/uv-bootstrap"
source_dir="$here/.cache/nimble-upstream"
venv_dir="$here/.venv"

if [[ -x "$bootstrap_dir/local/bin/uv" ]]; then
  uv_bin="$bootstrap_dir/local/bin/uv"
else
  uv_bin="$bootstrap_dir/bin/uv"
fi
if [[ ! -x "$uv_bin" || "$("$uv_bin" --version)" != "uv $uv_version"* ]]; then
  "${PYTHON_BOOTSTRAP:-python3}" -m pip install --ignore-installed --no-deps \
    --prefix "$bootstrap_dir" --disable-pip-version-check \
    --index-url https://pypi.org/simple "uv==$uv_version"
  if [[ -x "$bootstrap_dir/local/bin/uv" ]]; then
    uv_bin="$bootstrap_dir/local/bin/uv"
  else
    uv_bin="$bootstrap_dir/bin/uv"
  fi
fi
"$uv_bin" python install "$python_version"
if [[ ! -x "$venv_dir/bin/python" ]]; then
  "$uv_bin" venv --python "$python_version" "$venv_dir"
fi
actual_python="$("$venv_dir/bin/python" -c 'import platform; print(platform.python_version())')"
[[ "$actual_python" == "$python_version" ]] || {
  echo "Existing Nimble virtual environment has Python $actual_python; expected $python_version" >&2
  exit 1
}

"$uv_bin" pip install --python "$venv_dir/bin/python" -r "$here/requirements.txt"
if [[ ! -d "$source_dir/.git" ]]; then
  git clone --filter=blob:none https://github.com/bespokelabsai/nimble.git "$source_dir"
fi
git -C "$source_dir" fetch --depth 1 origin "$source_revision"
git -C "$source_dir" checkout --detach "$source_revision"
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$source_revision" ]] || exit 1

"$venv_dir/bin/python" - <<'PY'
import torch, transformers, peft, accelerate
print("torch", torch.__version__, "transformers", transformers.__version__)
print("peft", peft.__version__, "accelerate", accelerate.__version__)
print("CUDA available:", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise SystemExit("Nimble CUDA environment cannot see a GPU")
PY
"$uv_bin" pip freeze --python "$venv_dir/bin/python" > "$here/requirements.resolved.txt"
echo "Nimble environment ready: $venv_dir"
