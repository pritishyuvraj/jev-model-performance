#!/usr/bin/env bash
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd -- "$here/../.." && pwd)"
uv="$root/inference/.cache/uv-bootstrap/local/bin/uv"
rizzo_src="$root/.cache/third_party/rizzo"
rizzo_rev="b9ba007ee4d2928bbab5b1d8bfe9009c3696b6de"
llama_rev="161755f29e415e2c33efe906e91843c068efd664"
model_sha="dbec3c89d33984772324e65a8ed56b48e958e301b856cb870a7c1b385d01691a"
assets="${RIZZO_ASSETS:-/scratch/$(id -un)/jev-model-performance/rizzo}"
llama_src="$assets/llama.cpp"
weights="$assets/rizzo-flow-q8.gguf"

if [[ ! -x "$uv" ]]; then
  echo "Run bash inference/setup.sh first to install pinned uv and Python 3.12.14." >&2
  exit 2
fi
if [[ ! -d "$rizzo_src/.git" ]]; then
  mkdir -p "$(dirname "$rizzo_src")"
  git clone --quiet --filter=blob:none --no-checkout https://github.com/Rizzo-AI-Academy/rizzo-flow.git "$rizzo_src"
  git -C "$rizzo_src" fetch --quiet --depth 1 origin "$rizzo_rev"
  git -C "$rizzo_src" checkout --quiet --detach "$rizzo_rev"
fi
if [[ "$(git -C "$rizzo_src" rev-parse HEAD)" != "$rizzo_rev" ]]; then
  echo "Rizzo source is not at pinned commit $rizzo_rev: $rizzo_src" >&2
  exit 2
fi
"$uv" sync --locked --python 3.12.14 --directory "$rizzo_src"

mkdir -p "$assets"
HF_HOME="${HF_HOME:-/scratch/$(id -un)/jev-model-performance/hf}" \
  "$rizzo_src/.venv/bin/rizzo" download --only weights --destination "$weights"
printf '%s  %s\n' "$model_sha" "$weights" | sha256sum --check --status

# This DGX uses Ubuntu 22.04 (glibc 2.35) and driver 570. The upstream b11081
# prebuilt Linux CUDA 13.4 runtime needs newer system libraries/driver, so build
# the identical pinned llama.cpp commit against the local CUDA 12.8 toolkit.
if [[ ! -d "$llama_src/.git" ]]; then
  git clone --quiet --depth 1 --branch b11081 https://github.com/ggml-org/llama.cpp.git "$llama_src"
fi
if [[ "$(git -C "$llama_src" rev-parse HEAD)" != "$llama_rev" ]]; then
  echo "llama.cpp source is not at pinned b11081 commit $llama_rev: $llama_src" >&2
  exit 2
fi
if [[ ! -f "$llama_src/build/bin/libllama.so" || ! -f "$llama_src/build/bin/libggml-cuda.so" ]]; then
  cmake -S "$llama_src" -B "$llama_src/build" \
    -DGGML_CUDA=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.8/bin/nvcc \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=90 \
    -DLLAMA_BUILD_TESTS=OFF -DLLAMA_CURL=OFF
  cmake --build "$llama_src/build" --target llama --config Release -j12
fi
test -f "$llama_src/build/bin/libllama.so"
test -f "$llama_src/build/bin/libggml-cuda.so"
echo "Pinned Rizzo Q8_0 model and CUDA 12.8 runtime ready under $assets"
