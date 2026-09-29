#!/usr/bin/env bash
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd -- "$here/../.." && pwd)"
python="$root/inference/.venv/bin/python"
source_dir="$root/.cache/third_party/nanojev"
code_rev="76fdfc9ecdca45a9bcef17991a07d3041a87685a"
weight_rev="047b927b30882a1138fc504821b82ac145a4b81a"
weight_sha="f68c47d66998231b86b7e91b4ed5e82ae23acf104c8b7cd6d165c3ac7b7ffe1b"
assets="${NANOJEV_ASSETS:-/scratch/$(id -un)/jev-model-performance/nanojev}"
checkpoint="$assets/checkpoint"

if [[ ! -x "$python" ]]; then
  echo "Run bash inference/setup.sh first to create the pinned CUDA environment." >&2
  exit 2
fi
if [[ ! -d "$source_dir/.git" ]]; then
  mkdir -p "$(dirname "$source_dir")"
  git clone --quiet --filter=blob:none --no-checkout https://github.com/TianyuCodings/NanoJev.git "$source_dir"
  git -C "$source_dir" fetch --quiet --depth 1 origin "$code_rev"
  git -C "$source_dir" checkout --quiet --detach "$code_rev"
fi
if [[ "$(git -C "$source_dir" rev-parse HEAD)" != "$code_rev" ]]; then
  echo "NanoJev source is not at pinned commit $code_rev: $source_dir" >&2
  exit 2
fi

mkdir -p "$checkpoint"
"$python" - "$checkpoint" "$weight_rev" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="C-Tianyu/NanoJev",
    revision=sys.argv[2],
    local_dir=sys.argv[1],
    allow_patterns=["best.safetensors", "config.json", "tokenizer/*", "backbone_config/*"],
)
PY
printf '%s  %s\n' "$weight_sha" "$checkpoint/best.safetensors" | sha256sum --check --status
echo "NanoJev source and checkpoint ready: $checkpoint"
