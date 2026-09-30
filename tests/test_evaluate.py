"""Check the distinction between exact router actions and tool selection."""

from __future__ import annotations

import unittest

from inference.evaluate import dataset_run_fields, eval_schema, metrics, validate_answer


class EvaluationMetricsTests(unittest.TestCase):
    def test_v4_run_records_reviewed_contract_and_version(self) -> None:
        fields = dataset_run_fields({"schema": "bfcl-v4-live-jev-routing-subset/v1",
                                     "selection_review_sha256": "review-hash",
                                     "meta_card_version": "neutral-meta/v1"})
        self.assertEqual(fields["selection_review_sha256"], "review-hash")
        self.assertEqual(fields["meta_card_version"], "neutral-meta/v1")
        self.assertEqual(eval_schema("run", fields), "bfcl-v4-jev-eval-run/v1")
        self.assertEqual(eval_schema("summary", fields), "bfcl-v4-jev-eval-summary/v1")

    def test_existing_v1_run_contract_stays_unchanged(self) -> None:
        self.assertEqual(dataset_run_fields({"schema": "bfcl-v1-to-jev/v1"}), {})
        self.assertEqual(dataset_run_fields(None), {})
        self.assertEqual(eval_schema("run", {}), "bfcl-v1-jev-eval-run/v1")

    def test_clarify_on_a_no_call_case_selects_no_function(self) -> None:
        rows = [
            {"status": "ok", "gold_action": "no_tool", "predicted_action": "clarify", "correct": False},
            {"status": "ok", "gold_action": "tool_a", "predicted_action": "tool_a", "correct": True},
            {"status": "ok", "gold_action": "no_tool", "predicted_action": "tool_b", "correct": False},
            {"status": "error", "gold_action": "tool_c", "predicted_action": None, "correct": False},
        ]
        result = metrics(rows)
        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["tool_selection_correct"], 2)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["accuracy_all_cases"], 0.25)
        self.assertEqual(result["tool_selection_accuracy_all_cases"], 0.5)

    def test_response_must_choose_an_offered_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "unoffered"):
            validate_answer({"answers": {"next": {"type": "choice", "choice": "other",
                                                 "probabilities": {"tool_a": 1.0}}}}, ["tool_a"])


if __name__ == "__main__":
    unittest.main()
