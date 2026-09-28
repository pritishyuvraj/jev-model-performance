"""Checks for BFCL v1 conversion semantics and pinned-source edge cases."""

from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.convert_bfcl_v1 import (
    CATEGORIES,
    SOURCE_COMMIT,
    build,
    convert_case,
    parse_executable_call,
    resolve_reference_key,
)


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / ".cache" / "bfcl-v1" / "berkeley-function-call-leaderboard" / "data"


class ConverterUnitTests(unittest.TestCase):
    def test_no_call_and_weak_rest_are_distinct(self) -> None:
        chatable = convert_case({"question": "Explain this", "function": ""}, "chatable", 7)
        self.assertEqual(chatable["id"], "chatable_row_0007")
        self.assertIsNone(chatable["source"]["source_id"])
        self.assertEqual(chatable["gold_next_action_ids"], ["no_tool"])
        self.assertEqual(chatable["jev"]["option_ids"], ["no_tool", "clarify", "cannot_answer"])
        self.assertTrue(chatable["score_eligible"])

        rest = convert_case({"id": "rest_0", "question": "Fetch the record",
                             "function": {"name": "requests.get", "description": "Fetch by URL"}}, "rest", 1)
        self.assertEqual(rest["gold_next_action_ids"], ["requests.get"])
        self.assertEqual(rest["gold_calls"], [])
        self.assertFalse(rest["score_eligible"])
        self.assertEqual(rest["warnings"][0]["code"], "weak_inferred_label")

    def test_parallel_repeated_calls_keep_order_and_multiplicity(self) -> None:
        row = {"id": "parallel_function_4", "question": "Compute twice",
               "function": {"name": "calculate_bmi", "description": "Compute BMI"}}
        answer = {"calculate_bmi 1": {"weight": [80]},
                  "calculate_bmi 2": {"weight": [60]}}
        case = convert_case(row, "parallel_function", 5, answer)
        self.assertEqual(case["gold_call_names"], ["calculate_bmi", "calculate_bmi"])
        self.assertEqual(case["gold_next_action_ids"], ["calculate_bmi"])
        self.assertEqual([call["source_key"] for call in case["gold_calls"]], list(answer))
        self.assertEqual(case["source"]["ground_truth"], answer)
        self.assertEqual(case["jev"]["laya"]["questions"]["next"]["criteria"].keys(),
                         case["jev"]["macjev"]["question"]["crit"].keys())

    def test_executable_reference_is_parsed_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "would_have_run"
            expression = f"helper(__import__('os').system('touch {marker}'))"
            self.assertEqual(parse_executable_call(expression), "helper")
            row = {"id": "executable_simple_test", "question": "Use helper",
                   "function": {"name": "helper", "description": "Do work"},
                   "ground_truth": [expression]}
            case = convert_case(row, "executable_simple", 1)
            self.assertFalse(marker.exists())
            self.assertEqual(case["gold_next_action_ids"], ["helper"])
            self.assertEqual(case["gold_calls"][0]["expression"], expression)
            with self.assertRaises(ValueError):
                parse_executable_call("__import__('os').system('echo unsafe')")

    def test_unmatched_reference_fails_instead_of_guessing(self) -> None:
        with self.assertRaises(ValueError):
            resolve_reference_key("unrelated", ["alpha", "beta"], "multiple_function_test")
        with self.assertRaises(ValueError):
            resolve_reference_key("find_closest", ["different_tool"], "simple_363")


@unittest.skipUnless(SOURCE.is_dir(), "Pinned BFCL v1 checkout is unavailable")
class PinnedSourceTests(unittest.TestCase):
    def test_all_categories_and_known_answer_anomalies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = build(SOURCE, output)
            self.assertEqual(manifest["source_commit"], SOURCE_COMMIT)
            self.assertEqual(manifest["converted_count"], 2000)
            self.assertEqual(manifest["score_eligible_count"], 1930)
            self.assertEqual(set(manifest["category_counts"]), set(CATEGORIES))
            self.assertEqual(manifest["category_counts"]["rest"], 70)
            self.assertEqual(manifest["warning_counts"]["known_single_tool_key_repair"], 2)
            self.assertEqual(manifest["warning_counts"]["stray_answer_field"], 1)
            self.assertEqual(hashlib.sha256((output / "cases.jsonl").read_bytes()).hexdigest(),
                             manifest["cases_sha256"])

            with (output / "cases.jsonl").open(encoding="utf-8") as stream:
                cases = [json.loads(line) for line in stream]
            lookup = {case["id"]: case for case in cases}
            self.assertEqual(len(lookup), 2000)
            self.assertEqual(lookup["simple_363"]["gold_next_action_ids"],
                             ["restaurant_search.find_closest"])
            self.assertEqual(lookup["javascript_41"]["gold_next_action_ids"], ["queue_1"])
            self.assertEqual(len(lookup["parallel_multiple_function_179"]["gold_calls"]), 4)
            self.assertIn("deck", lookup["parallel_multiple_function_179"]["source"]["ground_truth"])
            self.assertEqual(lookup["parallel_function_4"]["gold_call_names"],
                             ["calculate_bmi", "calculate_bmi"])
            self.assertEqual(lookup["sql_15"]["kind"], "sequential_first_choice")
            self.assertEqual(lookup["sql_15"]["gold_call_names"], ["sql.execute", "sql.execute"])
            self.assertEqual(lookup["chatable_row_0001"]["source"]["source_id"], None)
            self.assertFalse(lookup["rest_0"]["score_eligible"])
            self.assertTrue(all(case["score_eligible"] for case in cases if case["category"] != "rest"))

            with (output / "index.csv").open(newline="") as stream:
                index = list(csv.DictReader(stream))
            self.assertEqual(len(index), 2000)
            self.assertEqual(index[0]["id"], cases[0]["id"])
            self.assertEqual(next(row for row in index if row["id"] == "rest_0")["score_eligible"], "false")
            review = (output / "review.md").read_text()
            for case_id in ("parallel_multiple_function_179", "chatable_row_0001", "rest_0"):
                self.assertIn(f"`{case_id}`", review)


if __name__ == "__main__":
    unittest.main()
