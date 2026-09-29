#!/usr/bin/env python3
"""Run native Bespoke-Nimble-9B candidate scoring on the pinned BFCL choices."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_REVISION = "62076b4f2d365b5879dafcf7f6dd072a1fe76df7"
MODEL_ID = "bespokelabs/Bespoke-Nimble-9B"
MODEL_REVISION = "bd792f44ec8e265be861bfcdf4e05967ffe0e858"
DEFAULT_HF_HOME = Path("/scratch") / os.environ.get("USER", "pritish") / "jev-model-performance" / "hf"
DEFAULT_MERGED = Path("/scratch") / os.environ.get("USER", "pritish") / "jev-model-performance" / "nimble-9b-merged-bd792f44"

# The existing evaluator owns case validation and the shared scoring definition.
sys.path.insert(0, str(HERE.parent))
from evaluate import (load_cases, read_predictions, sha256, stratum, summarize,
                      utc_now, write_json_atomic)  # noqa: E402


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_model(merged_dir: Path) -> tuple[Path, dict]:
    """Download pinned adapter/base, merge safely on CPU, and retain identity."""
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    from peft import PeftModel
    import torch

    snapshot = Path(snapshot_download(repo_id=MODEL_ID, revision=MODEL_REVISION))
    contract = json.loads((snapshot / "schema_config.json").read_text())
    adapter_digest = file_sha256(snapshot / "adapter_model.safetensors")
    identity = {
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "base_model": contract["model"],
        "base_revision": contract["revision"],
        "adapter_sha256": adapter_digest,
        "source_revision": SOURCE_REVISION,
    }
    ready_file = merged_dir / "READY.json"
    if ready_file.exists():
        ready = json.loads(ready_file.read_text())
        has_weights = (merged_dir / "model.safetensors").is_file() or (merged_dir / "model.safetensors.index.json").is_file()
        if all(ready.get(key) == value for key, value in identity.items()) and has_weights:
            return merged_dir, identity
        raise RuntimeError(f"Existing merged model identity does not match: {merged_dir}")
    if merged_dir.exists():
        raise RuntimeError(f"Incomplete merged model directory exists: {merged_dir}")
    merged_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = merged_dir.with_name(merged_dir.name + f".tmp-{os.getpid()}")
    temporary.mkdir()
    print(f"Merging {MODEL_ID}@{MODEL_REVISION} on CPU", file=sys.stderr, flush=True)
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        contract["model"], revision=contract["revision"],
        dtype=torch.bfloat16, device_map="cpu",
    )
    model = PeftModel.from_pretrained(base, snapshot)
    merged = model.merge_and_unload(safe_merge=True)
    merged.save_pretrained(temporary, safe_serialization=True)
    (temporary / "schema_config.json").write_text(json.dumps(contract, indent=2) + "\n")
    AutoTokenizer.from_pretrained(snapshot).save_pretrained(temporary)
    (temporary / "READY.json").write_text(json.dumps(identity, indent=2) + "\n")
    temporary.rename(merged_dir)
    return merged_dir, identity


def canonical_schema(case: dict) -> dict:
    question = case["jev"]["laya"]["questions"]["next"]
    return {"next": {
        "type": "enum",
        "choices": list(question["criteria"]),
        "description": question["instructions"],
        "choice_descriptions": dict(question["criteria"]),
    }}


def predict_case(case: dict, scorer, *, run_id: str, attempt: int) -> dict:
    state = case["jev"]["laya"]["state"]
    schema = canonical_schema(case)
    # Only state and option schema reach the model; source and gold stay in this runner.
    request = {"state": state, "schema": schema}
    request_digest = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    common = {
        "run_id": run_id,
        "case_id": case["id"],
        "category": case["category"],
        "stratum": stratum(case),
        "gold_action": case["gold_next_action_ids"][0],
        "attempt": attempt,
        "completed_at_utc": utc_now(),
        "request_sha256": request_digest,
    }
    started = time.perf_counter()
    try:
        result = scorer.score(state, schema)
        choice = result["output"]["next"]
        field = result["fields"]["next"]
        probabilities = field["scores"]
        option_ids = case["jev"]["option_ids"]
        if choice not in option_ids or set(probabilities) != set(option_ids):
            raise ValueError(f"Unrecognized choice or incomplete option scores: {choice!r}")
        if abs(sum(probabilities.values()) - 1) > 0.02:
            raise ValueError("Option scores do not sum to one")
        return {
            **common, "status": "ok", "predicted_action": choice,
            "correct": choice == common["gold_action"], "probabilities": probabilities,
            "option_logits": field["logits"],
            "prompt_token_sha256": field["prompt_token_sha256"],
            "prompt_token_count": field["prompt_token_count"],
            "response_model": result["model"],
            "input_tokens": field["prompt_token_count"],
            "server_latency_ms": round(result["metrics"]["total_seconds"] * 1000, 2),
            "wall_latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "http_retries": 0,
        }
    except Exception as error:
        return {
            **common, "status": "error", "predicted_action": None,
            "correct": False,
            "error": {"type": type(error).__name__, "message": str(error)[:1000]},
            "wall_latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "http_retries": 0,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "data/bfcl_v1/cases.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "results/bfcl_v1_nimble.jsonl")
    parser.add_argument("--merged-dir", type=Path, default=DEFAULT_MERGED)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rerun-errors", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    if "HF_HOME" not in os.environ:
        os.environ["HF_HOME"] = str(DEFAULT_HF_HOME)
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    source_dir = Path(os.environ.get("NIMBLE_SOURCE", HERE / ".cache/nimble-upstream"))
    if not (source_dir / "nimble/scoring/cuda_scorer.py").is_file():
        raise RuntimeError(f"Run setup.sh first; Nimble source missing at {source_dir}")
    import subprocess
    revision = subprocess.check_output(["git", "-C", str(source_dir), "rev-parse", "HEAD"], text=True).strip()
    if revision != SOURCE_REVISION:
        raise RuntimeError(f"Wrong Nimble source revision {revision}; expected {SOURCE_REVISION}")
    sys.path.insert(0, str(source_dir))

    merged_dir, identity = prepare_model(args.merged_dir.resolve())
    if args.prepare_only:
        print(json.dumps({"merged_dir": str(merged_dir), "identity": identity}, indent=2))
        return 0

    import torch
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("Set CUDA_VISIBLE_DEVICES to exactly one free GPU before scoring")
    from nimble.scoring.cuda_scorer import CudaCandidateScorer
    scorer = CudaCandidateScorer(
        model_path=str(merged_dir), model_id=MODEL_ID, revision=MODEL_REVISION,
        max_input_tokens=8192, dtype="bfloat16",
    )
    cases_path = args.cases.resolve()
    cases, manifest = load_cases(cases_path)
    output = args.output.resolve()
    run_config = {
        "provider": "nimble", "requested_model": MODEL_ID,
        "declared_model_revision": MODEL_REVISION,
        "endpoint": "native-cuda", "adapter": "nimble-cuda-enum-v1",
        "source_revision": SOURCE_REVISION,
        "base_model": identity["base_model"],
        "base_revision": identity["base_revision"],
        "adapter_sha256": identity["adapter_sha256"],
        "runtime": scorer.runtime,
        "temperature": scorer.temperature,
        "cases_path": str(cases_path), "cases_sha256": sha256(cases_path),
        "source_tag": manifest.get("source_tag") if manifest else None,
        "source_commit": manifest.get("source_commit") if manifest else None,
        "selection_review_sha256": (manifest.get("selection_review") or {}).get("sha256") if manifest else None,
    }
    run_id = hashlib.sha256(json.dumps(run_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    meta_path = output.with_suffix(".meta.json")
    summary_path = output.with_suffix(".summary.json")
    if output.exists() and not meta_path.exists():
        raise RuntimeError(f"Ambiguous existing predictions without {meta_path}")
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text())
        if metadata.get("run_id") != run_id or metadata.get("run") != run_config:
            raise RuntimeError(f"Run identity differs from {meta_path}")
    else:
        write_json_atomic(meta_path, {
            "schema": "bfcl-v1-jev-eval-run/v1", "created_at_utc": utc_now(),
            "run_id": run_id, "run": run_config,
            "server_probe": {"native_cuda_scorer": scorer.runtime},
            "server_identity": identity,
            "predictions_file": str(output),
        })
    latest, attempts = read_predictions(output, run_id, {case["id"] for case in cases})
    pending = [case for case in cases if case["id"] not in latest or
               (args.rerun_errors and latest[case["id"]]["status"] == "error")]
    if args.limit is not None:
        pending = pending[:args.limit]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as stream:
        for index, case in enumerate(pending, 1):
            row = predict_case(case, scorer, run_id=run_id, attempt=attempts[case["id"]] + 1)
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            latest[case["id"]] = row
            print(f"[{index}/{len(pending)}] {case['id']}: {row['predicted_action'] or row['status']}", file=sys.stderr, flush=True)
    summary = summarize(cases, latest, run_config)
    write_json_atomic(summary_path, summary)
    print(json.dumps({"summary": str(summary_path), "overall": summary["overall"]}, indent=2))
    return 2 if summary["is_complete"] and summary["overall"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
