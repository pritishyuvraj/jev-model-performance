"""Checks that offline viewer results stay tied to the selected case set."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "build_prompt_viewer.py"
SPEC = importlib.util.spec_from_file_location("build_prompt_viewer", MODULE_PATH)
viewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(viewer)


class ViewerResultsTests(unittest.TestCase):
    def test_loads_per_case_logs_and_escapes_embedded_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            row = {"case_id": "case-1", "status": "ok", "predicted_action": "tool.<script>"}
            (directory / "bfcl_v1_sample.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            (directory / "bfcl_v1_sample.meta.json").write_text(
                json.dumps({"run": {"cases_sha256": "pinned", "requested_model": "sample/model"}}),
                encoding="utf-8",
            )

            runs = viewer.read_results(directory, {"case-1"}, "pinned")

            self.assertEqual(runs[0]["rows"], [row])
            self.assertEqual(runs[0]["requested_model"], "sample/model")
            self.assertNotIn("<script>", viewer.embed_json(runs))

    def test_rejects_results_for_a_different_source_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "bfcl_v1_sample.jsonl").write_text(
                json.dumps({"case_id": "case-1", "status": "ok", "predicted_action": "tool"}) + "\n",
                encoding="utf-8",
            )
            (directory / "bfcl_v1_sample.meta.json").write_text(
                json.dumps({"run": {"cases_sha256": "other"}}), encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "different source-case SHA-256"):
                viewer.read_results(directory, {"case-1"}, "pinned")

    def test_rejects_unknown_or_duplicate_case_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "bfcl_v1_sample.jsonl"
            row = {"case_id": "case-1", "status": "ok", "predicted_action": "tool"}
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown or repeated case ID"):
                viewer.read_results(directory, {"case-1"}, "pinned")

            path.write_text(json.dumps({**row, "case_id": "other"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown or repeated case ID"):
                viewer.read_results(directory, {"case-1"}, "pinned")


if __name__ == "__main__":
    unittest.main()
