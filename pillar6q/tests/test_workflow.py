from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from crowd_cinema.workflow import (
    WorkflowError,
    render_workflow_board,
    route_issue_event,
    validate_matrices,
    validate_workflow_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "workflow" / "crowd_cinema_workflow.json"
TRACEABILITY_PATH = ROOT / "workflow" / "requirements_traceability.json"


def issue_event(
    event_type: str,
    *,
    affected_artifacts: str = "shot:canonical-shot-001",
    priority: str = "normal",
) -> dict[str, object]:
    body = f"""### Feedback type

{event_type}

### Affected artifacts

{affected_artifacts}

### Summary

Illustrative feedback for routing tests.

### Observed behavior

The downstream review found a mismatch.

### Expected behavior

The item should satisfy its documented gate.

### Evidence links

https://example.invalid/evidence

### Priority

{priority}
"""
    return {
        "action": "opened",
        "issue": {
            "number": 17,
            "title": "Illustrative feedback",
            "body": body,
            "html_url": "https://github.com/example/project/issues/17",
            "user": {"login": "fixture-contributor"},
        },
    }


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.traceability = json.loads(TRACEABILITY_PATH.read_text(encoding="utf-8"))

    def test_manifest_and_requirement_traceability_are_consistent(self) -> None:
        self.assertEqual(validate_matrices(self.manifest, self.traceability), [])
        self.assertEqual(validate_workflow_manifest(self.manifest), [])

    def test_manifest_records_forward_stages_and_backward_feedback_routes(self) -> None:
        stages = {stage["stage_id"]: stage for stage in self.manifest["stages"]}
        route_by_type = {
            route["event_type"]: route for route in self.manifest["feedback_routes"]
        }
        self.assertIn("source_intake", stages)
        self.assertIn("post_release_feedback", stages)
        self.assertLess(
            stages["source_intake"]["order"],
            stages["post_release_feedback"]["order"],
        )
        self.assertLess(
            stages[route_by_type["liveness_failure"]["target_stage"]]["order"],
            stages["post_release_feedback"]["order"],
        )
        self.assertTrue(
            any(
                stages[route_by_type["liveness_failure"]["target_stage"]]["order"]
                < stages[source_stage]["order"]
                for source_stage in route_by_type["liveness_failure"]["source_stages"]
            )
        )

    def test_feedback_issue_routes_to_stage_owner_and_exposes_notification(self) -> None:
        routed = route_issue_event(issue_event("liveness_failure"), self.manifest)
        route = next(
            route
            for route in self.manifest["feedback_routes"]
            if route["event_type"] == "liveness_failure"
        )
        stage = next(
            stage
            for stage in self.manifest["stages"]
            if stage["stage_id"] == route["target_stage"]
        )
        role = next(
            role
            for role in self.manifest["roles"]
            if role["role_id"] == stage["owner_role"]
        )
        self.assertEqual(routed["status"], "routed")
        self.assertEqual(routed["issue_number"], 17)
        self.assertEqual(routed["target_stage"], route["target_stage"])
        self.assertEqual(routed["source_stages"], route["source_stages"])
        self.assertEqual(routed["target_role"], stage["owner_role"])
        self.assertEqual(routed["notification_variable"], role["notification_variable"])
        self.assertIn(f"workflow:stage:{route['target_stage']}", routed["labels"])
        self.assertEqual(routed["affected_artifacts"], ["shot:canonical-shot-001"])

    def test_contribution_request_routes_to_its_stage_owner(self) -> None:
        event = issue_event("general_feedback")
        event["issue"]["body"] = event["issue"]["body"].replace(
            "### Feedback type\n\ngeneral_feedback",
            "### Contribution type\n\nrender_take",
        )
        routed = route_issue_event(event, self.manifest)
        route = next(
            route
            for route in self.manifest["contribution_routes"]
            if route["contribution_type"] == "render_take"
        )
        stage = next(
            stage
            for stage in self.manifest["stages"]
            if stage["stage_id"] == route["target_stage"]
        )
        self.assertEqual(routed["status"], "routed")
        self.assertEqual(routed["route_kind"], "contribution")
        self.assertEqual(routed["event_type"], "render_take")
        self.assertEqual(routed["target_stage"], route["target_stage"])
        self.assertEqual(routed["target_role"], stage["owner_role"])
        self.assertIn("crowd-cinema:contribution", routed["labels"])
        self.assertIn("workflow:contribution:render_take", routed["labels"])

    def test_project_registration_routes_to_source_intake(self) -> None:
        event = issue_event("general_feedback")
        event["issue"]["body"] = event["issue"]["body"].replace(
            "### Feedback type\n\ngeneral_feedback",
            "### Contribution type\n\nproject_registration",
        )
        routed = route_issue_event(event, self.manifest)
        self.assertEqual(routed["status"], "routed")
        self.assertEqual(routed["route_kind"], "contribution")
        self.assertEqual(routed["event_type"], "project_registration")
        self.assertEqual(routed["target_stage"], "source_intake")
        self.assertIn("workflow:contribution:project_registration", routed["labels"])

    def test_post_release_defect_uses_typed_artifact_owner(self) -> None:
        shot_owner = next(
            item["stage_id"]
            for item in self.manifest["artifact_owners"]
            if item["artifact_type"] == "shot"
        )
        routed = route_issue_event(issue_event("release_defect"), self.manifest)
        self.assertEqual(routed["status"], "routed")
        self.assertEqual(routed["target_stage"], shot_owner)
        self.assertEqual(routed["routing_basis"], "typed_artifact_owner")

    def test_post_release_defect_with_untyped_or_cross_stage_refs_stays_in_triage(self) -> None:
        for references in (
            "shot:canonical-shot-001\nunknown",
            "shot:canonical-shot-001\nsource:recension-a",
        ):
            with self.subTest(references=references):
                routed = route_issue_event(
                    issue_event("release_defect", affected_artifacts=references),
                    self.manifest,
                )
                self.assertEqual(routed["status"], "routed")
                self.assertEqual(routed["target_stage"], "post_release_feedback")
                self.assertEqual(routed["routing_basis"], "cross_stage_triage")

    def test_incomplete_or_unknown_issue_feedback_gets_needs_information(self) -> None:
        incomplete = issue_event("not_a_feedback_type")
        incomplete["issue"]["body"] = "### Summary\n\n"
        result = route_issue_event(incomplete, self.manifest)
        self.assertEqual(result["status"], "needs_information")
        self.assertIsNone(result["target_stage"])
        self.assertIn("workflow:status:needs-information", result["labels"])
        self.assertIn("feedback_type", result["required_fields"])
        self.assertIn("summary", result["required_fields"])
        self.assertIn("priority", result["required_fields"])
        self.assertIn("Feedback type is missing or not recognized", result["route_reason"])
        self.assertIn("Observed behavior is required", result["route_reason"])

    def test_invalid_manifest_is_rejected_instead_of_silently_routed(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["feedback_routes"].pop()
        errors = validate_workflow_manifest(invalid)
        self.assertTrue(any("missing required event types" in error for error in errors))
        with self.assertRaises(WorkflowError):
            route_issue_event(issue_event("general_feedback"), invalid)

    def test_malformed_matrix_types_return_errors_instead_of_crashing(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["transitions"][0]["from_stage"] = []
        invalid["feedback_routes"][0]["source_stages"] = [[]]
        invalid["contribution_routes"][0]["target_stage"] = []
        invalid["contribution_routes"][0]["required_fields"] = [[]]
        errors = validate_workflow_manifest(invalid)
        self.assertTrue(errors)
        self.assertTrue(any("references an unknown stage" in error for error in errors))

    def test_board_embeds_checked_matrices_without_template_placeholders(self) -> None:
        board = render_workflow_board(self.manifest, self.traceability)
        self.assertNotIn("@@WORKFLOW_JSON@@", board)
        self.assertNotIn("@@TRACEABILITY_JSON@@", board)
        self.assertIn("workflow-data", board)
        self.assertIn("traceability-data", board)
        self.assertIn("snapshot", board.casefold())
        self.assertIn("contribution", board.casefold())

        unsafe_manifest = copy.deepcopy(self.manifest)
        unsafe_manifest["workflow_name"] = "<script>alert(1)</script>"
        escaped = render_workflow_board(unsafe_manifest, self.traceability)
        self.assertIn(r"\u003cscript\u003e", escaped)

    def test_checked_in_workflow_board_matches_source_matrices(self) -> None:
        board_path = ROOT / "docs" / "workflow-board.html"
        self.assertTrue(board_path.is_file(), "regenerate and check in the workflow board")
        self.assertEqual(
            board_path.read_text(encoding="utf-8"),
            render_workflow_board(self.manifest, self.traceability),
            "workflow board is stale; run `crowd-cinema workflow board` and commit the update",
        )

    def test_workflow_check_cli_reports_matrix_totals(self) -> None:
        process = subprocess.run(
            [sys.executable, "-m", "crowd_cinema", "workflow", "check"],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["stages"], len(self.manifest["stages"]))
        self.assertEqual(result["gates"], len(self.manifest["gates"]))
        self.assertEqual(result["requirements"], len(self.traceability["requirements"]))

    def test_board_cli_generates_a_standalone_html_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "workflow-board.html"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "crowd_cinema",
                    "workflow",
                    "board",
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(output_path.is_file())
            self.assertIn("traceability-data", output_path.read_text(encoding="utf-8"))

    def test_route_issue_cli_emits_json_for_the_github_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            event_path = Path(temporary_directory) / "event.json"
            event_path.write_text(
                json.dumps(issue_event("liveness_failure")),
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "crowd_cinema",
                    "workflow",
                    "route-issue",
                    "--event-path",
                    str(event_path),
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result["status"], "routed")
            self.assertEqual(result["event_type"], "liveness_failure")
            self.assertIn("notification_variable", result)


if __name__ == "__main__":
    unittest.main()
