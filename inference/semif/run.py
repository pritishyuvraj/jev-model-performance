#!/usr/bin/env python3
"""Run the authoritative SemIf direct-logit scorer on frozen BFCL routing cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

from evaluate import (  # noqa: E402
    dataset_run_fields, eval_schema, load_cases, read_predictions, sha256, stratum, summarize, utc_now, write_json_atomic,
)
from semif_phase1.core import load_causal_model  # noqa: E402
from semif_phase1.direct import score  # noqa: E402


SOURCE_REVISION = "23cf1f39fc9534fe81437200959b6dfc7106e45a"
MODEL_ID = "Qwen/Qwen3.5-4B"
MODEL_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
ADAPTER = "semif-direct-bfcl-choice-v1"


def to_semif_input(case: dict) -> dict:
    """Build the entire native model input from the Jev-facing state and offers."""
    choice = case["jev"]["laya"]["questions"]["next"]
    return {
        "id": case["id"],
        "state": case["jev"]["laya"]["state"],
        "question": choice["instructions"],
        # SemIf renders only descriptions in its native prompt. Include the IDs
        # that other System One servers see as their Choice criterion keys.
        "options": [
            {"id": option_id, "description": f"{option_id}: {description}"}
            for option_id, description in choice["criteria"].items()
        ],
    }


def validated_selection(native: dict, option_ids: list[str]) -> tuple[str, dict[str, float], dict[str, float]]:
    if native.get("option_ids") != option_ids:
        raise ValueError("SemIf changed offered option order or IDs")
    raw_probabilities = native.get("probabilities")
    raw_logits = native.get("option_logits")
    if not isinstance(raw_probabilities, list) or len(raw_probabilities) != len(option_ids):
        raise ValueError("SemIf returned incomplete probabilities")
    if not isinstance(raw_logits, list) or len(raw_logits) != len(option_ids):
        raise ValueError("SemIf returned incomplete logits")
    probabilities = {}
    logits = {}
    for option_id, probability, logit in zip(option_ids, raw_probabilities, raw_logits):
        if (isinstance(probability, bool) or not isinstance(probability, (int, float))
                or not math.isfinite(probability) or not 0 <= probability <= 1):
            raise ValueError(f"Invalid probability for {option_id}")
        if isinstance(logit, bool) or not isinstance(logit, (int, float)) or not math.isfinite(logit):
            raise ValueError(f"Invalid logit for {option_id}")
        probabilities[option_id] = float(probability)
        logits[option_id] = float(logit)
    if abs(sum(probabilities.values()) - 1.0) > 0.02:
        raise ValueError("SemIf probabilities do not sum to one")
    selected = max(option_ids, key=probabilities.__getitem__)
    return selected, probabilities, logits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "data/bfcl_v1/cases.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "results/bfcl_v1_semif.jsonl")
    parser.add_argument("--limit", type=int, help="Score at most this many pending cases")
    parser.add_argument("--rerun-errors", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.max_tokens < 1:
        parser.error("--max-tokens must be positive")

    cases_path = args.cases.resolve()
    output = args.output.resolve()
    meta_path = output.with_suffix(".meta.json")
    summary_path = output.with_suffix(".summary.json")
    cases, source_manifest = load_cases(cases_path)
    run = {
        "provider": "semif",
        "requested_model": MODEL_ID,
        "declared_model_revision": MODEL_REVISION,
        "upstream_repo": "https://github.com/TheoLeeCJ/SemIf-OpenJev",
        "upstream_revision": SOURCE_REVISION,
        "mode": "direct",
        "backend": "torch",
        "dtype": "bfloat16",
        "device": "cuda",
        "max_input_tokens": args.max_tokens,
        "input_adapter": ADAPTER,
        "input_adapter_sha256": sha256(Path(__file__)),
        "cases_path": str(cases_path),
        "cases_sha256": sha256(cases_path),
        "source_tag": source_manifest.get("source_tag") if source_manifest else None,
        "source_commit": source_manifest.get("source_commit") if source_manifest else None,
        "selection_review_sha256": (source_manifest.get("selection_review") or {}).get("sha256") if source_manifest else None,
        **dataset_run_fields(source_manifest),
    }
    run_id = hashlib.sha256(json.dumps(run, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if output.exists() and not meta_path.exists():
        raise ValueError(f"{output} exists without metadata")
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if metadata.get("run_id") != run_id or metadata.get("run") != run:
            raise ValueError(f"{meta_path} belongs to a different run")
    else:
        metadata = {
            "schema": eval_schema("run", run),
            "created_at_utc": utc_now(),
            "run_id": run_id,
            "run": run,
            "predictions_file": str(output),
        }
        write_json_atomic(meta_path, metadata)

    latest, attempts = read_predictions(output, run_id, {case["id"] for case in cases})
    pending = [case for case in cases if case["id"] not in latest or (
        args.rerun_errors and latest[case["id"]]["status"] == "error"
    )]
    if args.limit is not None:
        pending = pending[:args.limit]

    if pending:
        model, tokenizer, model_metadata = load_causal_model(
            MODEL_ID, MODEL_REVISION, device="cuda", dtype="bfloat16"
        )
        if model_metadata.get("device") != "cuda:0":
            raise RuntimeError(f"Expected one visible CUDA GPU: {model_metadata}")
        if metadata.get("native_model_identity") not in (None, model_metadata):
            raise RuntimeError("Runtime model identity differs from the original run")
        metadata["native_model_identity"] = model_metadata
        write_json_atomic(meta_path, metadata)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as stream:
            for index, case in enumerate(pending, 1):
                case_id = case["id"]
                gold = case["gold_next_action_ids"][0]
                common = {
                    "run_id": run_id,
                    "case_id": case_id,
                    "category": case["category"],
                    "stratum": stratum(case),
                    "gold_action": gold,
                    "attempt": attempts[case_id] + 1,
                    "completed_at_utc": utc_now(),
                }
                started = time.perf_counter()
                try:
                    native_input = to_semif_input(case)
                    native = score(model, tokenizer, native_input, model_metadata, args.max_tokens)
                    selected, probabilities, logits = validated_selection(
                        native, case["jev"]["option_ids"]
                    )
                    row = {
                        **common,
                        "status": "ok",
                        "predicted_action": selected,
                        "correct": selected == gold,
                        "probabilities": probabilities,
                        "option_logits": logits,
                        "response_model": MODEL_ID,
                        "input_tokens": native["input_tokens"],
                        "forward_latency_ms": round(native["forward_seconds"] * 1000, 2),
                        "wall_latency_ms": round((time.perf_counter() - started) * 1000, 2),
                        "prompt_sha256": native["prompt_sha256"],
                        "prompt_version": native["prompt_version"],
                        "readout": native["readout"],
                        "probability_status": native["probability_status"],
                    }
                except Exception as error:
                    row = {
                        **common,
                        "status": "error",
                        "predicted_action": None,
                        "correct": False,
                        "error": {"type": type(error).__name__, "message": str(error)[:1000]},
                        "wall_latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                latest[case_id] = row
                attempts[case_id] += 1
                if index % 10 == 0 or index == len(pending):
                    print(f"[{index}/{len(pending)}] {case_id}: {row['predicted_action'] or row['status']}", flush=True)

    summary = summarize(cases, latest, run)
    write_json_atomic(summary_path, summary)
    print(json.dumps({"completed": summary["completed_count"], "overall": summary["overall"]}, indent=2))
    return 2 if summary["is_complete"] and summary["overall"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
