from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "crowd_cinema_spec.schema.yaml"
MINIMUM_SPEC_PATH = ROOT / "examples" / "shot.json"
FULL_SPEC_PATH = ROOT / "examples" / "full_production_spec.json"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def schema_document() -> dict:
    return load_json(SCHEMA_PATH)


def full_schema_fixture() -> dict:
    """Illustrative structural fixture with no asserted signatures or media scores."""
    return {
        "schema_version": "1.0",
        "platform": {"name": "illustrative-local", "version": "1"},
        "project": {
            "project_id": "illustrative-project",
            "title": "Illustrative scene",
            "genre": "CANONICAL_CLASSICAL",
        },
        "source_lineage": {
            "sources": [
                {
                    "source_id": "illustrative-source",
                    "uri": "urn:example:crowd-cinema:source",
                    "source_type": "edition",
                    "relationship": "canonical_basis",
                }
            ],
            "canonical_basis_source_ids": ["illustrative-source"],
        },
        "scenes": [
            {
                "scene_id": "illustrative-scene",
                "title": "Illustrative scene",
                "shots": [
                    {
                        "shot_id": "illustrative-shot",
                        "genre": "CANONICAL_CLASSICAL",
                        "duration_sec": 12,
                        "start_sec": 0,
                        "end_sec": 12,
                        "keyframes": [
                            {
                                "keyframe_id": "illustrative-start",
                                "role": "start",
                                "artifact_uri": "illustrative://keyframes/start",
                            },
                            {
                                "keyframe_id": "illustrative-end",
                                "role": "end",
                                "artifact_uri": "illustrative://keyframes/end",
                            },
                        ],
                        "foreground_action": "A traveler pauses at a threshold.",
                        "secondary_action": "A companion waits nearby.",
                        "crowd_action": "Distant figures pass along the path.",
                    }
                ],
            }
        ],
        "render_tasks": [
            {
                "task_id": "illustrative-render-task",
                "shot_id": "illustrative-shot",
                "created_at": "2026-01-15T12:00:00Z",
                "provider": {
                    "provider_id": "illustrative-provider",
                    "provider_type": "unknown",
                },
                "takes": [],
            }
        ],
        "findings": [
            {
                "finding_id": "illustrative-liveness-finding",
                "finding_type": "liveness",
                "subject_id": "illustrative-shot",
                "status": "not_run",
                "description": "No liveness assessment has been performed.",
            }
        ],
        "vote_policy": {
            "quorum": {"minimum_votes": 0},
            "tie_break": "no_winner",
        },
        "votes": [],
        "timeline": {"clips": []},
        "localizations": [
            {
                "language_tag": "en",
                "language_group": "global",
                "script": "Latn",
                "translation_status": "not_started",
                "cues": [],
            }
        ],
        "provenance": {"contributors": [], "events": []},
        "safety_report": {"method": "checklist", "hazards": []},
    }


class SpecSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = schema_document()
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    def assert_valid(self, instance: dict, message: str = "") -> None:
        def leaf_errors(errors):
            for error in errors:
                if error.context:
                    yield from leaf_errors(error.context)
                else:
                    yield error

        errors = sorted(
            leaf_errors(self.validator.iter_errors(instance)),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if errors:
            details = []
            for error in errors[:6]:
                path = ".".join(str(part) for part in error.path) or "<root>"
                explanation = error.message
                if len(explanation) > 160:
                    explanation = explanation[:157] + "..."
                details.append(f"{path} ({error.validator}): {explanation}")
            remainder = len(errors) - len(details)
            if remainder:
                details.append(f"and {remainder} more validation error(s)")
            self.fail(f"{message}: {'; '.join(details)}" if message else "; ".join(details))

    def assert_invalid(self, instance: dict, message: str = "") -> None:
        errors = list(self.validator.iter_errors(instance))
        self.assertTrue(errors, message or "Expected the schema to reject the specimen")

    def test_schema_is_valid_draft_2020_12(self) -> None:
        self.assertEqual(
            self.schema.get("$schema"),
            "https://json-schema.org/draft/2020-12/schema",
        )
        Draft202012Validator.check_schema(self.schema)

    def test_expanded_schema_declares_each_production_section(self) -> None:
        document = self.schema["$defs"]["pillar6qDocument"]
        for field in (
            "source_lineage",
            "scenes",
            "render_tasks",
            "findings",
            "vote_policy",
            "votes",
            "timeline",
            "localizations",
            "provenance",
            "safety_report",
        ):
            with self.subTest(field=field):
                self.assertIn(
                    field,
                    document["properties"],
                    f"expanded schema is missing the {field} production section",
                )

        for definition in (
            "source",
            "shot",
            "renderTake",
            "finding",
            "vote",
            "timelineClip",
            "localization",
            "cue",
            "provenance",
            "hazard",
        ):
            with self.subTest(definition=definition):
                self.assertIn(
                    definition,
                    self.schema["$defs"],
                    f"expanded schema is missing the {definition} definition",
                )

    def test_minimum_and_full_project_specimens_validate(self) -> None:
        self.assert_valid(
            load_json(MINIMUM_SPEC_PATH),
            "examples/shot.json must remain a valid minimum shot specimen",
        )
        self.assert_valid(
            load_json(FULL_SPEC_PATH),
            "examples/full_production_spec.json must validate as the full project specimen",
        )

    def test_canonical_and_speculative_lineage_are_distinct_valid_cases(self) -> None:
        canonical = full_schema_fixture()
        self.assert_valid(canonical, "canonical lineage fixture should be valid")

        speculative = copy.deepcopy(canonical)
        speculative["project"]["genre"] = "SPECULATIVE_ALTERNATE"
        speculative["project"]["classification_disclosure"] = (
            "This scene is an illustrative invented alternate."
        )
        speculative["source_lineage"].pop("canonical_basis_source_ids")
        speculative["source_lineage"]["speculative_disclosure"] = (
            "The scene is not asserted to be supported by the listed source."
        )
        speculative["scenes"][0]["shots"][0]["genre"] = "SPECULATIVE_ALTERNATE"
        self.assert_valid(speculative, "speculative lineage with disclosure should be valid")

        missing_basis = copy.deepcopy(canonical)
        missing_basis["source_lineage"]["canonical_basis_source_ids"] = []
        self.assert_invalid(
            missing_basis,
            "canonical projects must not pass without a canonical source basis",
        )

        missing_disclosure = copy.deepcopy(speculative)
        del missing_disclosure["source_lineage"]["speculative_disclosure"]
        self.assert_invalid(
            missing_disclosure,
            "speculative projects must not pass without a speculative disclosure",
        )

    def test_shot_duration_bounds_and_integer_shape_are_enforced(self) -> None:
        base = load_json(MINIMUM_SPEC_PATH)
        for duration in (9, 16, 12.5, True):
            with self.subTest(duration=duration):
                invalid = copy.deepcopy(base)
                invalid["duration_sec"] = duration
                self.assert_invalid(invalid, f"duration_sec={duration!r} must be rejected")

        for duration in (10, 15):
            with self.subTest(duration=duration):
                valid = copy.deepcopy(base)
                valid["duration_sec"] = duration
                self.assert_valid(valid)

    def test_secondary_and_crowd_directives_are_mandatory(self) -> None:
        base = load_json(MINIMUM_SPEC_PATH)
        for field in ("secondary_action", "crowd_action"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(base)
                del invalid[field]
                self.assert_invalid(invalid, f"{field} must be required")

        modern = full_schema_fixture()
        for field in ("secondary_action", "crowd_action"):
            with self.subTest(modern_field=field):
                invalid = copy.deepcopy(modern)
                del invalid["scenes"][0]["shots"][0][field]
                self.assert_invalid(invalid, f"modern shot must require {field}")

    def test_source_uri_and_canonical_source_linkage_are_constrained(self) -> None:
        invalid_uri = copy.deepcopy(full_schema_fixture())
        invalid_uri["source_lineage"]["sources"][0]["uri"] = ""
        self.assert_invalid(invalid_uri, "source URI must be non-empty")

        invalid_type = copy.deepcopy(full_schema_fixture())
        invalid_type["source_lineage"]["sources"][0]["source_type"] = "unlisted-source-type"
        self.assert_invalid(invalid_type, "source_type must use the declared source values")

        invalid_source_id = copy.deepcopy(full_schema_fixture())
        invalid_source_id["source_lineage"]["sources"][0]["source_id"] = ""
        self.assert_invalid(invalid_source_id, "source identifiers must be non-empty")

        invalid_linkage = copy.deepcopy(full_schema_fixture())
        invalid_linkage["source_lineage"]["canonical_basis_source_ids"] = []
        self.assert_invalid(
            invalid_linkage,
            "canonical source linkage must contain at least one source id",
        )

    def test_vote_timeline_and_localization_shapes_are_constrained(self) -> None:
        for field, bad_value in (
            ("render_tasks", {}),
            ("findings", {}),
            ("vote_policy", []),
            ("votes", {}),
            ("timeline", []),
            ("localizations", {}),
        ):
            with self.subTest(field=field):
                invalid = copy.deepcopy(full_schema_fixture())
                invalid[field] = bad_value
                self.assert_invalid(invalid, f"{field} must use its declared shape")

        invalid_take = copy.deepcopy(full_schema_fixture())
        invalid_take["render_tasks"][0]["takes"] = [{"take_id": "incomplete-take"}]
        self.assert_invalid(invalid_take, "render takes must satisfy their declared shape")

        invalid_finding = copy.deepcopy(full_schema_fixture())
        invalid_finding["findings"][0] = {"finding_type": "liveness"}
        self.assert_invalid(invalid_finding, "liveness findings must satisfy their declared shape")

        invalid_vote = copy.deepcopy(full_schema_fixture())
        invalid_vote["votes"] = [
            {
                "vote_id": "illustrative-vote",
                "take_id": "illustrative-take",
                "identity_id": "illustrative-identity",
                "choice": "maybe",
                "cast_at": "2026-01-15T12:00:00Z",
            }
        ]
        self.assert_invalid(invalid_vote, "vote choice outside the declared enum must fail")

        invalid_clip = copy.deepcopy(full_schema_fixture())
        invalid_clip["timeline"]["clips"] = [{"pts": "not-an-integer"}]
        self.assert_invalid(invalid_clip, "malformed timeline clip must fail")

        invalid_localization = copy.deepcopy(full_schema_fixture())
        invalid_localization["localizations"][0]["language_tag"] = "en/us"
        self.assert_invalid(
            invalid_localization,
            "malformed language tags must fail localization validation",
        )

        invalid_hazard = copy.deepcopy(full_schema_fixture())
        invalid_hazard["safety_report"]["hazards"] = [
            {
                "hazard_id": "illustrative-hazard",
                "hazard": "Illustrative hazard",
                "severity": 6,
                "likelihood": 1,
                "mitigation": "No real assessment is represented.",
            }
        ]
        self.assert_invalid(invalid_hazard, "out-of-range safety ratings must fail")

    def test_unknown_fields_are_rejected_at_document_and_shot_levels(self) -> None:
        unknown_document_field = copy.deepcopy(full_schema_fixture())
        unknown_document_field["unreviewed_extension"] = True
        self.assert_invalid(unknown_document_field, "unknown document fields must fail")

        unknown_shot_field = copy.deepcopy(full_schema_fixture())
        unknown_shot_field["scenes"][0]["shots"][0]["unreviewed_extension"] = True
        self.assert_invalid(unknown_shot_field, "unknown shot fields must fail")


if __name__ == "__main__":
    unittest.main()
