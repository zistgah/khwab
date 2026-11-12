from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

from crowd_cinema.workflow import REQUIRED_CONTRIBUTION_TYPES, REQUIRED_FEEDBACK_TYPES

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = yaml.load(source, Loader=yaml.BaseLoader)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a YAML mapping")
    return value


class GitOpsConfigTests(unittest.TestCase):
    def test_all_github_workflows_are_valid_yaml(self) -> None:
        paths = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertGreaterEqual(len(paths), 2)
        for path in paths:
            with self.subTest(path=path.name):
                workflow = load_yaml(path)
                self.assertIn("name", workflow)
                self.assertIn("on", workflow)
                self.assertIn("jobs", workflow)

    def test_feedback_router_uses_limited_permissions_and_issue_events(self) -> None:
        workflow = load_yaml(ROOT / ".github" / "workflows" / "crowd-cinema-workflow.yml")
        self.assertEqual(workflow["permissions"]["contents"], "read")
        self.assertEqual(workflow["permissions"]["issues"], "write")
        issue_event = workflow["on"]["issues"]
        event_types = set(issue_event["types"])
        self.assertIn("opened", event_types)
        self.assertIn("edited", event_types)
        self.assertIn("reopened", event_types)
        self.assertIn("closed", event_types)
        self.assertIn("mark-closed", workflow["jobs"])
        self.assertNotIn("pull_request_target", workflow["on"])

    def test_routing_edits_notify_when_owner_changes_and_closure_is_not_gate_proof(self) -> None:
        workflow = load_yaml(ROOT / ".github" / "workflows" / "crowd-cinema-workflow.yml")
        route_steps = workflow["jobs"]["route-intake"]["steps"]
        github_script = next(
            step["with"]["script"]
            for step in route_steps
            if step.get("uses", "").startswith("actions/github-script@")
        )
        self.assertIn("routeIdentity", github_script)
        self.assertIn('context.payload.action !== "reopened"', github_script)
        self.assertIn("github.rest.issues.createComment", github_script)
        close_script = workflow["jobs"]["mark-closed"]["steps"][0]["with"]["script"]
        self.assertIn("does not by itself prove", close_script)

    def test_issue_action_python_wrapper_compiles_and_checks_router_fields(self) -> None:
        workflow = load_yaml(ROOT / ".github" / "workflows" / "crowd-cinema-workflow.yml")
        route_step = next(
            step
            for step in workflow["jobs"]["route-intake"]["steps"]
            if step.get("name") == "Route issue"
        )
        run_block = route_step["run"]
        match = re.search(r"python - <<'PY'\n(.*?)\nPY\s*$", run_block, re.DOTALL)
        self.assertIsNotNone(match, "issue action must use the documented Python route wrapper")
        compile(match.group(1), ".github/workflows/crowd-cinema-workflow.yml", "exec")

        script_step = next(
            step
            for step in workflow["jobs"]["route-intake"]["steps"]
            if step.get("uses", "").startswith("actions/github-script@")
        )
        self.assertIn(
            "toJSON(vars)",
            script_step["env"]["CROWD_CINEMA_REPOSITORY_VARS"],
        )
        self.assertIn("route.notification_variable", script_step["with"]["script"])
        self.assertIn("route.required_fields", script_step["with"]["script"])

    def test_issue_action_wrapper_routes_valid_and_incomplete_issue_events(self) -> None:
        workflow = load_yaml(ROOT / ".github" / "workflows" / "crowd-cinema-workflow.yml")
        route_step = next(
            step
            for step in workflow["jobs"]["route-intake"]["steps"]
            if step.get("name") == "Route issue"
        )
        wrapper = re.search(
            r"python - <<'PY'\n(.*?)\nPY\s*$",
            route_step["run"],
            re.DOTALL,
        ).group(1)

        valid_event = json.loads(
            (ROOT / "examples" / "workflow" / "liveness-failure.issue.json").read_text(
                encoding="utf-8"
            )
        )
        incomplete_event = json.loads(json.dumps(valid_event))
        incomplete_event["issue"]["body"] = "### Summary\n\n"

        for event, expected_status in (
            (valid_event, "routed"),
            (incomplete_event, "needs_information"),
        ):
            with self.subTest(expected_status=expected_status):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    event_path = Path(temporary_directory) / "event.json"
                    output_path = Path(temporary_directory) / "github-output.txt"
                    event_path.write_text(json.dumps(event), encoding="utf-8")
                    process = subprocess.run(
                        [sys.executable, "-c", wrapper],
                        cwd=ROOT,
                        env={
                            **os.environ,
                            "PYTHONPATH": str(ROOT / "src"),
                            "GITHUB_EVENT_PATH": str(event_path),
                            "GITHUB_OUTPUT": str(output_path),
                        },
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(process.returncode, 0, process.stderr)
                    output = output_path.read_text(encoding="utf-8").strip()
                    self.assertTrue(output.startswith("result_b64="))
                    result = json.loads(base64.b64decode(output.split("=", 1)[1]))
                    self.assertEqual(result["status"], expected_status)
                    self.assertIn("target_stage", result)

    def test_intake_forms_cover_feedback_and_contribution_routes(self) -> None:
        template_root = ROOT / ".github" / "ISSUE_TEMPLATE"
        feedback = load_yaml(template_root / "workflow_feedback.yml")
        contribution = load_yaml(template_root / "workflow_contribution.yml")

        def find_dropdown_options(form: dict, label: str) -> set[str]:
            for field in form["body"]:
                attributes = field.get("attributes", {})
                if attributes.get("label") == label:
                    return set(attributes.get("options", []))
            self.fail(f"Issue form is missing a {label!r} dropdown")

        self.assertEqual(
            find_dropdown_options(feedback, "Feedback type"),
            set(REQUIRED_FEEDBACK_TYPES),
        )
        self.assertEqual(
            find_dropdown_options(contribution, "Contribution type"),
            set(REQUIRED_CONTRIBUTION_TYPES),
        )
        for form in (feedback, contribution):
            labels = {
                field.get("attributes", {}).get("label")
                for field in form["body"]
            }
            self.assertTrue(
                {
                    "Affected artifacts",
                    "Summary",
                    "Observed behavior",
                    "Expected behavior",
                    "Evidence links",
                    "Priority",
                }.issubset(labels)
            )

    def test_pr_template_requires_traceability_and_pr_closure_reference(self) -> None:
        template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        for required_text in (
            "Fixes #",
            "Stage and artifact IDs",
            "Requirements",
            "Gate evidence",
            "Downstream / upstream impact",
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, template)

    def test_repository_ci_runs_matrix_validation(self) -> None:
        workflow = load_yaml(ROOT / ".github" / "workflows" / "crowd-cinema-ci.yml")
        python_job = workflow["jobs"]["python"]
        run_commands = "\n".join(
            step.get("run", "")
            for step in python_job.get("steps", [])
            if isinstance(step, dict)
        )
        self.assertIn("python -m crowd_cinema workflow check", run_commands)
        self.assertIn("python -m unittest discover", run_commands)


if __name__ == "__main__":
    unittest.main()
