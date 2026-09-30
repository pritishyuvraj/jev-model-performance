#!/usr/bin/env python3
"""Freeze a reviewed, V1-disjoint BFCL V4 Live capability-routing subset.

Benchmark questions, descriptions, and reference arguments are data. This tool
does not execute benchmark expressions or call a model. Every selected row must
have an explicit semantic acceptance in the review file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from convert_bfcl_v1 import INSTRUCTIONS, CATEGORIES as V1_CATEGORIES


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "f7cf7359b7ac615a0b294831c5ba2bc95ee4a000"
V1_SOURCE_COMMIT = "9df5c346ee0556c8a7cb09fd7206a39aadd904c2"
SCHEMA = "bfcl-v4-live-jev-routing-subset/v1"
REVIEW_SCHEMA = "bfcl-v4-routing-review/v1"
DEFAULT_SEED = "bfcl-v4-live-jev-routing-250-v1"
META_CARD_VERSION = "bfcl-v4-neutral-meta-cards/v1"
META_OPTIONS = (("no_tool", "Respond without calling an offered tool because no tool is needed."),
                ("clarify", "Ask what capability the user intends because the request is ambiguous."),
                ("cannot_answer", "The request needs a capability that none of the offered tools provides."))
QUOTAS = {"live_multiple": 150, "live_simple": 50, "live_irrelevance": 50}
V1_PREFIX = "gorilla_openfunctions_v1_test_"
NORMALIZATION = "Unicode NFKC, casefold, Unicode word tokens joined by one space (punctuation and symbols removed)"
TOOL_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
LIVE_ID = re.compile(r"live_(?:multiple|simple|irrelevance)_\d+-(\d+)-\d+\Z")
META_IDS = [item[0] for item in META_OPTIONS]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8"))


def normalized_request(request: str) -> str:
    if not isinstance(request, str):
        raise ValueError("request must be a string")
    text = " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", request).casefold(), flags=re.UNICODE))
    if not text:
        raise ValueError("request is empty after normalization")
    return text


def request_hash(request: str) -> str:
    return sha256_bytes(normalized_request(request).encode("utf-8"))


def rank(case_id: str, seed: str) -> str:
    return sha256_bytes(f"{seed}\0{case_id}".encode("utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: expected JSON object")
        rows.append(row)
    return rows


def git_text(path: Path, *arguments: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *arguments],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"{path}: cannot verify pinned source: {result.stderr.strip()}")
    return result.stdout.strip()


def verify_source(data_dir: Path, relative_files: list[str], revision: str) -> dict[str, Any]:
    """Verify actual input bytes against the commit, including its root license.

    The checkout can have a newer HEAD if the specific consumed files are byte
    identical to the pin. This avoids falsely labelling a newer checkout as the
    pinned checkout while still verifying the frozen source data.
    """
    data_dir = data_dir.resolve()
    repository = Path(git_text(data_dir, "rev-parse", "--show-toplevel")).resolve()
    prefix = data_dir.relative_to(repository).as_posix()
    hashes: dict[str, str] = {}
    for relative_name in [*relative_files, "/LICENSE"]:
        path = repository / "LICENSE" if relative_name == "/LICENSE" else data_dir / relative_name
        git_path = "LICENSE" if relative_name == "/LICENSE" else f"{prefix}/{relative_name}"
        if not path.is_file():
            raise ValueError(f"missing source file: {path}")
        result = subprocess.run(["git", "-C", str(repository), "show", f"{revision}:{git_path}"],
                                capture_output=True, check=False)
        if result.returncode:
            raise ValueError(f"{git_path}: unavailable in pinned revision {revision}")
        actual = path.read_bytes()
        if actual != result.stdout:
            raise ValueError(f"{path}: bytes differ from pinned revision {revision}")
        hashes[git_path] = sha256_bytes(actual)
    return {"source_commit": revision, "observed_checkout_head": git_text(data_dir, "rev-parse", "HEAD"),
            "source_data_path": prefix, "source_sha256": dict(sorted(hashes.items())),
            "license_path": str(repository / "LICENSE")}


def v1_request_index(source_dir: Path, cases_path: Path, *, expected_count: int = 2000
                     ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_count = 0
    for category in V1_CATEGORIES:
        file_name = f"{V1_PREFIX}{category}.json"
        for row_number, row in enumerate(read_jsonl(source_dir / file_name), 1):
            question = row.get("question")
            key = request_hash(question)
            index[key].append({"origin": "v1_full_source", "file": file_name,
                               "row_number": row_number, "id": row.get("id")})
            source_count += 1
    if source_count != expected_count:
        raise ValueError(f"full BFCL V1 source expected {expected_count} rows; observed {source_count}")
    frozen_cases = read_jsonl(cases_path)
    for row_number, row in enumerate(frozen_cases, 1):
        key = request_hash(row.get("source", {}).get("question"))
        index[key].append({"origin": "v1_frozen_subset", "row_number": row_number, "id": row.get("id")})
    return dict(index), {"full_source_count": source_count, "frozen_subset_count": len(frozen_cases),
                         "unique_normalized_request_count": len(index),
                         "frozen_cases_sha256": sha256_file(cases_path), "normalization": NORMALIZATION}


def single_user_question(row: dict[str, Any]) -> str:
    question = row.get("question")
    if (not isinstance(question, list) or len(question) != 1 or
            not isinstance(question[0], list) or len(question[0]) != 1 or
            not isinstance(question[0][0], dict) or question[0][0].get("role") != "user" or
            not isinstance(question[0][0].get("content"), str)):
        raise ValueError("not exactly one user message in one turn")
    request = question[0][0]["content"]
    normalized_request(request)
    return request


def convert_case(row: dict[str, Any], category: str, row_number: int,
                 answer: Any = None, review: Mapping[str, Any] | None = None) -> dict[str, Any]:
    case_id = row.get("id")
    match = LIVE_ID.fullmatch(case_id) if isinstance(case_id, str) else None
    if not match or not case_id.startswith(category + "_"):
        raise ValueError("missing or malformed category-specific Live ID")
    request = single_user_question(row)
    functions = row.get("function")
    if not isinstance(functions, list) or any(not isinstance(item, dict) for item in functions):
        raise ValueError("invalid function catalog")
    names = [item.get("name") for item in functions]
    if any(not isinstance(name, str) or not TOOL_ID.fullmatch(name) for name in names):
        raise ValueError("invalid function name")
    if len(names) != len(set(names)) or set(names).intersection(META_IDS):
        raise ValueError("duplicate function name or meta-option collision")
    count = len(names)
    if (category == "live_multiple" and count not in (2, 3, 4)) or (
            category in ("live_simple", "live_irrelevance") and count != 1):
        raise ValueError("tool count outside selected stratum")
    if category not in QUOTAS:
        raise ValueError("unsupported category")
    calls = []
    if category != "live_irrelevance":
        if (not isinstance(answer, list) or len(answer) != 1 or
                not isinstance(answer[0], dict) or len(answer[0]) != 1):
            raise ValueError("reference is not exactly one call")
        tool_id, arguments = next(iter(answer[0].items()))
        if tool_id not in names or not isinstance(arguments, dict):
            raise ValueError("reference call does not exactly identify an offered tool")
        calls = [{"source_key": tool_id, "tool_id": tool_id, "arguments": arguments,
                  "expression": None, "resolution": "exact"}]
        gold = [tool_id]
        kind = "single_call"
    else:
        if answer is not None:
            raise ValueError("unexpected irrelevance reference")
        gold, kind = ["no_tool"], "no_call"
    overrides = {} if review is None else review.get("card_overrides", {})
    if not isinstance(overrides, dict) or set(overrides).difference(names):
        raise ValueError("card overrides must name offered tools")
    if any(not isinstance(value, str) or not value.strip() for value in overrides.values()):
        raise ValueError("card overrides must be nonempty descriptions")
    options = [{"id": name, "label": name, "description": description, "kind": "meta"}
               for name, description in META_OPTIONS]
    for function in functions:
        original = function.get("description")
        if not isinstance(original, str) or not original.strip():
            raise ValueError("missing nonempty original tool description")
        options.append({"id": function["name"], "label": function["name"],
                        "description": overrides.get(function["name"], original), "kind": "tool"})
    criteria = {option["id"]: option["description"] for option in options}
    question_file = f"BFCL_v4_{category}.json"
    catalog_hash = canonical_hash(sorted(functions, key=lambda item: item["name"]))
    prompt_request = " ".join(request.split())
    warnings = [{"code": "reviewed_card_override", "detail": f"Reviewed capability card for {name}; original schema retained."}
                for name in overrides]
    return {"id": case_id, "category": category, "kind": kind, "scope": "first_action_only",
            "score_eligible": True,
            "stratum": "one_tool_no_call" if kind == "no_call" else (
                "multi_tool_call" if count > 1 else "one_tool_call"),
            "label_source": "benchmark_irrelevance_semantically_reviewed" if kind == "no_call" else "possible_answer_semantically_reviewed",
            "source": {"question_file": question_file,
                       "answer_file": None if kind == "no_call" else f"possible_answer/{question_file}",
                       "row_number": row_number, "source_id": case_id, "question": request,
                       "original_question": row["question"], "functions": functions,
                       "ground_truth": answer, "execution_result_type": None},
            "adapter": "single_user_text",
            "jev": {"option_ids": list(criteria), "options": options,
                    "laya": {"state": f"Actions this turn: none yet\nUser request: {prompt_request}",
                             "questions": {"next": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": criteria}}},
                    "macjev": {"state": {"request": prompt_request, "actions_this_turn": [], "time_zone": "UTC"},
                               "question": {"t": "choice", "ins": INSTRUCTIONS, "crit": criteria}}},
            "gold_next_action_ids": gold, "gold_route_action_ids": META_IDS if kind == "no_call" else gold,
            "gold_call_names": [call["tool_id"] for call in calls], "gold_calls": calls, "warnings": warnings,
            "selection": {"normalized_request_sha256": request_hash(request),
                          "catalog_sha256": catalog_hash, "source_family": f"{category}:{match.group(1)}"},
            "review": None if review is None else dict(review)}


def read_review(path: Path) -> dict[str, Any]:
    review = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(review, dict) or review.get("version") != REVIEW_SCHEMA:
        raise ValueError(f"review version must be {REVIEW_SCHEMA}")
    if not isinstance(review.get("seed"), str) or not review["seed"].strip():
        raise ValueError("review requires an explicit nonempty seed")
    if set(review.get("categories", {})) != set(QUOTAS):
        raise ValueError("review must contain all three Live categories")
    for category, data in review["categories"].items():
        if not isinstance(data, dict):
            raise ValueError(f"{category}: review must be an object")
        accepted, excluded = data.get("accepted"), data.get("excluded")
        if not isinstance(accepted, dict) or not isinstance(excluded, dict):
            raise ValueError(f"{category}: accepted/excluded must be reason maps")
        if set(accepted).intersection(excluded):
            raise ValueError(f"{category}: an ID is both accepted and excluded")
        for case_id, decision in accepted.items():
            if not isinstance(case_id, str) or not isinstance(decision, dict) or not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
                raise ValueError(f"{category}: accepted IDs require a nonempty reason")
        if any(not isinstance(case_id, str) or not isinstance(reason, str) or not reason.strip()
               for case_id, reason in excluded.items()):
            raise ValueError(f"{category}: exclusions require nonempty reasons")
    return review


def collect_candidates(source_dir: Path, review: Mapping[str, Any], v1_index: Mapping[str, Any]
                       ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    candidates, audit = [], []
    source_counts = {}
    for category in QUOTAS:
        name = f"BFCL_v4_{category}.json"
        rows = read_jsonl(source_dir / name)
        source_counts[category] = len(rows)
        ids = [row.get("id") for row in rows]
        if any(not isinstance(case_id, str) for case_id in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"{name}: missing or duplicate IDs")
        decisions = review["categories"][category]
        unknown = (set(decisions["accepted"]) | set(decisions["excluded"])) - set(ids)
        if unknown:
            raise ValueError(f"{category}: unknown review IDs: {sorted(unknown)}")
        answers = {}
        if category != "live_irrelevance":
            answer_rows = read_jsonl(source_dir / "possible_answer" / name)
            if [item.get("id") for item in answer_rows] != ids:
                raise ValueError(f"{name}: answer IDs or ordering differ from questions")
            answers = {item["id"]: item.get("ground_truth") for item in answer_rows}
        for number, row in enumerate(rows, 1):
            case_id = row["id"]
            decision = decisions["accepted"].get(case_id)
            entry: dict[str, Any] = {"id": case_id, "category": category, "row_number": number}
            try:
                case = convert_case(row, category, number, answers.get(case_id), decision)
            except ValueError as error:
                if decision is not None:
                    raise ValueError(f"accepted case {case_id}: {error}") from error
                entry.update(reason="structural_exclusion", detail=str(error))
                audit.append(entry)
                continue
            entry.update(case["selection"])
            matches = v1_index.get(case["selection"]["normalized_request_sha256"], [])
            if matches:
                if decision is not None:
                    raise ValueError(f"accepted case {case_id}: request overlaps full/frozen V1 source")
                entry.update(reason="v1_request_overlap", v1_matches=matches)
            elif case_id in decisions["excluded"]:
                entry.update(reason="explicit_review_exclusion", detail=decisions["excluded"][case_id])
            elif decision is None:
                entry.update(reason="not_semantically_reviewed")
            else:
                entry["reason"] = "reviewed_candidate"
                candidates.append(case)
            audit.append(entry)
    return candidates, audit, source_counts


def select_cases(candidates: list[dict[str, Any]], quotas: Mapping[str, int], seed: str
                 ) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if set(quotas) != set(QUOTAS) or any(type(value) is not int or value < 0 for value in quotas.values()):
        raise ValueError("quotas must specify nonnegative integer counts for all three categories")
    if not sum(quotas.values()):
        raise ValueError("at least one selected case is required")
    if len({case["id"] for case in candidates}) != len(candidates):
        raise ValueError("duplicate candidate IDs")
    selected, dispositions = [], {}
    used_requests, used_families, used_catalogs = set(), set(), set()
    for category in QUOTAS:
        count = 0
        pool = sorted((case for case in candidates if case["category"] == category),
                      key=lambda case: (rank(case["id"], seed), case["id"]))
        for case in pool:
            identity = case["selection"]
            if identity["normalized_request_sha256"] in used_requests:
                reason = "duplicate_selected_request"
            elif identity["source_family"] in used_families:
                reason = "source_family_cap"
            elif identity["catalog_sha256"] in used_catalogs:
                reason = "complete_catalog_cap"
            elif count >= quotas[category]:
                reason = "quota_filled"
            else:
                reason = "selected"
                selected.append(case)
                count += 1
                used_requests.add(identity["normalized_request_sha256"])
                used_families.add(identity["source_family"])
                used_catalogs.add(identity["catalog_sha256"])
                case["selection"]["rank_sha256"] = rank(case["id"], seed)
            dispositions[case["id"]] = reason
        if count != quotas[category]:
            counts = Counter(dispositions[case["id"]] for case in pool)
            raise ValueError(f"{category}: only {count}/{quotas[category]} fit reviewed quotas and diversity controls; {dict(counts)}")
    return selected, dispositions


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                            for row in rows), encoding="utf-8")


def build(source_dir: Path, v1_source_dir: Path, v1_cases: Path, review_file: Path, output_dir: Path,
          *, quotas: Mapping[str, int] = QUOTAS, expected_source_commit: str = SOURCE_COMMIT,
          expected_v1_commit: str = V1_SOURCE_COMMIT, expected_v1_count: int = 2000) -> dict[str, Any]:
    source_files = [f"BFCL_v4_{category}.json" for category in QUOTAS]
    source_files += [f"possible_answer/BFCL_v4_{category}.json" for category in QUOTAS if category != "live_irrelevance"]
    source = verify_source(source_dir, source_files, expected_source_commit)
    v1_source = verify_source(v1_source_dir, [f"{V1_PREFIX}{category}.json" for category in V1_CATEGORIES], expected_v1_commit)
    v1_index, overlap = v1_request_index(v1_source_dir, v1_cases, expected_count=expected_v1_count)
    review = read_review(review_file)
    candidates, audit, source_counts = collect_candidates(source_dir, review, v1_index)
    cases, dispositions = select_cases(candidates, quotas, review["seed"])
    for entry in audit:
        if entry["id"] in dispositions:
            entry["reason"] = dispositions[entry["id"]]
    cases.sort(key=lambda case: (list(QUOTAS).index(case["category"]), case["selection"]["rank_sha256"], case["id"]))
    # Validate everything before creating output files, so a failed quota never
    # looks like a partial frozen evaluation set.
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "cases.jsonl", cases)
    write_jsonl(output_dir / "selection_audit.jsonl", audit)
    write_jsonl(output_dir / "exclusions.jsonl", [entry for entry in audit if entry["reason"] != "selected"])
    write_json(output_dir / "selection_review.json", review)
    (output_dir / "LICENSE").write_bytes(Path(source["license_path"]).read_bytes())
    with (output_dir / "index.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ("id", "category", "stratum", "kind", "tool_count", "gold_next_action_ids",
                  "normalized_request_sha256", "catalog_sha256", "source_family", "question_preview")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow({"id": case["id"], "category": case["category"], "stratum": case["stratum"],
                             "kind": case["kind"], "tool_count": len(case["source"]["functions"]),
                             "gold_next_action_ids": "|".join(case["gold_next_action_ids"]),
                             **{name: case["selection"][name] for name in ("normalized_request_sha256", "catalog_sha256", "source_family")},
                             "question_preview": " ".join(case["source"]["question"].split())})
    selection = {"schema": SCHEMA, "seed": review["seed"], "quotas": dict(quotas),
                 "category_order": list(QUOTAS), "rank": "SHA256(seed + NUL + source_id)",
                 "review_version": REVIEW_SCHEMA, "review_input_sha256": sha256_file(review_file),
                 "source_counts": source_counts, "reviewed_candidate_counts": dict(Counter(case["category"] for case in candidates)),
                 "audit_reason_counts": dict(sorted(Counter(entry["reason"] for entry in audit).items())),
                 "selected_ids": [case["id"] for case in cases],
                 "diversity_controls": {"normalized_requests": "at most one globally",
                                        "source_family": "at most one category + Live middle ID globally",
                                        "complete_catalog": "at most one complete catalog SHA256 globally; catalog order ignored"},
                 "v1_overlap": {**overlap, "selected_overlap_count": 0,
                                "excluded_structural_overlap_count": sum(entry["reason"] == "v1_request_overlap" for entry in audit)},
                 "reviewed_card_override_count": sum(len(case["review"].get("card_overrides", {})) for case in cases)}
    write_json(output_dir / "selection_manifest.json", selection)
    manifest = {"schema": SCHEMA, "source_repository": "https://github.com/ShishirPatil/gorilla",
                "source_tag": "BFCL V4 corpus / Live categories", "source_commit": source["source_commit"],
                "observed_checkout_head": source["observed_checkout_head"],
                "source_data_path": source["source_data_path"], "source_license": "Apache-2.0",
                "source_sha256": source["source_sha256"],
                "v1_exclusion_source": {key: value for key, value in v1_source.items() if key != "license_path"},
                "selected_count": len(cases), "score_eligible_count": len(cases),
                "category_counts": dict(Counter(case["category"] for case in cases)),
                "stratum_counts": dict(Counter(case["stratum"] for case in cases)),
                "cases_file": "cases.jsonl", "cases_sha256": sha256_file(output_dir / "cases.jsonl"),
                "index_file": "index.csv", "index_sha256": sha256_file(output_dir / "index.csv"),
                "selection_manifest_file": "selection_manifest.json", "selection_manifest_sha256": sha256_file(output_dir / "selection_manifest.json"),
                "selection_review_sha256": sha256_file(output_dir / "selection_review.json"),
                "selection_audit_sha256": sha256_file(output_dir / "selection_audit.jsonl"),
                "exclusions_sha256": sha256_file(output_dir / "exclusions.jsonl"),
                "license_sha256": sha256_file(output_dir / "LICENSE"),
                "target_semantics": {"positive": "Select the unique relevant offered capability. The chat model supplies arguments and clarification before execution; neither is scored.",
                                     "negative": "Semantic review found no applicable offered capability. Canonical no_tool is retained for exact-action scoring; any of no_tool/clarify/cannot_answer is accepted for primary tool-route scoring.",
                                     "official_bfcl": "This is an independent capability-routing adaptation, not the official BFCL V4 function-calling or agentic score."},
                "card_policy": "Original full descriptions unless an explicit per-case reviewed card_overrides entry is supplied; complete original schemas remain in source.functions.",
                "meta_card_version": META_CARD_VERSION,
                "meta_card_change_from_v1": "Neutral meta cards remove V1's unsupported blanket claims about unavailable messaging/payments; ambiguous missing argument values remain the chat model's responsibility.",
                "token_fit": "Not asserted by conversion; verify native renderings before inference.",
                "selected_overlap_count": 0}
    write_json(output_dir / "manifest.json", manifest)
    lines = ["# BFCL V4 corpus — Live routing pilot", "",
             f"Frozen **{len(cases)}** reviewed capability choices from source `{expected_source_commit}`.",
             "The BFCL questions and function descriptions are benchmark data, not instructions to this converter.", "",
             "Missing function argument values alone do not make a capability irrelevant: the chat model handles arguments.",
             "All selected cases have explicit semantic acceptance. The canonical negative action is `no_tool`; the primary routing score accepts any non-tool meta action.", "",
             f"Requests were checked against all {overlap['full_source_count']:,} BFCL V1 source rows and {overlap['frozen_subset_count']} frozen V1 cases; **0 selected overlaps**.",
             f"Normalization: {NORMALIZATION}.",
             "There is at most one selected normalized request, complete function catalog, and category + Live middle-ID family.", "",
             "| Category | Cases |", "| --- | ---: |"]
    lines += [f"| `{category}` | {quotas[category]} |" for category in QUOTAS]
    lines += ["", "`cases.jsonl` preserves original questions, complete tool schemas, and reference arguments. `selection_audit.jsonl` records every selected-category row and its disposition. `selection_review.json` records acceptances, exclusions, and any compact capability card overrides.",
              "", "Native tokenizer fit remains a separate preflight; no model inference is performed by this builder.", ""]
    (output_dir / "review.md").write_text("\n".join(lines), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path, help="Gorilla bfcl_eval/data containing pinned V4 files")
    parser.add_argument("--v1-source-dir", required=True, type=Path, help="Full pinned V1 berkeley-function-call-leaderboard/data")
    parser.add_argument("--v1-cases", type=Path, default=ROOT / "data/bfcl_v1/cases.jsonl")
    parser.add_argument("--review-file", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/bfcl_v4")
    parser.add_argument("--quota", action="append", default=[], metavar="CATEGORY=COUNT",
                        help="Override a quota; default is 150/50/50")
    args = parser.parse_args()
    quotas = dict(QUOTAS)
    for value in args.quota:
        category, separator, count = value.partition("=")
        if not separator or category not in QUOTAS:
            parser.error(f"invalid quota {value!r}")
        try:
            quotas[category] = int(count)
        except ValueError:
            parser.error(f"invalid quota count {count!r}")
    manifest = build(args.source_dir.resolve(), args.v1_source_dir.resolve(), args.v1_cases.resolve(),
                     args.review_file.resolve(), args.output_dir.resolve(), quotas=quotas)
    print(json.dumps({key: manifest[key] for key in ("source_commit", "selected_count", "category_counts", "cases_sha256", "selected_overlap_count")}, indent=2))


if __name__ == "__main__":
    main()
