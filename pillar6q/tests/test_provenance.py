from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from crowd_cinema.provenance import (
    canonical_json,
    create_manifest,
    render_credits,
    serialize_manifest,
    validate_manifest,
    verify_manifest,
)


CONTRIBUTORS = [
    {
        "contributor_id": "anon-01",
        "display_label": "Illustrative contributor 01",
        "roles": ["collation"],
    },
    {
        "contributor_id": "anon-02",
        "display_label": "Illustrative contributor 02",
        "roles": ["editorial-review"],
    },
]


def sample_manifest():
    return create_manifest(
        CONTRIBUTORS,
        [
            {
                "event_id": "event-02",
                "timestamp": "2026-02-02T10:00:00+02:00",
                "contributor_id": "anon-02",
                "role": "editorial-review",
                "contribution": "Reviewed illustrative wording",
            },
            {
                "event_id": "event-01",
                "timestamp": "2026-02-02T07:00:00Z",
                "contributor_id": "anon-01",
                "role": "collation",
                "contribution": "Compared illustrative readings",
            },
        ],
    )


class ProvenanceTests(unittest.TestCase):
    def test_checked_in_example_is_illustrative_and_verifiable(self) -> None:
        path = Path(__file__).resolve().parents[1] / "crowd_cinema_provenance.manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertIs(manifest["illustrative"], True)
        self.assertIn("No real people", manifest["notice"])
        self.assertTrue(verify_manifest(manifest))
        self.assertIn("End credits (chronological)", render_credits(manifest))

    def test_creation_is_deterministic_and_verifiable(self) -> None:
        manifest = sample_manifest()
        self.assertEqual(manifest, sample_manifest())
        self.assertTrue(verify_manifest(manifest))
        self.assertEqual(serialize_manifest(manifest), serialize_manifest(sample_manifest()))
        self.assertEqual(
            canonical_json({"z": 1, "a": "é"}),
            '{"a":"é","z":1}',
        )

    def test_rejects_duplicate_event_ids_unknown_roles_and_mismatched_role(self) -> None:
        event = {
            "event_id": "same",
            "timestamp": "2026-02-02T07:00:00Z",
            "contributor_id": "anon-01",
            "role": "collation",
            "contribution": "Illustrative work",
        }
        with self.assertRaisesRegex(ValueError, "duplicate event_id"):
            create_manifest(CONTRIBUTORS, [event, event])

        invalid_role = {**event, "role": "signature-verification"}
        with self.assertRaisesRegex(ValueError, "unsupported role"):
            create_manifest(CONTRIBUTORS, [invalid_role])

        unassigned_role = {**event, "role": "visual-design"}
        with self.assertRaisesRegex(ValueError, "not registered"):
            create_manifest(CONTRIBUTORS, [unassigned_role])

    def test_rejects_naive_timestamps_and_tampered_content(self) -> None:
        event = {
            "event_id": "event-01",
            "timestamp": "2026-02-02T07:00:00",
            "contributor_id": "anon-01",
            "role": "collation",
            "contribution": "Illustrative work",
        }
        with self.assertRaisesRegex(ValueError, "timezone"):
            create_manifest(CONTRIBUTORS, [event])

        tampered = copy.deepcopy(sample_manifest())
        tampered["events"][0]["contribution"] = "Changed after sealing"
        self.assertFalse(verify_manifest(tampered))
        with self.assertRaisesRegex(ValueError, "digest"):
            serialize_manifest(tampered)

    def test_renders_credits_chronologically_in_utc(self) -> None:
        credits = render_credits(sample_manifest())
        self.assertLess(credits.index("Compared"), credits.index("Reviewed"))
        self.assertIn("2026-02-02T07:00:00Z", credits)
        self.assertIn("2026-02-02T08:00:00Z", credits)

    def test_manifest_validation_rejects_duplicate_contributor_ids(self) -> None:
        manifest = sample_manifest()
        duplicate = copy.deepcopy(manifest)
        duplicate["contributors"].append(copy.deepcopy(duplicate["contributors"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate contributor_id"):
            validate_manifest(duplicate)


if __name__ == "__main__":
    unittest.main()
