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

    def test_v4_does_not_embed_v1_results_even_with_a_shared_case_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            row = {"case_id": "shared-case", "status": "ok", "predicted_action": "tool"}
            (directory / "bfcl_v1_old.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            (directory / "bfcl_v1_old.meta.json").write_text(
                json.dumps({"run": {"cases_sha256": "old-v1-sha"}}), encoding="utf-8"
            )

            self.assertEqual(viewer.read_results(directory, {"shared-case"}, "v4-sha", "bfcl_v4_"), [])

            (directory / "bfcl_v4_new.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            (directory / "bfcl_v4_new.meta.json").write_text(
                json.dumps({"run": {"cases_sha256": "v4-sha"}}), encoding="utf-8"
            )
            runs = viewer.read_results(directory, {"shared-case"}, "v4-sha", "bfcl_v4_")

            self.assertEqual([run["id"] for run in runs], ["new"])
            self.assertEqual(runs[0]["rows"], [row])

    def test_result_prefix_is_literal_and_rejects_globs_or_paths(self):
        for prefix in ("", "../bfcl_v4_", "bfcl_v4_*", "bfcl_v4_?"):
            with self.subTest(prefix=prefix), self.assertRaisesRegex(ValueError, "filename prefix"):
                viewer.read_results(Path("/nonexistent-viewer-results"), set(), "sha", prefix)


class ViewerRenderingTests(unittest.TestCase):
    def test_v1_default_matches_existing_html_exactly(self):
        cases = [{"id": "case-1", "source": {"question": "Triangle <area>"}}]
        runs = [{"id": "sample", "rows": []}]
        expected = viewer.HTML.replace("__CASE_JSON__", viewer.embed_json(cases), 1)
        expected = expected.replace("__RESULT_JSON__", viewer.embed_json(runs), 1)
        expected = expected.replace("__SOURCE_SHA256__", "pinned", 1)

        self.assertEqual(viewer.render_html(cases, runs, "pinned"), expected)

    def test_v4_empty_results_keep_prompt_and_gold_without_v1_branding(self):
        case = {
            "id": "live_multiple_42", "source": {"question": "Find a train", "ground_truth": "source-reference"},
            "gold_next_action_ids": ["train.find"], "jev": {"options": []},
        }
        rendered = viewer.render_html([case], [], "v4-sha", "v4")

        self.assertIn("<title>BFCL V4 · Jev prompt viewer</title>", rendered)
        self.assertIn('class="eyebrow">BFCL V4 → Jev', rendered)
        self.assertIn("Source: Berkeley Function Calling Leaderboard V4", rendered)
        self.assertIn('name="source-case-sha256" content="v4-sha"', rendered)
        self.assertIn('<script type="application/json" id="result-data">[]</script>', rendered)
        self.assertIn('"gold_next_action_ids":["train.find"]', rendered)
        self.assertIn('"ground_truth":"source-reference"', rendered)
        self.assertIn('file.name.startsWith("bfcl_v4_")', rendered)
        self.assertNotIn("BFCL V1", rendered)
        self.assertNotIn("bfcl_v1_", rendered)

    def test_custom_name_is_html_escaped_and_result_prefix_is_used(self):
        rendered = viewer.render_html([], [], "sha", "v4", 'BFCL V4 <review> & "pilot"', "pilot_v4_")

        self.assertIn("<title>BFCL V4 &lt;review&gt; &amp; &quot;pilot&quot; ·", rendered)
        self.assertIn('file.name.startsWith("pilot_v4_")', rendered)
        self.assertNotIn("<review>", rendered)


if __name__ == "__main__":
    unittest.main()
