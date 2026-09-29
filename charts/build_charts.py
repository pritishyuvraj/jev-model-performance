#!/usr/bin/env python3
"""Rebuild static BFCL routing charts from the committed per-case JSONL logs."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
CASES = ROOT / "data" / "bfcl_v1" / "cases.jsonl"
NO_FUNCTION = frozenset({"no_tool", "clarify", "cannot_answer"})
EXPECTED_CASES_SHA256 = "68868277c9f10c56706a5d8a1a79a78720582dd731fef414a4b7c4ae366cc602"

# Rounded published model/backbone sizes for the checkpoints used in these logs.
# See charts/README.md for model-card links and interpretation.
MODELS = (
    ("laya", "Laya", 0.421, "#0f766e"),
    ("kev", "Kev", 0.8, "#0d6efd"),
    ("nimble", "Nimble", 9.0, "#7c3aed"),
    ("semif", "SemIf", 4.0, "#b45309"),
    ("rizzo", "Rizzo Flow", 4.0, "#e11d48"),
    ("von", "Von", 0.395, "#2563eb"),
    ("nanojev", "NanoJev", 0.6, "#6b7280"),
)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def percentile(values: list[float], fraction: float) -> float:
    """Linear interpolation between sorted observations, as in numpy.percentile."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    left = math.floor(position)
    right = math.ceil(position)
    return ordered[left] + (ordered[right] - ordered[left]) * (position - left)


def compute_metrics() -> list[dict]:
    case_hash = hashlib.sha256(CASES.read_bytes()).hexdigest()
    if case_hash != EXPECTED_CASES_SHA256:
        raise ValueError(f"Unexpected BFCL case file SHA-256: {case_hash}")
    cases = read_jsonl(CASES)
    case_ids = {case["id"] for case in cases}
    if len(cases) != 250 or len(case_ids) != 250:
        raise ValueError("Expected 250 unique source cases")

    metrics = []
    for slug, label, params_billion, color in MODELS:
        rows = read_jsonl(RESULTS / f"bfcl_v1_{slug}.jsonl")
        summary = json.loads((RESULTS / f"bfcl_v1_{slug}.summary.json").read_text(encoding="utf-8"))
        metadata = json.loads((RESULTS / f"bfcl_v1_{slug}.meta.json").read_text(encoding="utf-8"))
        row_ids = [row["case_id"] for row in rows]
        if len(rows) != 250 or len(set(row_ids)) != 250 or set(row_ids) != case_ids:
            raise ValueError(f"{slug}: cases do not match the selected BFCL set")
        if metadata["run"]["cases_sha256"] != case_hash:
            raise ValueError(f"{slug}: metadata cites a different case file")
        if any(row["status"] != "ok" for row in rows):
            raise ValueError(f"{slug}: this chart requires 250 completed responses")

        call_rows = [row for row in rows if row["gold_action"] not in NO_FUNCTION]
        no_call_rows = [row for row in rows if row["gold_action"] in NO_FUNCTION]
        if len(call_rows) != 200 or len(no_call_rows) != 50:
            raise ValueError(f"{slug}: expected 200 call and 50 no-call cases")
        exact_call_correct = sum(row["predicted_action"] == row["gold_action"] for row in call_rows)
        no_call_correct = sum(row["predicted_action"] in NO_FUNCTION for row in no_call_rows)
        all_selection_correct = exact_call_correct + no_call_correct
        if all_selection_correct != summary["overall"]["tool_selection_correct"]:
            raise ValueError(f"{slug}: recomputed selection score disagrees with summary")

        for row in call_rows:
            if row["gold_action"] not in row["probabilities"]:
                raise ValueError(f"{slug}: missing gold function probability in {row['case_id']}")
        latencies = [float(row["wall_latency_ms"]) for row in rows]
        gold_function_probabilities = [float(row["probabilities"][row["gold_action"]]) for row in call_rows]
        route_probabilities = [
            (float(row["probabilities"][row["gold_action"]])
             if row["gold_action"] not in NO_FUNCTION
             else sum(float(row["probabilities"].get(option, 0.0)) for option in NO_FUNCTION))
            for row in rows
        ]
        metrics.append({
            "model": label,
            "slug": slug,
            "parameters_billion_approx": params_billion,
            "color": color,
            "call_cases": 200,
            "correct_functions": exact_call_correct,
            "exact_right_tool_accuracy": exact_call_correct / 200,
            "no_call_cases": 50,
            "all_case_route_accuracy": all_selection_correct / 250,
            "mean_gold_function_probability_call_cases": statistics.mean(gold_function_probabilities),
            "mean_gold_route_probability_all_cases": statistics.mean(route_probabilities),
            "mean_wall_latency_ms": statistics.mean(latencies),
            "median_wall_latency_ms": statistics.median(latencies),
            "p95_wall_latency_ms": percentile(latencies, 0.95),
            "run_id": metadata["run_id"],
        })
    return metrics


def format_plot() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelcolor": "#293241",
        "text.color": "#293241",
        "xtick.color": "#526172",
        "ytick.color": "#526172",
        "axes.edgecolor": "#b9c2cf",
        "grid.color": "#dce2e9",
        "grid.alpha": 0.8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "svg.fonttype": "none",
        "svg.hashsalt": "bfcl-v1-jev-routing-charts",
    })


def save(fig: plt.Figure, basename: str) -> None:
    svg = OUT / f"{basename}.svg"
    fig.savefig(svg, bbox_inches="tight", metadata={"Date": None})
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fig.savefig(OUT / f"{basename}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def point_label(ax: plt.Axes, x: float, y: float, name: str, dx: int, dy: int) -> None:
    ax.annotate(name, (x, y), xytext=(dx, dy), textcoords="offset points",
                ha="left" if dx >= 0 else "right", va="center", fontsize=10,
                fontweight="semibold", color="#263445")


def chart_size_accuracy(metrics: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    fig.subplots_adjust(left=0.13, right=0.96, top=0.87, bottom=0.20)
    offsets = {
        "Laya": (10, 9), "Kev": (10, 10), "Nimble": (-10, -13),
        "SemIf": (10, 9), "Rizzo Flow": (10, -9),
        "Von": (10, -10), "NanoJev": (10, 0),
    }
    for model in metrics:
        x = model["parameters_billion_approx"]
        y = 100 * model["exact_right_tool_accuracy"]
        ax.scatter(x, y, s=125, color=model["color"], edgecolor="white", linewidth=1.6, zorder=3)
        point_label(ax, x, y, model["model"], *offsets[model["model"]])
    ax.set_xscale("log")
    ax.set_xlim(0.30, 15)
    ax.set_ylim(0, 106)
    ax.set_xticks([0.4, 0.6, 0.8, 1, 2, 4, 9])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    ax.set_yticks([0, 20, 40, 60, 80, 90, 100])
    ax.grid(axis="y")
    ax.set_xlabel("Approximate checkpoint parameters (billions; log scale)", labelpad=10)
    ax.set_ylabel("Exact right function on 200 call cases (%)", labelpad=10)
    ax.set_title("Model size and right-tool accuracy", loc="left", fontsize=16, fontweight="bold", pad=17)
    fig.text(0.5, 0.045, "BFCL V1 Jev routing pilot · rounded published sizes · no argument scoring",
             ha="center", fontsize=9, color="#526172")
    save(fig, "size_vs_right_tool_accuracy")


def chart_latency_accuracy(metrics: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    fig.subplots_adjust(left=0.13, right=0.96, top=0.87, bottom=0.20)
    offsets = {
        "Laya": (9, 8), "Kev": (-9, -13), "Nimble": (9, 10),
        "SemIf": (9, -10), "Rizzo Flow": (9, -10),
        "Von": (9, 8), "NanoJev": (9, 0),
    }
    for model in metrics:
        x = model["mean_wall_latency_ms"]
        y = 100 * model["exact_right_tool_accuracy"]
        ax.scatter(x, y, s=125, color=model["color"], edgecolor="white", linewidth=1.6, zorder=3)
        point_label(ax, x, y, model["model"], *offsets[model["model"]])
    ax.set_xlim(15, 88)
    ax.set_ylim(0, 106)
    ax.set_xticks([20, 30, 40, 50, 60, 70, 80])
    ax.set_yticks([0, 20, 40, 60, 80, 90, 100])
    ax.grid(axis="both")
    ax.set_xlabel("Mean observed wall latency per case (ms)", labelpad=10)
    ax.set_ylabel("Exact right function on 200 call cases (%)", labelpad=10)
    ax.set_title("Observed latency and right-tool accuracy", loc="left", fontsize=16, fontweight="bold", pad=17)
    fig.text(0.5, 0.045, "Sequential GPU runs; different runtimes and prompts. Means include first-request warmup.",
             ha="center", fontsize=9, color="#526172")
    save(fig, "latency_vs_right_tool_accuracy")


def chart_accuracy_probability(metrics: list[dict]) -> None:
    ranked = sorted(metrics, key=lambda item: item["exact_right_tool_accuracy"], reverse=True)
    fig, ax = plt.subplots(figsize=(10.5, 6.1))
    fig.subplots_adjust(left=0.15, right=0.96, top=0.87, bottom=0.20)
    positions = list(range(len(ranked)))
    top = [100 * item["exact_right_tool_accuracy"] for item in ranked]
    scores = [100 * item["mean_gold_function_probability_call_cases"] for item in ranked]
    ax.barh([p - 0.19 for p in positions], top, height=0.36, color="#2563eb",
            label="Correct function selected")
    ax.barh([p + 0.19 for p in positions], scores, height=0.36, color="#f59e0b",
            label="Mean probability assigned to correct function")
    ax.set_yticks(positions, [item["model"] for item in ranked])
    ax.invert_yaxis()
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}%"))
    ax.grid(axis="x")
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    for position, accuracy, score in zip(positions, top, scores):
        ax.text(accuracy + 1.2, position - 0.19, f"{accuracy:.1f}%", va="center", fontsize=9)
        ax.text(score + 1.2, position + 0.19, f"{score:.1f}%", va="center", fontsize=9)
    ax.set_xlabel("Share of 200 call cases / mean assigned probability", labelpad=10)
    ax.set_title("Choosing the right function versus scoring it highly", loc="left",
                 fontsize=16, fontweight="bold", pad=17)
    fig.text(0.5, 0.045, "Both measures use the same 200 call cases. Option scores are conditional and uncalibrated.",
             ha="center", fontsize=9, color="#526172")
    save(fig, "accuracy_vs_gold_function_probability")


def main() -> None:
    format_plot()
    metrics = compute_metrics()
    payload = {
        "schema": "bfcl-v1-jev-chart-metrics/v1",
        "case_file": "data/bfcl_v1/cases.jsonl",
        "cases_sha256": EXPECTED_CASES_SHA256,
        "latency_measure": "wall_latency_ms; all 250 rows, including first request",
        "accuracy_measure": "exact function ID on 200 BFCL tool-call rows",
        "probability_measure": "mean probability assigned to gold function on the same 200 rows",
        "models": metrics,
    }
    (OUT / "metrics.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    chart_size_accuracy(metrics)
    chart_latency_accuracy(metrics)
    chart_accuracy_probability(metrics)
    for item in metrics:
        print(f"{item['model']:11} {item['correct_functions']:3}/200 "
              f"{100 * item['exact_right_tool_accuracy']:5.1f}%  "
              f"mean latency {item['mean_wall_latency_ms']:5.1f} ms  "
              f"gold function probability {100 * item['mean_gold_function_probability_call_cases']:5.1f}%")


if __name__ == "__main__":
    main()
