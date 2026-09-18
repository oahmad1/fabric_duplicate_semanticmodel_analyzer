from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "semantic_model_duplicate_finder.py"
SAMPLE_PATH = ROOT / "samples" / "semantic_models.sample.json"
DUMMY_PATH = ROOT / "samples" / "dummy_semantic_models.json"

spec = importlib.util.spec_from_file_location("semantic_model_duplicate_finder", MODULE_PATH)
scanner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


class SemanticModelDuplicateFinderTests(unittest.TestCase):
    def sample_signatures(self):
        payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
        return [scanner.build_signature(model, payload.get("warnings", [])) for model in payload["models"]]

    def test_exact_duplicate_pair_ranks_first(self):
        matches = scanner.find_matches(
            self.sample_signatures(),
            min_score=0.60,
            duplicate_threshold=0.85,
            overlap_threshold=0.65,
            top=10,
        )

        self.assertGreaterEqual(len(matches), 2)
        first = matches[0]
        self.assertEqual(first["classification"], "likely_duplicate")
        self.assertEqual(first["left"]["modelId"], "sales-certified")
        self.assertEqual(first["right"]["modelId"], "sales-certified-copy")
        self.assertAlmostEqual(first["duplicateScore"], 1.0)

    def test_extended_copy_is_high_overlap(self):
        matches = scanner.find_matches(
            self.sample_signatures(),
            min_score=0.60,
            duplicate_threshold=0.85,
            overlap_threshold=0.65,
            top=10,
        )

        ids = {(match["left"]["modelId"], match["right"]["modelId"]): match for match in matches}
        overlap = ids[("sales-certified", "sales-department-mart")]
        self.assertEqual(overlap["classification"], "high_overlap")
        self.assertGreaterEqual(overlap["overlapScore"], 0.80)

    def test_unrelated_model_is_filtered(self):
        matches = scanner.find_matches(
            self.sample_signatures(),
            min_score=0.60,
            duplicate_threshold=0.85,
            overlap_threshold=0.65,
            top=10,
        )

        compared_ids = {
            frozenset((match["left"]["modelId"], match["right"]["modelId"]))
            for match in matches
        }
        self.assertNotIn(frozenset(("sales-certified", "hr-headcount")), compared_ids)

    def test_markdown_renderer_outputs_table(self):
        matches = scanner.find_matches(
            self.sample_signatures(),
            min_score=0.60,
            duplicate_threshold=0.85,
            overlap_threshold=0.65,
            top=10,
        )

        markdown = scanner.render_markdown(matches)
        self.assertIn("| Classification | Confidence | Duplicate |", markdown)
        self.assertIn("likely_duplicate", markdown)
        self.assertIn("## Common objects", markdown)
        self.assertIn("`sales[total sales]`", markdown)

    def test_json_result_includes_common_object_lists(self):
        matches = scanner.find_matches(
            self.sample_signatures(),
            min_score=0.60,
            duplicate_threshold=0.85,
            overlap_threshold=0.65,
            top=10,
        )

        first = matches[0]
        self.assertIn("commonObjects", first)
        self.assertIn("sales", first["commonObjects"]["tables"]["items"])
        self.assertIn("sales[total sales]", first["commonObjects"]["measures"]["items"])
        self.assertIn("sales[salesamount] (decimal)", first["commonObjects"]["columns"]["items"])

    def test_html_renderer_outputs_common_object_lists(self):
        matches = scanner.find_matches(
            self.sample_signatures(),
            min_score=0.60,
            duplicate_threshold=0.85,
            overlap_threshold=0.65,
            top=10,
        )

        html = scanner.render_html(matches)
        self.assertIn("<!doctype html>", html)
        self.assertIn("Semantic Model Duplicate Finder Report", html)
        self.assertIn("Common tables", html)
        self.assertIn("sales[total sales]", html)

    def test_rich_dummy_inventory_expected_outcome(self):
        payload = json.loads(DUMMY_PATH.read_text(encoding="utf-8"))
        signatures = [scanner.build_signature(model, payload.get("warnings", [])) for model in payload["models"]]
        matches = scanner.find_matches(
            signatures,
            min_score=0.60,
            duplicate_threshold=0.85,
            overlap_threshold=0.65,
            top=10,
        )

        by_pair = {
            frozenset((match["left"]["modelId"], match["right"]["modelId"])): match
            for match in matches
        }
        self.assertEqual(len(matches), 3)
        self.assertEqual(
            by_pair[frozenset(("contoso-sales-certified", "contoso-sales-exec-copy"))]["classification"],
            "likely_duplicate",
        )
        self.assertEqual(
            by_pair[frozenset(("contoso-sales-certified", "contoso-sales-regional-extended"))]["classification"],
            "high_overlap",
        )
        self.assertNotIn(
            frozenset(("contoso-sales-certified", "contoso-hr-headcount")),
            by_pair,
        )


if __name__ == "__main__":
    unittest.main()
