# BFCL V4 Hugging Face publication

Public dataset: [pyuvraj/bfcl-v4-jev-routing](https://huggingface.co/datasets/pyuvraj/bfcl-v4-jev-routing).

The frozen release contains **250 test cases**, **seven models' 1,750 saved decisions**, comparison tables, PNG/SVG charts, the offline prompt viewer, selection/review evidence, source pins, and licenses. It contains no model weights. This is a capability-selection pilot; it does not score function arguments or execution and is not an official BFCL V4 leaderboard score.

## Immutable release

| Artifact | Revision or SHA-256 |
| --- | --- |
| [Hugging Face release](https://huggingface.co/datasets/pyuvraj/bfcl-v4-jev-routing/tree/9cd92d8c7789eb390d271adbd7312bbb3e3657cf) | `9cd92d8c7789eb390d271adbd7312bbb3e3657cf` |
| [GitHub evaluation snapshot](https://github.com/pritishyuvraj/jev-model-performance/tree/043cb627cd09a74f3c8eb462e916211de61e0293) | `043cb627cd09a74f3c8eb462e916211de61e0293` |
| BFCL source | `f7cf7359b7ac615a0b294831c5ba2bc95ee4a000` |
| Canonical `frozen_cases.jsonl` | `2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8` |
| Hub projection `test.jsonl` | `7fd9811684920f5708413b3cca8a18e44b52ee79726431592d464ffeaa8643d4` |

The [remote verification record](bfcl_v4_hf_publication.json) records all 56 payload file hashes and sizes. After publication, every payload file was downloaded at the pinned Hub revision and compared byte for byte with the local release. The Hub's `.gitattributes` is an additional repository-generated file.

Loading the public dataset at that revision produced **250 rows and 21 columns**. Every loaded row, including option order and text, matched the local projection. Route kinds are `tool_call` (200) and `no_function` (50). The Dataset Viewer also showed the 250-row test split. The existing V1 Hub repository remained at `fa299523f41ec165bb7557a85951734efae14b82` during verification.

## Load the test split

The loader check used `datasets==4.4.1`, `pyarrow==22.0.0`, and `huggingface_hub==1.33.0` in the existing publication environment. To create a separate environment with those versions:

```sh
python3 -m venv .cache/hf-dataset-venv
.cache/hf-dataset-venv/bin/python -m pip install datasets==4.4.1 pyarrow==22.0.0 huggingface_hub==1.33.0
```

```python
from datasets import load_dataset

cases = load_dataset(
    "pyuvraj/bfcl-v4-jev-routing",
    "default",
    split="test",
    revision="9cd92d8c7789eb390d271adbd7312bbb3e3657cf",
)
assert len(cases) == 250
```

Use only `state`, `instruction`, and `options` when constructing decision inputs. Gold actions, original BFCL references, argument schemas, and review annotations are for offline scoring and inspection. The [dataset card](https://huggingface.co/datasets/pyuvraj/bfcl-v4-jev-routing/blob/9cd92d8c7789eb390d271adbd7312bbb3e3657cf/README.md) describes the flat schema and safe input construction. Canonical native inputs remain in `frozen_cases.jsonl`.

## Rebuild the release package

From this GitHub checkout containing the release builder:

```sh
python3 tools/build_bfcl_v4_hf_release.py
python3 tools/build_bfcl_v4_hf_release.py --check
```

The standard-library builder creates `.cache/hf-bfcl-v4-release/`. It preserves canonical data, per-case logs, charts, and source pins; creates the 21-column Hub projection; rewrites artifact links; and emits `release_manifest.json` with hashes for the other 55 payload files. The manifest excludes its own hash to avoid a recursive checksum. The builder does not authenticate or upload.

The HF dataset clone contains the release artifacts. Rebuilding the package or rerunning inference uses the GitHub code checkout; see [V4 inference commands](../inference/BFCL_V4.md). Upstream BFCL data retains Apache 2.0 attribution; original support code retains MIT attribution. All model authors and sources are listed in the dataset card and `CREDITS.md`.
