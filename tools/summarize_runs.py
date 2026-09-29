#!/usr/bin/env python3
"""Rebuild the seven-model BFCL V1 comparison from frozen per-case logs.

No inference is performed. Percentile 95 uses linear interpolation at
0.95 * (n - 1) on sorted observed wall-clock response times.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NO_FUNCTION = frozenset({"no_tool", "clarify", "cannot_answer"})
MODELS = (
    ("laya", "Laya typed-decisions", 421_000_000, "~421M"),
    ("kev", "Kev-0.8B", 800_000_000, "~0.8B"),
    ("nimble", "Bespoke Nimble 9B", 9_000_000_000, "~9B"),
    ("semif", "SemIf / frozen Qwen3.5-4B", 4_000_000_000, "~4B"),
    ("rizzo", "Rizzo Flow 4B Q8_0", 4_000_000_000, "~4B"),
    ("von", "Von 1.3, chains off", 395_000_000, "~395M"),
    ("nanojev", "NanoJev unified-games-v1", 600_000_000, "~0.6B"),
)
FIELDS = (
    "model_id", "model", "parameters_approx", "parameter_label",
    "cases", "call_cases", "exact_right_tool_correct", "exact_right_tool_accuracy_pct",
    "tool_selection_correct", "tool_selection_accuracy_pct",
    "mean_wall_latency_ms", "median_wall_latency_ms", "p95_wall_latency_ms",
    "mean_correct_route_probability_pct", "cases_sha256", "log_sha256",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def validate_run(root: Path, model_id: str, cases: dict[str, dict], case_hash: str) -> tuple[list[dict], str]:
    log_path = root / f"results/bfcl_v1_{model_id}.jsonl"
    meta = json.loads((root / f"results/bfcl_v1_{model_id}.meta.json").read_text(encoding="utf-8"))
    rows = read_jsonl(log_path)
    if meta["run"]["cases_sha256"] != case_hash:
        raise ValueError(f"{model_id}: source case hash differs")
    if len(rows) != len(cases) or {row["case_id"] for row in rows} != set(cases):
        raise ValueError(f"{model_id}: expected exactly one row per frozen case")
    for row in rows:
        case = cases[row["case_id"]]
        name = f"{model_id}/{row['case_id']}"
        if row["run_id"] != meta["run_id"] or row["gold_action"] != case["gold_next_action_ids"][0]:
            raise ValueError(f"{name}: run or gold label differs from source")
        if row["status"] != "ok":
            raise ValueError(f"{name}: incomplete response; comparison requires full runs")
        if row["predicted_action"] not in case["jev"]["option_ids"]:
            raise ValueError(f"{name}: predicted action was not offered")
        probs = row["probabilities"]
        if set(probs) != set(case["jev"]["option_ids"]):
            raise ValueError(f"{name}: incomplete option probabilities")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1 for value in probs.values()):
            raise ValueError(f"{name}: invalid option probability")
        if abs(sum(probs.values()) - 1) > 0.02:
            raise ValueError(f"{name}: option probabilities do not sum to one")
        elapsed = row["wall_latency_ms"]
        if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError(f"{name}: invalid wall latency")
    return rows, sha256(log_path)


def build_rows(root: Path) -> list[dict]:
    case_path = root / "data/bfcl_v1/cases.jsonl"
    case_hash = sha256(case_path)
    manifest = json.loads((root / "data/bfcl_v1/manifest.json").read_text(encoding="utf-8"))
    source_cases = read_jsonl(case_path)
    cases = {case["id"]: case for case in source_cases}
    if (manifest["cases_sha256"] != case_hash or len(cases) != len(source_cases)
            or manifest["selected_count"] != len(cases) or len(cases) != 250):
        raise ValueError("Frozen cases or manifest differ from the expected 250-case set")
    if sum(case["gold_next_action_ids"][0] != "no_tool" for case in cases.values()) != 200:
        raise ValueError("Expected 200 function-call cases and 50 no-call cases")

    output = []
    for model_id, name, parameters, label in MODELS:
        rows, log_hash = validate_run(root, model_id, cases, case_hash)
        call_rows = [row for row in rows if row["gold_action"] != "no_tool"]
        exact_call = sum(row["predicted_action"] == row["gold_action"] for row in call_rows)
        selection = sum(
            row["predicted_action"] == row["gold_action"]
            or (row["gold_action"] == "no_tool" and row["predicted_action"] in NO_FUNCTION)
            for row in rows
        )
        correct_route_mass = [
            (sum(row["probabilities"][option] for option in NO_FUNCTION)
             if row["gold_action"] == "no_tool"
             else row["probabilities"][row["gold_action"]])
            for row in rows
        ]
        elapsed = [float(row["wall_latency_ms"]) for row in rows]
        output.append({
            "model_id": model_id,
            "model": name,
            "parameters_approx": parameters,
            "parameter_label": label,
            "cases": len(rows),
            "call_cases": len(call_rows),
            "exact_right_tool_correct": exact_call,
            "exact_right_tool_accuracy_pct": round(100 * exact_call / len(call_rows), 3),
            "tool_selection_correct": selection,
            "tool_selection_accuracy_pct": round(100 * selection / len(rows), 3),
            "mean_wall_latency_ms": round(statistics.fmean(elapsed), 3),
            "median_wall_latency_ms": round(statistics.median(elapsed), 3),
            "p95_wall_latency_ms": round(percentile(elapsed, 0.95), 3),
            "mean_correct_route_probability_pct": round(100 * statistics.fmean(correct_route_mass), 3),
            "cases_sha256": case_hash,
            "log_sha256": log_hash,
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Benchmark repository root")
    parser.add_argument("--output", type=Path, default=Path("results/bfcl_v1_comparison.csv"))
    parser.add_argument("--check", action="store_true", help="Fail if the committed CSV is stale")
    args = parser.parse_args()
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(build_rows(args.root))
    output = args.output if args.output.is_absolute() else args.root / args.output
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != buffer.getvalue():
            raise SystemExit(f"Stale comparison file: {output}")
        print(f"Up to date: {output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(buffer.getvalue(), encoding="utf-8")
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
