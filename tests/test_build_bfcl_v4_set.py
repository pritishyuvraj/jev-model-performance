"""Checks the release boundaries that could corrupt a routing comparison."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_bfcl_v4_set as builder


def row(category: str, index: int, group: int, request: str, name: str | None = None) -> dict:
    name = name or f"tool_{category}_{index}"
    functions = [{"name": name, "description": f"Complete capability for {name}; accepts all relevant input.",
                  "parameters": {"type": "dict", "properties": {}, "required": []}}]
    if category == "live_multiple":
        functions.append({"name": f"alternative_{index}", "description": f"An unrelated alternative {index}.",
                          "parameters": {"type": "dict", "properties": {}, "required": []}})
    return {"id": f"{category}_{index}-{group}-0", "question": [[{"role": "user", "content": request}]],
            "function": functions}


def reference(source_row: dict) -> list:
    return [{source_row["function"][0]["name"]: {"argument": ["archived value"]}}]


def acceptance(*rows: dict) -> dict:
    result = {"version": builder.REVIEW_SCHEMA, "seed": "test-fixed-seed", "categories": {}}
    for category in builder.QUOTAS:
        result["categories"][category] = {"accepted": {}, "excluded": {}}
    for source_row in rows:
        category = source_row["id"].rsplit("_", 1)[0]
        result["categories"][category]["accepted"][source_row["id"]] = {
            "reason": "Reviewed complete schema and request; unique capability matches, or none is applicable."}
    return result


class BuilderUnitTests(unittest.TestCase):
    def test_normalization_catches_v1_case_width_punctuation_symbols_and_whitespace(self):
        self.assertEqual(builder.normalized_request("ＢＯＯＫ—A\nFlight! ✈"), "book a flight")
        self.assertEqual(builder.request_hash("ＢＯＯＫ—A\nFlight! ✈"), builder.request_hash("book a flight"))
        with self.assertRaisesRegex(ValueError, "empty"):
            builder.normalized_request("!! ✈")

    def test_nested_reference_retained_and_reviewed_cards_do_not_alter_archive(self):
        source_row = row("live_multiple", 1, 7, "Use the first capability")
        tool = source_row["function"][0]["name"]
        decision = {"reason": "Capability reviewed.", "card_overrides": {tool: "Reviewed compact complete capability."}}
        case = builder.convert_case(source_row, "live_multiple", 1, reference(source_row), decision)
        self.assertEqual(case["source"]["functions"], source_row["function"])
        self.assertEqual(case["source"]["ground_truth"], reference(source_row))
        self.assertEqual(case["gold_next_action_ids"], [tool])
        self.assertEqual(case["gold_calls"][0]["arguments"], {"argument": ["archived value"]})
        self.assertEqual(case["jev"]["laya"]["questions"]["next"]["criteria"][tool], decision["card_overrides"][tool])
        self.assertEqual(case["jev"]["options"][-1]["description"], source_row["function"][-1]["description"])
        self.assertEqual(case["source"]["original_question"], source_row["question"])

    def test_irrelevance_has_one_canonical_action_but_all_meta_routes(self):
        source_row = row("live_irrelevance", 2, 2, "Discuss a poem with a calendar-only tool")
        case = builder.convert_case(source_row, "live_irrelevance", 1, review={"reason": "No calendar capability is relevant."})
        self.assertEqual(case["gold_next_action_ids"], ["no_tool"])
        self.assertEqual(case["gold_route_action_ids"], builder.META_IDS)
        self.assertEqual(case["gold_calls"], [])

    def test_multiple_users_or_parallel_gold_are_ineligible(self):
        source_row = row("live_multiple", 1, 7, "Use the first capability")
        changed = copy.deepcopy(source_row)
        changed["question"][0].append({"role": "assistant", "content": "Context"})
        with self.assertRaisesRegex(ValueError, "one user"):
            builder.convert_case(changed, "live_multiple", 1, reference(source_row))
        with self.assertRaisesRegex(ValueError, "exactly one call"):
            builder.convert_case(source_row, "live_multiple", 1, reference(source_row) * 2)

    def test_selection_global_catalog_and_family_caps_and_order_independence(self):
        multiple = [row("live_multiple", 1, 1, "first unique request"),
                    row("live_multiple", 2, 1, "second unique request"),
                    row("live_multiple", 3, 3, "third unique request"),
                    row("live_multiple", 4, 4, "fourth unique request")]
        multiple[3]["function"] = list(reversed(copy.deepcopy(multiple[2]["function"])))
        simple = row("live_simple", 1, 1, "simple unique request")
        negative = row("live_irrelevance", 1, 1, "negative unique request")
        cases = [builder.convert_case(item, "live_multiple", number, reference(item), {"reason": "reviewed"})
                 for number, item in enumerate(multiple, 1)]
        cases += [builder.convert_case(simple, "live_simple", 1, reference(simple), {"reason": "reviewed"}),
                  builder.convert_case(negative, "live_irrelevance", 1, review={"reason": "reviewed"})]
        quotas = {"live_multiple": 2, "live_simple": 1, "live_irrelevance": 1}
        selected, dispositions = builder.select_cases(cases, quotas, "fixed-seed")
        second, _ = builder.select_cases(list(reversed(cases)), quotas, "fixed-seed")
        self.assertEqual([item["id"] for item in selected], [item["id"] for item in second])
        self.assertEqual(len({item["selection"]["source_family"] for item in selected}), len(selected))
        self.assertEqual(len({item["selection"]["catalog_sha256"] for item in selected}), len(selected))
        self.assertIn("source_family_cap", dispositions.values())
        self.assertIn("complete_catalog_cap", dispositions.values())
        # A matching full single-tool catalog is also capped across categories.
        negative["function"] = copy.deepcopy(simple["function"])
        conflicting = builder.convert_case(negative, "live_irrelevance", 1, review={"reason": "reviewed"})
        with self.assertRaisesRegex(ValueError, "live_irrelevance.*only 0/1"):
            builder.select_cases(cases[:-1] + [conflicting], quotas, "fixed-seed")


class BuildIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.v4 = self.directory / "v4" / "data"
        self.v1 = self.directory / "v1" / "data"
        self.v4.mkdir(parents=True)
        self.v1.mkdir(parents=True)
        self.v4.joinpath("possible_answer").mkdir()
        self.source_rows = {category: [row(category, 1, 1, f"Fresh request for {category}")]
                            for category in builder.QUOTAS}
        for category, rows in self.source_rows.items():
            name = f"BFCL_v4_{category}.json"
            builder.write_jsonl(self.v4 / name, rows)
            if category != "live_irrelevance":
                builder.write_jsonl(self.v4 / "possible_answer" / name,
                                    [{"id": item["id"], "ground_truth": reference(item)} for item in rows])
        for category in builder.V1_CATEGORIES:
            builder.write_jsonl(self.v1 / f"{builder.V1_PREFIX}{category}.json",
                                [{"id": f"v1_{category}", "question": f"Old V1 request for {category}"}])
        self.frozen = self.directory / "v1_cases.jsonl"
        builder.write_jsonl(self.frozen, [{"id": "v1_only_in_frozen", "source": {"question": "Original frozen request"}}])
        self.review_path = self.directory / "review.json"
        builder.write_json(self.review_path, acceptance(*(rows[0] for rows in self.source_rows.values())))
        self.v4_revision = self.commit(self.v4.parent)
        self.v1_revision = self.commit(self.v1.parent)
        self.output = self.directory / "output"

    def commit(self, path: Path) -> str:
        (path / "LICENSE").write_text("Apache License\nVersion 2.0\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(path), "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "commit", "-qm", "Pinned fixture"], check=True)
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()

    def build(self):
        return builder.build(self.v4, self.v1, self.frozen, self.review_path, self.output,
                             quotas={category: 1 for category in builder.QUOTAS},
                             expected_source_commit=self.v4_revision, expected_v1_commit=self.v1_revision,
                             expected_v1_count=len(builder.V1_CATEGORIES))

    def test_frozen_release_is_reproducible_and_loads_in_existing_evaluator(self):
        manifest = self.build()
        first_bytes = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.build()
        self.assertEqual(first_bytes, {path.name: path.read_bytes() for path in self.output.iterdir()})
        self.assertEqual(manifest["selected_count"], 3)
        self.assertEqual(manifest["selected_overlap_count"], 0)
        spec = importlib.util.spec_from_file_location("v4_eval_fixture", ROOT / "inference" / "evaluate.py")
        evaluator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evaluator)
        cases, loaded_manifest = evaluator.load_cases(self.output / "cases.jsonl")
        self.assertEqual(len(cases), 3)
        self.assertEqual(loaded_manifest["cases_sha256"], manifest["cases_sha256"])
        audit = builder.read_jsonl(self.output / "selection_audit.jsonl")
        self.assertEqual({item["reason"] for item in audit}, {"selected"})

    def test_unreviewed_case_cannot_silently_fill_quota(self):
        review = json.loads(self.review_path.read_text())
        review["categories"]["live_simple"]["accepted"] = {}
        builder.write_json(self.review_path, review)
        with self.assertRaisesRegex(ValueError, "live_simple.*only 0/1"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_v1_full_source_overlap_rejected_even_when_not_in_frozen_250(self):
        source_row = self.source_rows["live_multiple"][0]
        v1_name = f"{builder.V1_PREFIX}{builder.V1_CATEGORIES[0]}.json"
        builder.write_jsonl(self.v1 / v1_name, [{"id": "full_source_overlap", "question": source_row["question"][0][0]["content"].upper() + "!!!"}])
        self.v1_revision = self.commit(self.v1.parent)
        with self.assertRaisesRegex(ValueError, "overlaps full/frozen V1"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_frozen_only_request_also_excluded(self):
        source_row = self.source_rows["live_simple"][0]
        builder.write_jsonl(self.frozen, [{"id": "frozen_only", "source": {"question": source_row["question"][0][0]["content"]}}])
        with self.assertRaisesRegex(ValueError, "overlaps full/frozen V1"):
            self.build()

    def test_changed_source_or_license_fails_before_output(self):
        with (self.v4 / "BFCL_v4_live_multiple.json").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "bytes differ from pinned revision"):
            self.build()
        self.assertFalse(self.output.exists())
        # Verify that licensing bytes are part of the pinned provenance too.
        source_path = self.v4 / "BFCL_v4_live_multiple.json"
        source_path.write_text(source_path.read_text().rstrip() + "\n")
        (self.v4.parent / "LICENSE").write_text("Changed license")
        with self.assertRaisesRegex(ValueError, "LICENSE.*bytes differ"):
            self.build()


if __name__ == "__main__":
    unittest.main()
