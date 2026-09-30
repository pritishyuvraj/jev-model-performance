#!/usr/bin/env python3
"""Check complete V4 choice inputs against the scored native Laya tokenizer.

Tokenization only: no model weights, inference, or network downloads. The layout
and default limits mirror NandhaKishorM/laya@9d955671 common.py. The accepted
tokenizer is byte-identical in the pinned standalone and scored bundled model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TOKENIZER_SHA256 = "6c8aaa9a542084f2457eab775d4eeb51f92a70c0fd9de28d5edb0ddec3c08d30"
TOKENIZER_CONFIG_SHA256 = "08d4cf3ac4dca381759441b85b91a6d40e688471dcd33d15d6649eb0a9a854d1"
MAX_LEN, HEAD_MAX_LEN, MAX_OPTION_TOKENS = 1024, 256, 48


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(tok, payload: dict) -> dict:
    question = payload["questions"]["next"]
    if question["type"] != "choice" or not isinstance(payload["state"], str):
        raise ValueError("expected string state and one choice question")
    count = lambda s: len(tok(s.replace(tok.mask_token, " "), add_special_tokens=False)["input_ids"])
    instruction = count(f"choice question: {question['instructions']}")
    lengths = [count(f" {key}: {description}") for key, description in question["criteria"].items()]
    options = sum(1 + length for length in lengths)
    head = instruction + options
    total = 4 + head + count(payload["state"])
    failures = []
    if max(lengths, default=0) > MAX_OPTION_TOKENS:
        failures.append("per_option_limit")
    if head > HEAD_MAX_LEN or HEAD_MAX_LEN - options < 16:
        failures.append("head_limit")
    if total > MAX_LEN:
        failures.append("total_limit")
    return {"fits_without_truncation": not failures, "failures": failures,
            "input_tokens": total, "head_tokens": head,
            "longest_option_tokens": max(lengths, default=0)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--tokenizer-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    tokenizer_file = args.tokenizer_path / "tokenizer.json"
    if digest(tokenizer_file) != TOKENIZER_SHA256:
        raise SystemExit("Tokenizer differs from the frozen native Laya tokenizer")
    if digest(args.tokenizer_path / "tokenizer_config.json") != TOKENIZER_CONFIG_SHA256:
        raise SystemExit("Tokenizer configuration differs from the frozen native Laya configuration")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.tokenizer_path, local_files_only=True)
    cases = [json.loads(line) for line in args.cases.read_text().splitlines() if line.strip()]
    rows = [{"id": case["id"], **inspect(tok, case["jev"]["laya"])} for case in cases]
    report = {
        "schema": "bfcl-v4-native-laya-input-fit/v1",
        "method": "Complete, untruncated tokenization only; no model inference.",
        "cases_sha256": digest(args.cases),
        "checked_count": len(rows),
        "tokenizer_sha256": TOKENIZER_SHA256,
        "tokenizer_config_sha256": TOKENIZER_CONFIG_SHA256,
        "checkpoint_revision": "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851",
        "serving_revision": "9d955671415fc19f069b9cc998928075c1f255ec",
        "limits": {"max_len": MAX_LEN, "head_max_len": HEAD_MAX_LEN,
                   "max_option_tokens": MAX_OPTION_TOKENS},
        "max_input_tokens": max((r["input_tokens"] for r in rows), default=0),
        "max_head_tokens": max((r["head_tokens"] for r in rows), default=0),
        "max_option_tokens": max((r["longest_option_tokens"] for r in rows), default=0),
        "failures": [r for r in rows if not r["fits_without_truncation"]],
        "per_case": rows,
        "coverage_note": "This checks native Laya only. The other six native adapters require their own preflight when evaluated.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"checked_count": len(rows), "failures": len(report["failures"]),
                      "max_input_tokens": report["max_input_tokens"], "output": str(args.output)}))
    if report["failures"] or not rows:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
