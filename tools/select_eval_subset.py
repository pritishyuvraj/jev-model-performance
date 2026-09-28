#!/usr/bin/env python3
"""Select a reproducible, reviewable 250-case BFCL v1 Jev routing subset.

The converted BFCL questions and tool descriptions are benchmark data. This
script never treats their text as instructions or executes reference calls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / ".cache" / "bfcl-v1-converted" / "cases.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "bfcl_v1"
DEFAULT_REVIEW = ROOT / "tools" / "bfcl_v1_selection_review.json"
SCHEMA = "bfcl-v1-jev-eval-subset/v1"
SEED = "bfcl-v1-jev-routing-250-v1"
# Priority matters when two BFCL categories reuse the same user request.
QUOTAS: dict[str, int] = {
    "multiple_function": 120,
    "executable_multiple_function": 30,
    "relevance": 50,
    "simple": 35,
    "executable_simple": 15,
}
CATEGORY_EXCLUSIONS = {
    "parallel_function": "Several calls are valid, so there is no unique first action.",
    "parallel_multiple_function": "Several calls are valid, so there is no unique first action.",
    "executable_parallel_function": "Several calls are valid, so there is no unique first action.",
    "executable_parallel_multiple_function": "Several calls are valid, so there is no unique first action.",
    "chatable": "The zero-tool prompts mostly repeat tool-call questions with a different offered catalog.",
    "rest": "BFCL v1 supplies no reference answer for REST; its converted label is inferred.",
    "sql": "These controls all offer the same single sql.execute tool; other one-tool controls provide more variety.",
    "java": "Language-specific function catalogs are outside the chosen pilot categories.",
    "javascript": "Language-specific function catalogs are outside the chosen pilot categories.",
}
INDEX_FIELDS = ("id", "category", "stratum", "kind", "tool_count", "gold_next_action_ids", "question_preview")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_request(case: dict[str, Any]) -> str:
    request = case.get("source", {}).get("question")
    if not isinstance(request, str):
        raise ValueError(f"{case.get('id')}: missing source question")
    key = " ".join(unicodedata.normalize("NFKC", request).split()).casefold()
    if not key:
        raise ValueError(f"{case.get('id')}: empty source question")
    return key


def rank(case_id: str) -> str:
    return sha256_bytes(f"{SEED}\0{case_id}".encode("utf-8"))


def read_parent(input_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    parent_path = input_path.with_name("manifest.json")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    if not isinstance(parent, dict):
        raise ValueError(f"{parent_path}: expected manifest object")
    input_hash = sha256_file(input_path)
    if parent.get("cases_sha256") != input_hash:
        raise ValueError(f"{parent_path}: parent cases_sha256 does not match {input_path}")
    if not isinstance(parent.get("source_commit"), str) or not parent["source_commit"]:
        raise ValueError(f"{parent_path}: missing source_commit")
    cases: list[dict[str, Any]] = []
    ids: set[str] = set()
    with input_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{input_path}:{line_number}: invalid JSON") from exc
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                raise ValueError(f"{input_path}:{line_number}: expected case with string id")
            if case["id"] in ids:
                raise ValueError(f"{input_path}:{line_number}: duplicate id {case['id']}")
            ids.add(case["id"])
            normalized_request(case)
            cases.append(case)
    if parent.get("converted_count") != len(cases):
        raise ValueError(f"{parent_path}: converted_count does not match input")
    return cases, parent, input_hash


def read_selection_review(path: Path | None) -> tuple[dict[str, str], set[str] | None, dict[str, set[str]], str | None]:
    if path is None:
        return {}, None, {}, None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON selection review object")
    excluded = raw.get("exclude_ids", {})
    if isinstance(excluded, list):
        if any(not isinstance(case_id, str) or not case_id for case_id in excluded) or len(excluded) != len(set(excluded)):
            raise ValueError(f"{path}: exclude_ids must contain distinct nonempty case ids")
        exclusions = {case_id: "manual_review" for case_id in excluded}
    elif isinstance(excluded, dict):
        if any(not isinstance(case_id, str) or not case_id or
               not isinstance(reason, str) or not reason.strip()
               for case_id, reason in excluded.items()):
            raise ValueError(f"{path}: exclude_ids must map case ids to nonempty review reasons")
        exclusions = dict(excluded)
    else:
        raise ValueError(f"{path}: exclude_ids must be a list or reason map")
    listed = raw.get("relevance_allowlist")
    if listed is not None:
        if not isinstance(listed, list) or any(not isinstance(case_id, str) or not case_id for case_id in listed) or len(listed) != len(set(listed)):
            raise ValueError(f"{path}: relevance_allowlist must contain distinct nonempty case ids")
        allowlist: set[str] | None = set(listed)
    else:
        allowlist = None
    raw_positive = raw.get("positive_allowlist", {})
    if not isinstance(raw_positive, dict) or any(category not in ("simple", "executable_simple")
                                              for category in raw_positive):
        raise ValueError(f"{path}: positive_allowlist must be an object keyed by simple/executable_simple")
    positive_allowlist: dict[str, set[str]] = {}
    for category, listed_ids in raw_positive.items():
        if not isinstance(listed_ids, list) or any(not isinstance(case_id, str) or not case_id for case_id in listed_ids) or len(listed_ids) != len(set(listed_ids)):
            raise ValueError(f"{path}: positive_allowlist.{category} must contain distinct nonempty case ids")
        positive_allowlist[category] = set(listed_ids)
    return exclusions, allowlist, positive_allowlist, sha256_file(path)


def eligibility_reason(case: dict[str, Any], quotas: Mapping[str, int],
                       exclusions: Mapping[str, str] | None = None,
                       relevance_allowlist: set[str] | None = None,
                       positive_allowlist: Mapping[str, set[str]] | None = None) -> str:
    # Reasons form a partition of the parent corpus, in this priority order.
    if case.get("score_eligible") is not True:
        return "not_score_eligible"
    if case.get("kind") not in ("single_call", "no_call"):
        return "non_unique_first_action"
    if case.get("warnings") != []:
        return "conversion_warning"
    if case.get("category") not in quotas:
        return "category_not_selected"
    if exclusions and case["id"] in exclusions:
        return "explicit_review_exclusion"
    if case.get("category") == "relevance" and relevance_allowlist is not None and case["id"] not in relevance_allowlist:
        return "outside_reviewed_relevance_allowlist"
    if positive_allowlist and case.get("category") in positive_allowlist and case["id"] not in positive_allowlist[case["category"]]:
        return "outside_reviewed_positive_allowlist"
    gold = case.get("gold_next_action_ids")
    options = case.get("jev", {}).get("option_ids")
    if not isinstance(gold, list) or len(gold) != 1 or not isinstance(options, list) or gold[0] not in options:
        raise ValueError(f"{case['id']}: invalid single-action label or options")
    return "eligible_pool"


def tool_options(case: dict[str, Any]) -> list[str]:
    options = case.get("jev", {}).get("options")
    if not isinstance(options, list):
        raise ValueError(f"{case['id']}: missing Jev options")
    tools = [option.get("id") for option in options if isinstance(option, dict) and option.get("kind") == "tool"]
    if any(not isinstance(tool, str) for tool in tools):
        raise ValueError(f"{case['id']}: invalid tool option")
    return tools


def stratum(case: dict[str, Any]) -> str:
    tools = tool_options(case)
    if case["kind"] == "no_call" and len(tools) == 1 and case["gold_next_action_ids"] == ["no_tool"]:
        return "one_tool_no_call"
    if case["kind"] == "single_call" and len(tools) == 1:
        return "one_tool_call"
    if case["kind"] == "single_call" and len(tools) > 1:
        return "multi_tool_call"
    raise ValueError(f"{case['id']}: selected case does not belong to a defined routing stratum")


def select_cases(cases: list[dict[str, Any]], quotas: Mapping[str, int] = QUOTAS,
                 exclusions: Mapping[str, str] | None = None,
                 relevance_allowlist: set[str] | None = None,
                 positive_allowlist: Mapping[str, set[str]] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not quotas or any(not isinstance(count, int) or count <= 0 for count in quotas.values()):
        raise ValueError("quotas must contain positive integer counts")
    exclusions = {} if exclusions is None else exclusions
    positive_allowlist = {} if positive_allowlist is None else positive_allowlist
    lookup = {case["id"]: case for case in cases}
    if len(lookup) != len(cases):
        raise ValueError("duplicate case ids")
    for case_id in exclusions:
        if case_id not in lookup:
            raise ValueError(f"explicit exclusion id {case_id!r} is absent from parent corpus")
        if eligibility_reason(lookup[case_id], quotas) != "eligible_pool":
            raise ValueError(f"explicit exclusion id {case_id!r} is not in the eligible pool")
    if relevance_allowlist is not None:
        for case_id in relevance_allowlist:
            if case_id not in lookup or lookup[case_id].get("category") != "relevance":
                raise ValueError(f"relevance allowlist id {case_id!r} is absent or not a relevance case")
            if case_id in exclusions:
                raise ValueError(f"relevance allowlist id {case_id!r} is also explicitly excluded")
            if eligibility_reason(lookup[case_id], quotas) != "eligible_pool":
                raise ValueError(f"relevance allowlist id {case_id!r} is not in the eligible pool")
    for category, listed_ids in positive_allowlist.items():
        if category not in ("simple", "executable_simple") or category not in quotas:
            raise ValueError(f"positive allowlist category {category!r} is not an included positive category")
        for case_id in listed_ids:
            if case_id not in lookup or lookup[case_id].get("category") != category:
                raise ValueError(f"positive allowlist id {case_id!r} is absent or not in {category}")
            if case_id in exclusions:
                raise ValueError(f"positive allowlist id {case_id!r} is also explicitly excluded")
            if eligibility_reason(lookup[case_id], quotas) != "eligible_pool":
                raise ValueError(f"positive allowlist id {case_id!r} is not in the eligible pool")
    reasons = Counter(eligibility_reason(case, quotas, exclusions, relevance_allowlist, positive_allowlist)
                      for case in cases)
    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        if eligibility_reason(case, quotas, exclusions, relevance_allowlist, positive_allowlist) == "eligible_pool":
            pools[case["category"]].append(case)
    seen: set[str] = set()
    selected: list[dict[str, Any]] = []
    selected_counts: dict[str, int] = {}
    duplicate_skips: dict[str, int] = {}
    for category, quota in quotas.items():
        chosen: list[dict[str, Any]] = []
        skipped = 0
        for case in sorted(pools[category], key=lambda item: (rank(item["id"]), item["id"])):
            key = normalized_request(case)
            if key in seen:
                skipped += 1
                continue
            # Validate the intended strata before mutating selection state.
            stratum(case)
            seen.add(key)
            chosen.append(case)
            if len(chosen) == quota:
                break
        if len(chosen) != quota:
            raise ValueError(f"{category}: only {len(chosen)} unique eligible cases for quota {quota}")
        selected.extend(chosen)
        selected_counts[category] = len(chosen)
        duplicate_skips[category] = skipped
    order = {category: index for index, category in enumerate(quotas)}
    selected.sort(key=lambda case: (order[case["category"]], case["source"].get("row_number", 0), case["id"]))
    candidate_keys = Counter(normalized_request(case) for pool in pools.values() for case in pool)
    diagnostics = {
        "parent_count": len(cases),
        "eligibility_counts": dict(sorted(reasons.items())),
        "eligible_pool_counts": {category: len(pools[category]) for category in quotas},
        "selected_counts": selected_counts,
        "selection_skipped_duplicate_requests": duplicate_skips,
        "eligible_pool_duplicate_request_groups": sum(count > 1 for count in candidate_keys.values()),
        "eligible_pool_extra_duplicate_request_rows": sum(count - 1 for count in candidate_keys.values()),
    }
    return selected, diagnostics


def baseline_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_stratum: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "first_offered_tool_correct": 0, "always_no_tool_correct": 0})
    for case in cases:
        label = stratum(case)
        bucket = by_stratum[label]
        bucket["count"] += 1
        bucket["first_offered_tool_correct"] += int(tool_options(case)[0] in case["gold_next_action_ids"])
        bucket["always_no_tool_correct"] += int("no_tool" in case["gold_next_action_ids"])
    result = {label: by_stratum[label] for label in ("multi_tool_call", "one_tool_call", "one_tool_no_call")}
    result["overall"] = {field: sum(bucket[field] for bucket in by_stratum.values())
                         for field in ("count", "first_offered_tool_correct", "always_no_tool_correct")}
    return result


def one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def preview(case: dict[str, Any], limit: int = 160) -> str:
    request = one_line(case["source"]["question"])
    return request if len(request) <= limit else request[: limit - 1].rstrip() + "…"


def render_index(cases: list[dict[str, Any]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=INDEX_FIELDS, lineterminator="\n")
    writer.writeheader()
    for case in cases:
        writer.writerow({"id": case["id"], "category": case["category"], "stratum": stratum(case),
                         "kind": case["kind"], "tool_count": len(tool_options(case)),
                         "gold_next_action_ids": "|".join(case["gold_next_action_ids"]),
                         "question_preview": preview(case)})
    return buffer.getvalue()


def fenced(content: str) -> list[str]:
    longest = max((len(match.group()) for match in re.finditer(r"`+", content)), default=0)
    marker = "`" * max(3, longest + 1)
    return [marker + "text", content, marker]


def render_review(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    summary = manifest["baseline_by_stratum"]
    lines = ["# BFCL v1 → Jev: 250-case review set", "",
             f"Pinned BFCL source: `{manifest['source_commit']}`. This subset contains **{len(cases)}** source-grounded, warning-free, single-action prompts.",
             "The benchmark requests, descriptions, and reference answers below are data for review, not instructions to execute.",
             "", "## What this set measures", "",
             "A Jev-style router chooses its next capability from the offered catalog. After it selects a function, the chat model supplies arguments and can ask for missing values before execution. This set scores only the router's choice.",
             "BFCL's relevance category says only that no function was called. Mapping that to Jev `no_tool` does not establish whether `clarify` or `cannot_answer` would be preferable; review these 50 prompts before treating subtype accuracy as definitive.",
             "", "| Stratum | Cases | First offered tool correct | Always no_tool correct |", "|---|---:|---:|---:|" ]
    for label in ("multi_tool_call", "one_tool_call", "one_tool_no_call", "overall"):
        row = summary[label]
        lines.append(f"| {label} | {row['count']} | {row['first_offered_tool_correct']} | {row['always_no_tool_correct']} |")
    lines += ["", "## Representative prompts", ""]
    for category in manifest["quotas"]:
        case = next(case for case in cases if case["category"] == category)
        laya = case["jev"]["laya"]
        lines += [f"### `{case['id']}` · {category}", "", "**Laya state**", ""]
        lines += fenced(laya["state"])
        lines += ["", "**Choice question**", ""]
        lines += fenced(json.dumps(laya["questions"], ensure_ascii=False, indent=2))
        lines += ["", f"**Gold next action:** `{case['gold_next_action_ids'][0]}`", "",
                  "**Original BFCL reference answer**", ""]
        lines += fenced(json.dumps(case["source"]["ground_truth"], ensure_ascii=False, indent=2))
        lines.append("")
    lines += ["## All selected cases", "",
              "See `index.csv` for the same list in a sortable format and `cases.jsonl` for complete prompts and BFCL source records.",
              "", "| ID | Stratum | Gold next action | Request preview |", "|---|---|---|---|"]
    for case in cases:
        request = preview(case, 120).replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")
        gold = case["gold_next_action_ids"][0].replace("|", "\\|")
        lines.append(f"| `{case['id']}` | {stratum(case)} | `{gold}` | {request} |")
    return "\n".join(lines) + "\n"


def build(input_path: Path, output_dir: Path, quotas: Mapping[str, int] = QUOTAS,
          selection_review_file: Path | None = None) -> dict[str, Any]:
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    if input_path == output_dir / "cases.jsonl":
        raise ValueError("input and output cases.jsonl must be different paths")
    cases, parent, parent_hash = read_parent(input_path)
    exclusions, relevance_allowlist, positive_allowlist, review_hash = read_selection_review(selection_review_file)
    selected, diagnostics = select_cases(cases, quotas, exclusions, relevance_allowlist, positive_allowlist)
    if len(selected) != sum(quotas.values()):
        raise AssertionError("selection count differs from quotas")
    cases_text = "".join(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n" for case in selected)
    index_text = render_index(selected)
    excluded_categories = {category: count for category, count in sorted(Counter(case["category"] for case in cases).items())
                           if category not in quotas}
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "source_repository": parent.get("source_repository"),
        "source_tag": parent.get("source_tag"),
        "source_commit": parent["source_commit"],
        "source_license": parent.get("source_license"),
        "parent_corpus": {"schema": parent.get("schema"), "cases_sha256": parent_hash,
                          "converted_count": len(cases)},
        "cases_file": "cases.jsonl", "cases_sha256": sha256_bytes(cases_text.encode("utf-8")),
        "index_file": "index.csv", "index_sha256": sha256_bytes(index_text.encode("utf-8")),
        "selected_count": len(selected), "quotas": dict(quotas),
        "selected_category_counts": diagnostics["selected_counts"],
        "baseline_by_stratum": baseline_summary(selected),
        "selection_algorithm": {
            "name": "stratified_sha256_id_rank_with_global_request_dedup",
            "seed": SEED,
            "rank": "SHA256 of UTF-8 seed, NUL, and case id; ascending lexical digest per category",
            "quota_priority": list(quotas),
            "prefilter": "Apply explicit review exclusions and optional relevance/positive allowlists before hash ranking; refill each category quota",
            "duplicate_key": "Unicode NFKC source question, collapsed whitespace, casefold",
            "output_order": "quota priority, then source row number, then case id",
        },
        "selection_review": {
            "file": selection_review_file.name if selection_review_file is not None else None,
            "sha256": review_hash,
            "excluded_id_count": len(exclusions),
            "relevance_allowlist_count": len(relevance_allowlist) if relevance_allowlist is not None else None,
            "relevance_allowlist": sorted(relevance_allowlist) if relevance_allowlist is not None else None,
            "positive_allowlist_counts": {category: len(ids) for category, ids in sorted(positive_allowlist.items())},
            "positive_allowlist": {category: sorted(ids) for category, ids in sorted(positive_allowlist.items())},
        },
        "exclusions": {
            "rules": ["score_eligible must be true", "kind must be single_call or no_call",
                      "warnings must be empty", "one gold next-action id must appear in offered options",
                      "duplicate normalized user requests cannot both be selected"],
            "category_reasons": CATEGORY_EXCLUSIONS,
            "excluded_category_counts": excluded_categories,
            "eligibility_counts": diagnostics["eligibility_counts"],
            "eligible_pool_counts": diagnostics["eligible_pool_counts"],
            "selection_skipped_duplicate_requests": diagnostics["selection_skipped_duplicate_requests"],
            "eligible_pool_duplicate_request_groups": diagnostics["eligible_pool_duplicate_request_groups"],
            "eligible_pool_extra_duplicate_request_rows": diagnostics["eligible_pool_extra_duplicate_request_rows"],
            "explicit_review_exclusions": dict(sorted(exclusions.items())),
        },
        "evaluation_notes": [
            "Score the three strata separately; option count and no-call prevalence differ across them.",
            "The relevance no_tool label is BFCL's no-function-call outcome mapped to a Jev action, not a verified clarify/cannot_answer subtype.",
            "Some BFCL call examples may be answerable directly. Human review is required before interpreting the set as a final Jev benchmark.",
            "The chat model handles tool arguments and can clarify missing values after a tool is selected; this set does not score arguments, execution, or full-task completion.",
        ],
    }
    review_text = render_review(selected, manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cases.jsonl").write_text(cases_text, encoding="utf-8")
    (output_dir / "index.csv").write_text(index_text, encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "review.md").write_text(review_text, encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Full converted BFCL v1 cases.jsonl (with sibling manifest.json)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Directory for the 250-case review and evaluation subset")
    parser.add_argument("--review-file", type=Path,
                        help="JSON selection review with exclude_ids and optional relevance/positive allowlists")
    args = parser.parse_args()
    review_file = args.review_file
    if review_file is None and DEFAULT_REVIEW.is_file():
        review_file = DEFAULT_REVIEW
    manifest = build(args.input, args.output, selection_review_file=review_file)
    print(json.dumps({"selected_count": manifest["selected_count"],
                      "selected_category_counts": manifest["selected_category_counts"],
                      "baseline_by_stratum": manifest["baseline_by_stratum"],
                      "cases_sha256": manifest["cases_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
