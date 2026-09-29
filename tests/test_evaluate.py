"""Check the distinction between exact router actions and tool selection."""

from __future__ import annotations

import unittest

from inference.evaluate import metrics, validate_answer


class EvaluationMetricsTests(unittest.TestCase):
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
