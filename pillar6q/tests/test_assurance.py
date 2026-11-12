from __future__ import annotations

import unittest

from crowd_cinema.assurance import (
    build_hazard_report,
    deterministic_vote_winner,
    evaluate_authority_quorum,
    validate_content_safety,
    validate_shot_duration,
    validate_timeline,
)


class AssuranceTests(unittest.TestCase):
    def test_canonical_requires_valid_and_linked_sources(self) -> None:
        content = {
            "genre": "CANONICAL_CLASSICAL",
            "source_uris": ["https://example.org/edition/1"],
            "source_links": {"foreground_action": ["https://example.org/edition/1"]},
        }
        result = validate_content_safety(content)
        self.assertTrue(result["source_links_valid"])
        self.assertFalse(result["source_authenticity_verified"])

        content["source_links"] = {}
        with self.assertRaisesRegex(ValueError, "link sources"):
            validate_content_safety(content)

    def test_speculative_requires_disclosure_and_uri_links_must_be_declared(self) -> None:
        content = {
            "genre": "SPECULATIVE_ALTERNATE",
            "source_uris": ["doi:10.1234/example"],
            "speculative_disclosure": "This is an alternate retelling.",
            "source_links": {"inspiration": ["https://example.org/not-declared"]},
        }
        with self.assertRaisesRegex(ValueError, "not present"):
            validate_content_safety(content)
        content["source_links"] = {}
        self.assertTrue(validate_content_safety(content)["classification_disclosed"])
        del content["speculative_disclosure"]
        with self.assertRaisesRegex(ValueError, "speculative_disclosure"):
            validate_content_safety(content)

    def test_duration_and_timeline_invariants(self) -> None:
        self.assertEqual(validate_shot_duration(10), 10)
        with self.assertRaisesRegex(ValueError, "integer"):
            validate_shot_duration(True)
        with self.assertRaisesRegex(ValueError, "10 through 15"):
            validate_shot_duration(16)
        timeline = validate_timeline(
            [
                {"shot_id": "a", "start_sec": 0, "duration_sec": 10},
                {"shot_id": "b", "start_sec": 10, "duration_sec": 12},
            ]
        )
        self.assertEqual(timeline["total_duration_sec"], 22)
        with self.assertRaisesRegex(ValueError, "discontinuity"):
            validate_timeline(
                [
                    {"shot_id": "a", "start_sec": 0, "duration_sec": 10},
                    {"shot_id": "b", "start_sec": 11, "duration_sec": 12},
                ]
            )

    def test_quorum_and_vote_tie_break_are_deterministic(self) -> None:
        quorum = evaluate_authority_quorum([1, 2, 3], [True, False, True], 2)
        self.assertTrue(quorum["quorum_met"])
        self.assertFalse(evaluate_authority_quorum([1, 2], [True, False], 2)["quorum_met"])
        with self.assertRaisesRegex(ValueError, "duplicate approved"):
            evaluate_authority_quorum([7, 7], [True, True], 1)

        result = deterministic_vote_winner([(1, 9, 2), (2, 4, 2)])
        self.assertEqual(result["winner_id"], 4)
        self.assertEqual(result["winner_weight"], 2)
        with self.assertRaisesRegex(ValueError, "duplicate voter"):
            deterministic_vote_winner([(1, 9, 1), (1, 4, 2)])
        with self.assertRaisesRegex(ValueError, "integer"):
            deterministic_vote_winner([(True, 9, 1)])

    def test_hazard_report_is_structured_and_explicit_about_limits(self) -> None:
        report = build_hazard_report()
        self.assertEqual(report["method"], "qualitative HAZOP/FMECA-style screening")
        self.assertTrue(all(hazard["rpn"] > 0 for hazard in report["hazards"]))
        self.assertTrue(any("CBMC/Z3" in item for item in report["limitations"]))
        self.assertTrue(any("cryptographic" in item for item in report["limitations"]))


if __name__ == "__main__":
    unittest.main()
