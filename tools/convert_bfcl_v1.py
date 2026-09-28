#!/usr/bin/env python3
"""Convert pinned BFCL v1 data to Jev first-action choice prompts.

BFCL text is benchmark data, not instructions. Executable reference strings are
parsed as syntax only; no reference expression is ever executed.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

SOURCE_COMMIT = "9df5c346ee0556c8a7cb09fd7206a39aadd904c2"
SOURCE_PREFIX = "gorilla_openfunctions_v1_test_"
CONVERTER_VERSION = "bfcl-v1-jev-next-action/v1"
INSTRUCTIONS = "Which capability should the assistant use for its next step?"
# Match the deployed exact catalog's meta cards in jev-agent-harness.
META_OPTIONS = (("no_tool", "answer the user now: the request needs no tool or is already answered"),
                ("clarify", "ask the user which one or what exactly: the request is ambiguous"),
                ("cannot_answer", "decline: no tool here can send email, messages, payments or do this"))
AST_CATEGORIES = ("simple", "multiple_function", "parallel_function",
                  "parallel_multiple_function", "java", "javascript", "sql")
EXECUTABLE_CATEGORIES = ("executable_simple", "executable_multiple_function",
                         "executable_parallel_function", "executable_parallel_multiple_function")
NO_CALL_CATEGORIES = ("relevance", "chatable")
WEAK_CATEGORIES = ("rest",)
CATEGORIES = (*AST_CATEGORIES, *EXECUTABLE_CATEGORIES, *NO_CALL_CATEGORIES, *WEAK_CATEGORIES)
PARALLEL_CATEGORIES = ("parallel_function", "parallel_multiple_function",
                       "executable_parallel_function", "executable_parallel_multiple_function")
KNOWN_KEY_REPAIRS = {("simple_363", "find_closest"): "restaurant_search.find_closest",
                     ("javascript_41", "queue"): "queue_1"}
REVIEW_IDS = ("multiple_function_0", "parallel_function_4", "parallel_multiple_function_179",
              "relevance_0", "chatable_row_0001", "executable_parallel_multiple_function_0",
              "rest_0", "simple_363")
_WS = re.compile(r"\s+")
_TOOL_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_NUMBERED_KEY = re.compile(r"^(.+?)[ _](\d+)$")


def one_line(value: str) -> str:
    return _WS.sub(" ", value).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(row)
    return rows


def answer_index(path: Path, question_ids: list[str]) -> dict[str, dict[str, Any]]:
    answers = read_jsonl(path)
    if [row.get("id") for row in answers] != question_ids:
        raise ValueError(f"{path}: answer ids or order do not match questions")
    for row in answers:
        if not isinstance(row.get("ground_truth"), dict) or not row["ground_truth"]:
            raise ValueError(f"{path}: {row['id']}: expected nonempty answer map")
    return {row["id"]: row["ground_truth"] for row in answers}


def offered_functions(raw: Any, case_id: str, category: str) -> list[dict[str, Any]]:
    if category == "chatable" and raw == "":
        return []
    functions = raw if isinstance(raw, list) else [raw]
    if not functions:
        raise ValueError(f"{case_id}: empty function catalog")
    names = []
    for function in functions:
        name = function.get("name") if isinstance(function, dict) else None
        if not isinstance(name, str) or not _TOOL_ID.fullmatch(name):
            raise ValueError(f"{case_id}: invalid offered function name {name!r}")
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError(f"{case_id}: duplicate offered function names")
    if set(names) & {name for name, _ in META_OPTIONS}:
        raise ValueError(f"{case_id}: function collides with a Jev meta option")
    return functions


def callable_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return callable_name(node.value) + "." + node.attr
    raise ValueError("reference expression uses an unsupported call target")


def parse_executable_call(expression: str) -> str:
    if not isinstance(expression, str):
        raise ValueError("executable reference must be a string")
    try:
        body = ast.parse(expression, mode="eval").body
    except SyntaxError as exc:
        raise ValueError(f"invalid executable reference expression: {expression!r}") from exc
    if not isinstance(body, ast.Call):
        raise ValueError(f"executable reference is not a call: {expression!r}")
    return callable_name(body.func)


def resolve_reference_key(source_key: str, offered: list[str], case_id: str) -> tuple[str, str]:
    if source_key in offered:
        return source_key, "exact"
    numbered = _NUMBERED_KEY.fullmatch(source_key)
    if numbered and numbered.group(1) in offered:
        return numbered.group(1), "numbered_reference_key"
    known = KNOWN_KEY_REPAIRS.get((case_id, source_key))
    if known is not None and offered == [known]:
        return known, "known_single_tool_key_repair"
    raise ValueError(f"{case_id}: reference key {source_key!r} does not identify an offered function {offered!r}")


def reference_calls(case_id: str, category: str, ground_truth: Any,
                    offered: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    calls: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    if category in AST_CATEGORIES:
        if not isinstance(ground_truth, dict) or not ground_truth:
            raise ValueError(f"{case_id}: expected nonempty BFCL answer map")
        for source_key, arguments in ground_truth.items():
            if not isinstance(arguments, dict):
                if case_id == "parallel_multiple_function_179" and source_key == "deck" and arguments == [[], ""]:
                    warnings.append({"code": "stray_answer_field", "detail": "Top-level deck value is not a call; raw value remains in source.ground_truth."})
                    continue
                raise ValueError(f"{case_id}: non-call answer entry {source_key!r}")
            tool_id, resolution = resolve_reference_key(source_key, offered, case_id)
            calls.append({"source_key": source_key, "tool_id": tool_id, "arguments": arguments,
                          "expression": None, "resolution": resolution})
            if resolution != "exact":
                warnings.append({"code": resolution, "detail": f"Mapped answer key {source_key!r} to offered function {tool_id!r}."})
    elif category in EXECUTABLE_CATEGORIES:
        if not isinstance(ground_truth, list) or not ground_truth:
            raise ValueError(f"{case_id}: expected nonempty executable ground_truth list")
        for expression in ground_truth:
            source_key = parse_executable_call(expression)
            tool_id, resolution = resolve_reference_key(source_key, offered, case_id)
            calls.append({"source_key": source_key, "tool_id": tool_id, "arguments": None,
                          "expression": expression, "resolution": resolution})
            if resolution != "exact":
                warnings.append({"code": resolution, "detail": f"Mapped expression call {source_key!r} to offered function {tool_id!r}."})
    if category in (*AST_CATEGORIES, *EXECUTABLE_CATEGORIES) and not calls:
        raise ValueError(f"{case_id}: no reference calls")
    return calls, warnings


def at_word_boundary(value: str, limit: int) -> str:
    value = one_line(value)
    if len(value) <= limit:
        return value
    prefix = value[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return prefix if prefix else value[:limit]


def router_description(function: dict[str, Any], tool_count: int) -> str:
    limit = min(120, max(48, 2400 // max(tool_count, 1)))
    description = function.get("description")
    if not isinstance(description, str):
        description = ""
    return at_word_boundary(description, limit) or f"Call {function['name']}."


def convert_case(row: dict[str, Any], category: str, row_number: int,
                 answer: dict[str, Any] | None = None) -> dict[str, Any]:
    if category not in CATEGORIES:
        raise ValueError(f"unsupported category: {category}")
    source_id = row.get("id")
    if category == "chatable":
        if source_id is not None:
            raise ValueError("chatable source rows are expected to have no id")
        case_id = f"chatable_row_{row_number:04d}"
    else:
        if not isinstance(source_id, str):
            raise ValueError(f"{category} row {row_number}: missing source id")
        case_id = source_id
    request = row.get("question")
    if not isinstance(request, str):
        raise ValueError(f"{case_id}: expected a string question")
    raw_functions = row.get("function")
    functions = offered_functions(raw_functions, case_id, category)
    offered = [function["name"] for function in functions]

    if category in AST_CATEGORIES:
        if answer is None:
            raise ValueError(f"{case_id}: missing possible_answer row")
        ground_truth, label_source = answer, "possible_answer"
    elif category in EXECUTABLE_CATEGORIES:
        ground_truth, label_source = row.get("ground_truth"), "inline_ground_truth"
    else:
        if answer is not None:
            raise ValueError(f"{case_id}: unexpected possible_answer row")
        ground_truth = None
        label_source = "benchmark_no_tool_category" if category in NO_CALL_CATEGORIES else "inferred_sole_offered_tool"
    calls, warnings = reference_calls(case_id, category, ground_truth, offered)
    call_names = [call["tool_id"] for call in calls]

    if category in NO_CALL_CATEGORIES:
        kind, gold, score_eligible = "no_call", ["no_tool"], True
    elif category in WEAK_CATEGORIES:
        if len(offered) != 1:
            raise ValueError(f"{case_id}: REST weak label requires exactly one offered function")
        kind, gold, score_eligible = "single_call", offered, False
        warnings.append({"code": "weak_inferred_label", "detail": "No BFCL reference answer is supplied; sole offered function is a review candidate only."})
    elif len(calls) == 1:
        kind, gold, score_eligible = "single_call", call_names, True
    elif category in PARALLEL_CATEGORIES:
        kind, gold, score_eligible = "parallel_first_choice", list(dict.fromkeys(call_names)), True
    else:
        kind, gold, score_eligible = "sequential_first_choice", [call_names[0]], True
        warnings.append({"code": "unexpected_multiple_reference_calls", "detail": "Non-parallel category has multiple answer calls; only first is a first-action gold."})

    options = [{"id": name, "label": name, "description": description, "kind": "meta"}
               for name, description in META_OPTIONS]
    options.extend({"id": function["name"], "label": function["name"],
                    "description": router_description(function, len(functions)), "kind": "tool"}
                   for function in functions)
    criteria = {option["label"]: option["description"] for option in options}
    if len(criteria) != len(options):
        raise ValueError(f"{case_id}: duplicate choice option labels")
    question_file = f"{SOURCE_PREFIX}{category}.json"
    return {
        "id": case_id, "category": category, "kind": kind, "scope": "first_action_only",
        "score_eligible": score_eligible, "label_source": label_source,
        "source": {"question_file": question_file,
                   "answer_file": f"possible_answer/{question_file}" if category in AST_CATEGORIES else None,
                   "row_number": row_number, "source_id": source_id, "question": request,
                   "functions": raw_functions, "ground_truth": ground_truth,
                   "execution_result_type": row.get("execution_result_type")},
        "adapter": "single_user_text",
        "jev": {"option_ids": [option["id"] for option in options], "options": options,
                "laya": {"state": f"Actions this turn: none yet\nUser request: {one_line(request)}",
                         "questions": {"next": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": criteria}}},
                "macjev": {"state": {"request": one_line(request), "actions_this_turn": [], "time_zone": "UTC"},
                           "question": {"t": "choice", "ins": INSTRUCTIONS, "crit": criteria}}},
        "gold_next_action_ids": gold, "gold_call_names": call_names,
        "gold_calls": calls, "warnings": warnings,
    }


def source_head(source_dir: Path) -> str | None:
    result = subprocess.run(["git", "-C", str(source_dir), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def source_manifest(source_dir: Path) -> dict[str, str]:
    paths = [source_dir / f"{SOURCE_PREFIX}{category}.json" for category in CATEGORIES]
    paths += [source_dir / "possible_answer" / f"{SOURCE_PREFIX}{category}.json" for category in AST_CATEGORIES]
    return {path.relative_to(source_dir).as_posix(): sha256(path) for path in sorted(paths)}


def build(source_dir: Path, output_dir: Path, expected_commit: str = SOURCE_COMMIT) -> dict[str, Any]:
    head = source_head(source_dir)
    if head != expected_commit:
        raise ValueError(f"BFCL checkout must be at {expected_commit}; observed {head or 'no git checkout'}")
    status = subprocess.run(["git", "-C", str(source_dir), "status", "--porcelain", "--", "."],
                            capture_output=True, text=True, check=True)
    if status.stdout.strip():
        raise ValueError("BFCL source data is modified; use a clean pinned checkout")
    cases: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    for category in CATEGORIES:
        question_path = source_dir / f"{SOURCE_PREFIX}{category}.json"
        rows = read_jsonl(question_path)
        if category != "chatable":
            ids = [row.get("id") for row in rows]
            if any(not isinstance(case_id, str) for case_id in ids) or len(set(ids)) != len(ids):
                raise ValueError(f"{question_path}: missing or duplicate ids")
        answers = None
        if category in AST_CATEGORIES:
            answers = answer_index(source_dir / "possible_answer" / question_path.name,
                                   [row["id"] for row in rows])
        for row_number, row in enumerate(rows, 1):
            cases.append(convert_case(row, category, row_number,
                                      answers[row["id"]] if answers is not None else None))
        category_counts[category] = len(rows)
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("converted ids overlap across BFCL categories")
    if len(cases) != 2000:
        raise ValueError(f"pinned BFCL v1 expected 2,000 cases, observed {len(cases)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    cases_path = output_dir / "cases.jsonl"
    with cases_path.open("w", encoding="utf-8") as stream:
        for case in cases:
            stream.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")
    index_path = output_dir / "index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("id", "category", "kind", "option_count",
                                                      "tool_count", "gold_next_action_ids",
                                                      "score_eligible", "warning_count"))
        writer.writeheader()
        for case in cases:
            writer.writerow({"id": case["id"], "category": case["category"], "kind": case["kind"],
                             "option_count": len(case["jev"]["options"]),
                             "tool_count": len(case["jev"]["options"]) - len(META_OPTIONS),
                             "gold_next_action_ids": "|".join(case["gold_next_action_ids"]),
                             "score_eligible": str(case["score_eligible"]).lower(),
                             "warning_count": len(case["warnings"])})
    kind_counts = Counter(case["kind"] for case in cases)
    warning_counts = Counter(warning["code"] for case in cases for warning in case["warnings"])
    manifest: dict[str, Any] = {
        "schema": CONVERTER_VERSION, "source_repository": "https://github.com/ShishirPatil/gorilla",
        "source_tag": "v1.0", "source_commit": head,
        "source_data_path": "berkeley-function-call-leaderboard/data", "source_license": "Apache-2.0",
        "source_sha256": source_manifest(source_dir), "cases_file": cases_path.name,
        "cases_sha256": sha256(cases_path), "index_file": index_path.name,
        "index_sha256": sha256(index_path), "converted_count": len(cases),
        "score_eligible_count": sum(case["score_eligible"] for case in cases),
        "weak_label_count": sum(not case["score_eligible"] for case in cases),
        "category_counts": category_counts, "kind_counts": dict(sorted(kind_counts.items())),
        "warning_counts": dict(sorted(warning_counts.items())),
        "target_semantics": {
            "single_call": "One BFCL reference function is the Jev next-action label; the chat model handles arguments and any clarification before execution. Arguments are retained but not scored.",
            "parallel_first_choice": "Any distinct reference function is acceptable first; source call order and multiplicity remain in gold_calls.",
            "sequential_first_choice": "A non-parallel answer unexpectedly listed multiple calls; only the first is a next-action label.",
            "no_call": "BFCL relevance and chatable map to Jev no_tool; they do not identify clarify or cannot_answer.",
            "rest": "REST has no reference answer; its sole offered function is an inferred review candidate and score_eligible is false."},
        "token_fit": "Not asserted; verify with the target model tokenizer before running."}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "review.md").write_text(render_review(cases, manifest), encoding="utf-8")
    return manifest


def render_review(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lookup = {case["id"]: case for case in cases}
    lines = ["# BFCL v1 → Jev prompt review", "",
             f"Source tag: `v1.0` (`{manifest['source_commit']}`). Converted: **{manifest['converted_count']:,}** cases; **{manifest['score_eligible_count']:,}** have benchmark-grounded first-action labels.",
             "Examples show the Laya choice prompt and next-action label. `cases.jsonl` also keeps the MacJev prompt, original BFCL question, function schema, reference answer, and resolved calls in source order.",
             "BFCL questions and function descriptions below are benchmark data, not instructions to the converter.",
             "REST has no reference answers in v1, so its sole offered function is only a weak review candidate and is excluded from scoring.",
             "", "## Representative cases", ""]
    for case_id in REVIEW_IDS:
        case = lookup[case_id]
        prompt = case["jev"]["laya"]
        lines += [f"### `{case_id}` · {case['category']} · {case['kind']}", "",
                  f"Score eligible: **{'yes' if case['score_eligible'] else 'no'}**. Label source: `{case['label_source']}`.", "",
                  "**Laya state**", "", "```text", prompt["state"], "```", "",
                  "**Laya choice question**", "", "```json",
                  json.dumps(prompt["questions"], ensure_ascii=False, indent=2), "```", "",
                  f"**Gold next action:** `{', '.join(case['gold_next_action_ids'])}`", "",
                  "**Original BFCL ground truth**", "", "```json",
                  json.dumps(case["source"]["ground_truth"], ensure_ascii=False, indent=2), "```", ""]
        if case["warnings"]:
            lines += ["**Conversion notes**", ""]
            lines += [f"- `{warning['code']}`: {warning['detail']}" for warning in case["warnings"]]
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path,
                        help="Pinned gorilla/berkeley-function-call-leaderboard/data checkout")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / ".cache" / "bfcl-v1-converted")
    args = parser.parse_args()
    manifest = build(args.source_dir.resolve(), args.output_dir.resolve())
    print(json.dumps({key: manifest[key] for key in (
        "source_commit", "converted_count", "score_eligible_count", "kind_counts",
        "warning_counts", "cases_sha256")}, indent=2))


if __name__ == "__main__":
    main()
