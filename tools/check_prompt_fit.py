#!/usr/bin/env python3
"""Check generated BFCL prompts against the Jev harness's pinned tokenizers.

Run with the harness virtual environment. This loads tokenizers only, not model
weights, and does not call a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(cases_path: Path, harness_root: Path) -> dict:
    sys.path.insert(0, str(harness_root / "python"))
    from transformers import AutoTokenizer
    from localpa import config
    from localpa.decision.laya import fit as laya_fit
    from localpa.decision.macjev_runtime.macjev_inputs import (
        InputBudgetError, TokenizerAdapter, build_sequence, options,
    )

    laya_path = config.model_snapshot("decision") / "tokenizer"
    macjev_path = config.model_snapshot("decision_macjev")
    laya_tok = AutoTokenizer.from_pretrained(laya_path, local_files_only=True)
    macjev_tok = TokenizerAdapter(
        (macjev_path / "tokenizer/tokenizer.json").read_text(),
        json.loads((macjev_path / "tokenizer/tokenizer_config.json").read_text()),
    )
    models = config.models_config()
    budgets = {
        "laya": (int(models["decision"]["max_len"]), int(models["decision"]["head_max_len"])),
        "macjev": (int(models["decision_macjev"]["max_len"]), int(models["decision_macjev"]["head_max_len"])),
    }
    counts = {"laya": {"failures": [], "max_input_tokens": 0, "max_head_tokens": 0},
              "macjev": {"failures": [], "max_input_tokens": 0, "max_head_tokens": 0}}
    total = 0
    with cases_path.open(encoding="utf-8") as stream:
        for line in stream:
            case = json.loads(line)
            total += 1
            laya = case["jev"]["laya"]
            laya_result = laya_fit(laya_tok, laya["state"], laya["questions"]["next"], *budgets["laya"])
            counts["laya"]["max_input_tokens"] = max(counts["laya"]["max_input_tokens"], laya_result["input_tokens"])
            counts["laya"]["max_head_tokens"] = max(counts["laya"]["max_head_tokens"], laya_result["head_tokens"])
            if not laya_result["fits"]:
                counts["laya"]["failures"].append({"id": case["id"], "reason": laya_result["reason"]})

            macjev = case["jev"]["macjev"]
            state, question = macjev["state"], macjev["question"]
            clean = lambda value: str(value).replace(macjev_tok.mask_token, " ")
            encoded = macjev_tok([
                f"{question['t']} question: {clean(question['ins'])}",
                *[" " + clean(value) for value in options(question)],
                clean(json.dumps(state, ensure_ascii=False)),
            ])["input_ids"]
            head = len(encoded[0]) + sum(1 + len(piece) for piece in encoded[1:-1])
            input_tokens = head + len(encoded[-1]) + 4
            counts["macjev"]["max_input_tokens"] = max(counts["macjev"]["max_input_tokens"], input_tokens)
            counts["macjev"]["max_head_tokens"] = max(counts["macjev"]["max_head_tokens"], head)
            try:
                build_sequence(macjev_tok, state, question, *budgets["macjev"])
            except InputBudgetError as exc:
                counts["macjev"]["failures"].append({"id": case["id"], "reason": str(exc)})

    return {
        "schema": "jev-prompt-fit/v1",
        "cases_sha256": sha256(cases_path),
        "checked_count": total,
        "method": "Tokenization and complete input-budget check only; no model inference.",
        "models": {
            "laya": {"repo": models["decision"]["repo"], "revision": models["decision"]["revision"],
                     "max_len": budgets["laya"][0], "head_max_len": budgets["laya"][1], **counts["laya"]},
            "macjev": {"repo": models["decision_macjev"]["repo"], "revision": models["decision_macjev"]["revision"],
                       "max_len": budgets["macjev"][0], "head_max_len": budgets["macjev"][1], **counts["macjev"]},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness-root", required=True, type=Path)
    parser.add_argument("--cases", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data/bfcl_v1/cases.jsonl")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data/bfcl_v1/fit_report.json")
    args = parser.parse_args()
    report = check(args.cases.resolve(), args.harness_root.resolve())
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checked_count": report["checked_count"],
                      "failure_counts": {name: len(value["failures"]) for name, value in report["models"].items()},
                      "output": str(args.output)}, indent=2))
    if any(value["failures"] for value in report["models"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
