"""Check provenance, selection balance, and duplicate protection for the review set."""

from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.select_eval_subset import (
    DEFAULT_INPUT,
    QUOTAS,
    baseline_summary,
    build,
    normalized_request,
    select_cases,
)


def case(case_id: str, category: str, question: str, *, gold: str = "tool_a",
         tools: tuple[str, ...] = ("tool_a",), warnings: list[dict] | None = None,
         score_eligible: bool = True, kind: str = "single_call", row_number: int = 1) -> dict:
    return {
        "id": case_id, "category": category, "kind": kind,
        "score_eligible": score_eligible, "warnings": [] if warnings is None else warnings,
        "source": {"question": question, "row_number": row_number,
                   "ground_truth": {gold: {}} if kind == "single_call" else None},
        "jev": {"option_ids": ["no_tool", "clarify", "cannot_answer", *tools],
                "options": [{"id": "no_tool", "kind": "meta"},
                            {"id": "clarify", "kind": "meta"},
                            {"id": "cannot_answer", "kind": "meta"},
                            *({"id": tool, "kind": "tool"} for tool in tools)],
                "laya": {"state": f"User request: {question}",
                         "questions": {"next": {"type": "choice", "criteria": {tool: "Example" for tool in tools}}}}},
        "gold_next_action_ids": [gold],
    }


def write_parent(directory: Path, cases: list[dict], *, good_hash: bool = True) -> Path:
    input_path = directory / "cases.jsonl"
    content = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in cases)
    input_path.write_text(content, encoding="utf-8")
    actual_hash = hashlib.sha256(content.encode()).hexdigest()
    manifest = {"schema": "bfcl-v1-jev-next-action/v1", "source_commit": "pinned-example-commit",
                "source_repository": "https://example.test/bfcl", "source_tag": "v1.0",
                "source_license": "Apache-2.0", "cases_sha256": actual_hash if good_hash else "bad",
                "converted_count": len(cases)}
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return input_path


class SelectEvalSubsetTests(unittest.TestCase):
    def test_deterministic_selection_and_global_request_dedup(self) -> None:
        rows = [
            case("multi_a", "multiple_function", "Calculate total.", tools=("tool_a", "tool_b"), row_number=1),
            case("rel_a", "relevance", "  CALCULATE   TOTAL. ", gold="no_tool", kind="no_call", row_number=1),
            case("rel_b", "relevance", "Explain a word.", gold="no_tool", kind="no_call", row_number=2),
            case("rel_warning", "relevance", "Weather now?", gold="no_tool",
                 kind="no_call", warnings=[{"code": "bad"}], row_number=3),
            case("rest_weak", "rest", "Fetch a URL.", score_eligible=False),
            case("parallel", "parallel_function", "Compute two things.", kind="parallel_first_choice"),
        ]
        quotas = {"multiple_function": 1, "relevance": 1}
        first, diagnostics = select_cases(rows, quotas)
        second, _ = select_cases(list(reversed(rows)), quotas)
        self.assertEqual([item["id"] for item in first], ["multi_a", "rel_b"])
        self.assertEqual([item["id"] for item in second], [item["id"] for item in first])
        self.assertEqual(len({normalized_request(item) for item in first}), 2)
        self.assertEqual(diagnostics["eligibility_counts"]["conversion_warning"], 1)
        self.assertEqual(diagnostics["eligibility_counts"]["not_score_eligible"], 1)
        self.assertEqual(diagnostics["eligibility_counts"]["non_unique_first_action"], 1)
        self.assertEqual(diagnostics["selection_skipped_duplicate_requests"]["relevance"], 1)

    def test_output_preserves_cases_and_records_parent_hash(self) -> None:
        rows = [case("multi", "multiple_function", "Find the record.", tools=("tool_a", "tool_b")),
                case("rel", "relevance", "Explain this concept.", gold="no_tool", kind="no_call")]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent_dir = root / "parent"
            parent_dir.mkdir()
            input_path = write_parent(parent_dir, rows)
            output = root / "subset"
            manifest = build(input_path, output, {"multiple_function": 1, "relevance": 1})
            selected = [json.loads(line) for line in (output / "cases.jsonl").read_text().splitlines()]
            self.assertEqual(selected, rows)
            self.assertEqual(manifest["source_commit"], "pinned-example-commit")
            self.assertEqual(manifest["parent_corpus"]["cases_sha256"], hashlib.sha256(input_path.read_bytes()).hexdigest())
            self.assertEqual(manifest["cases_sha256"], hashlib.sha256((output / "cases.jsonl").read_bytes()).hexdigest())
            self.assertEqual(manifest["baseline_by_stratum"]["one_tool_no_call"]["count"], 1)
            self.assertEqual(manifest["baseline_by_stratum"]["multi_tool_call"]["first_offered_tool_correct"], 1)
            with (output / "index.csv").open(newline="") as stream:
                self.assertEqual([row["id"] for row in csv.DictReader(stream)], ["multi", "rel"])
            review = (output / "review.md").read_text()
            self.assertIn("BFCL's relevance category", review)
            self.assertIn("`multi`", review)
            self.assertIn("`rel`", review)

    def test_bad_parent_hash_and_unfillable_quota_leave_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent_dir = root / "parent"
            parent_dir.mkdir()
            input_path = write_parent(parent_dir, [case("simple", "simple", "Add numbers.")], good_hash=False)
            output = root / "subset"
            with self.assertRaisesRegex(ValueError, "cases_sha256"):
                build(input_path, output, {"simple": 1})
            self.assertFalse(output.exists())
            write_parent(parent_dir, [case("simple", "simple", "Add numbers.")])
            with self.assertRaisesRegex(ValueError, "quota 2"):
                build(input_path, output, {"simple": 2})
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError, "different paths"):
                build(input_path, parent_dir, {"simple": 1})

    def test_review_exclusions_and_relevance_allowlist_are_recorded(self) -> None:
        rows = [case("multi_a", "multiple_function", "Get account A.", tools=("tool_a", "tool_b"), row_number=1),
                case("multi_b", "multiple_function", "Get account B.", tools=("tool_a", "tool_b"), row_number=2),
                case("rel_a", "relevance", "Give the current price.", gold="no_tool", kind="no_call", row_number=1),
                case("rel_b", "relevance", "Explain the term.", gold="no_tool", kind="no_call", row_number=2),
                case("simple_a", "simple", "Explain triangles.", row_number=1),
                case("simple_b", "simple", "Calculate a triangle area.", row_number=2)]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent_dir = root / "parent"
            parent_dir.mkdir()
            input_path = write_parent(parent_dir, rows)
            review_path = root / "review.json"
            review_path.write_text(json.dumps({"exclude_ids": {"multi_a": "incorrect source answer"},
                                               "relevance_allowlist": ["rel_b"],
                                               "positive_allowlist": {"simple": ["simple_b"]}}), encoding="utf-8")
            output = root / "subset"
            manifest = build(input_path, output, {"multiple_function": 1, "relevance": 1, "simple": 1},
                             selection_review_file=review_path)
            selected = [json.loads(line)["id"] for line in (output / "cases.jsonl").read_text().splitlines()]
            self.assertEqual(selected, ["multi_b", "rel_b", "simple_b"])
            self.assertEqual(manifest["selection_review"]["sha256"], hashlib.sha256(review_path.read_bytes()).hexdigest())
            self.assertEqual(manifest["selection_review"]["relevance_allowlist_count"], 1)
            self.assertEqual(manifest["selection_review"]["positive_allowlist_counts"], {"simple": 1})
            self.assertEqual(manifest["exclusions"]["explicit_review_exclusions"],
                             {"multi_a": "incorrect source answer"})
            self.assertEqual(manifest["exclusions"]["eligibility_counts"]["outside_reviewed_relevance_allowlist"], 1)
            self.assertEqual(manifest["exclusions"]["eligibility_counts"]["outside_reviewed_positive_allowlist"], 1)
            review_path.write_text(json.dumps({"relevance_allowlist": ["rel_a"]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "quota 2"):
                build(input_path, root / "other", {"relevance": 2}, selection_review_file=review_path)
            review_path.write_text(json.dumps({"positive_allowlist": {"simple": ["rel_a"]}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not in simple"):
                build(input_path, root / "other", {"simple": 1}, selection_review_file=review_path)


@unittest.skipUnless(DEFAULT_INPUT.is_file(), "Full converted BFCL v1 corpus is unavailable")
class FullCorpusSelectionTests(unittest.TestCase):
    def test_250_cases_have_balanced_one_tool_strata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(QUOTAS, {"multiple_function": 120, "executable_multiple_function": 30,
                                      "relevance": 50, "simple": 35, "executable_simple": 15})
            manifest = build(DEFAULT_INPUT, Path(temporary))
            self.assertEqual(manifest["selected_count"], 250)
            self.assertEqual(manifest["selected_category_counts"], QUOTAS)
            baseline = manifest["baseline_by_stratum"]
            self.assertEqual([baseline[label]["count"] for label in
                              ("multi_tool_call", "one_tool_call", "one_tool_no_call")], [150, 50, 50])
            with (Path(temporary) / "cases.jsonl").open(encoding="utf-8") as stream:
                cases = [json.loads(line) for line in stream]
            self.assertEqual(len({normalized_request(item) for item in cases}), 250)
            self.assertTrue(all(item["warnings"] == [] and item["score_eligible"] for item in cases))
            self.assertEqual(baseline_summary(cases), baseline)


if __name__ == "__main__":
    unittest.main()
