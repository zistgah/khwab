"""GitOps workflow matrices, feedback routing, and static board generation."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


class WorkflowError(ValueError):
    """Raised when a workflow manifest or traceability matrix is invalid."""


REQUIRED_FEEDBACK_TYPES = frozenset(
    {
        "source_provenance",
        "attestation_rejected",
        "canonical_mismatch",
        "storyboard_defect",
        "render_failure",
        "liveness_failure",
        "anachronism_flag",
        "vote_appeal",
        "timeline_continuity",
        "translation_correction",
        "subtitle_timing",
        "dub_audio_issue",
        "provenance_credits",
        "release_defect",
        "general_feedback",
    }
)
REQUIRED_BACKWARD_FEEDBACK_TYPES = frozenset(
    {
        "source_provenance",
        "attestation_rejected",
        "canonical_mismatch",
        "storyboard_defect",
        "render_failure",
        "liveness_failure",
        "anachronism_flag",
        "vote_appeal",
        "timeline_continuity",
        "translation_correction",
        "subtitle_timing",
        "dub_audio_issue",
        "provenance_credits",
    }
)
REQUIRED_STAGES = (
    "source_intake",
    "textual_collation",
    "adaptation",
    "shot_design",
    "volunteer_render",
    "technical_review",
    "community_selection",
    "assembly",
    "localization",
    "release_assurance",
    "release",
    "post_release_feedback",
)
REQUIRED_CONTRIBUTION_TYPES = frozenset(
    {
        "source_material",
        "transcription",
        "scholarly_review",
        "adaptation_proposal",
        "shot_blueprint",
        "render_take",
        "technical_review",
        "assembly_change",
        "localization_text",
        "voice_or_audio",
        "provenance_credit",
        "release_package",
    }
)
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
_ROLE_NOTIFICATION = re.compile(r"^CROWD_CINEMA_NOTIFY_[A-Z0-9_]+$")
_FORM_HEADING = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
_ISSUE_FORM_FIELDS = frozenset(
    {
        "summary",
        "observed_behavior",
        "expected_behavior",
        "affected_artifacts",
        "evidence_links",
        "priority",
    }
)


def _is_mapping(value: Any) -> bool:
    return isinstance(value, dict)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_json(path: str | Path) -> dict[str, Any]:
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8") as source:
        value = json.load(source)
    if not _is_mapping(value):
        raise WorkflowError(f"{source_path}: expected a JSON object")
    return value


def _string_list(value: Any, label: str, errors: list[str], allow_empty: bool = True) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return
    if not allow_empty and not value:
        errors.append(f"{label} must not be empty")
    for index, item in enumerate(value):
        if not _non_empty_string(item):
            errors.append(f"{label}[{index}] must be a non-empty string")


def validate_workflow_manifest(manifest: Any) -> list[str]:
    """Validate stage, role, gate, transition, ownership, and route references."""
    errors: list[str] = []
    if not _is_mapping(manifest):
        return ["workflow manifest must be a JSON object"]

    if manifest.get("workflow_version") != "1.0":
        errors.append("workflow_version must be '1.0'")
    if not _non_empty_string(manifest.get("workflow_name")):
        errors.append("workflow_name must be a non-empty string")

    roles_value = manifest.get("roles")
    roles: dict[str, dict[str, Any]] = {}
    if not isinstance(roles_value, list) or not roles_value:
        errors.append("roles must be a non-empty array")
    else:
        for index, role in enumerate(roles_value):
            if not _is_mapping(role):
                errors.append(f"roles[{index}] must be an object")
                continue
            role_id = role.get("role_id")
            if not isinstance(role_id, str) or not _IDENTIFIER.fullmatch(role_id):
                errors.append(f"roles[{index}].role_id must be lowercase snake_case")
                continue
            if role_id in roles:
                errors.append(f"role_id {role_id!r} is duplicated")
                continue
            roles[role_id] = role
            if not _non_empty_string(role.get("responsibility")):
                errors.append(f"roles[{index}].responsibility must be non-empty")
            notification_variable = role.get("notification_variable")
            if not isinstance(notification_variable, str) or not _ROLE_NOTIFICATION.fullmatch(
                notification_variable
            ):
                errors.append(
                    f"roles[{index}].notification_variable must name a "
                    "CROWD_CINEMA_NOTIFY_* repository variable"
                )

    stages_value = manifest.get("stages")
    stages: dict[str, dict[str, Any]] = {}
    stage_orders: set[int] = set()
    if not isinstance(stages_value, list) or not stages_value:
        errors.append("stages must be a non-empty array")
    else:
        for index, stage in enumerate(stages_value):
            if not _is_mapping(stage):
                errors.append(f"stages[{index}] must be an object")
                continue
            stage_id = stage.get("stage_id")
            if not isinstance(stage_id, str) or not _IDENTIFIER.fullmatch(stage_id):
                errors.append(f"stages[{index}].stage_id must be lowercase snake_case")
                continue
            if stage_id in stages:
                errors.append(f"stage_id {stage_id!r} is duplicated")
                continue
            stages[stage_id] = stage
            order = stage.get("order")
            if isinstance(order, bool) or not isinstance(order, int) or order < 0:
                errors.append(f"stages[{index}].order must be a non-negative integer")
            elif order in stage_orders:
                errors.append(f"stage order {order} is duplicated")
            else:
                stage_orders.add(order)
            for field in ("title", "owner_role"):
                if not _non_empty_string(stage.get(field)):
                    errors.append(f"stages[{index}].{field} must be non-empty")
            owner_role = stage.get("owner_role")
            if not isinstance(owner_role, str) or owner_role not in roles:
                errors.append(
                    f"stages[{index}].owner_role must reference a declared role"
                )
            for field in ("inputs", "outputs", "entry_gates", "exit_gates"):
                _string_list(
                    stage.get(field),
                    f"stages[{index}].{field}",
                    errors,
                    allow_empty=field in {"inputs", "outputs"},
                )

    missing_stages = set(REQUIRED_STAGES) - stages.keys()
    if missing_stages:
        errors.append("stages is missing required lifecycle phases: " + ", ".join(sorted(missing_stages)))

    gates_value = manifest.get("gates")
    gates: dict[str, dict[str, Any]] = {}
    if not isinstance(gates_value, list) or not gates_value:
        errors.append("gates must be a non-empty array")
    else:
        for index, gate in enumerate(gates_value):
            if not _is_mapping(gate):
                errors.append(f"gates[{index}] must be an object")
                continue
            gate_id = gate.get("gate_id")
            if not _non_empty_string(gate_id):
                errors.append(f"gates[{index}].gate_id must be non-empty")
                continue
            if gate_id in gates:
                errors.append(f"gate_id {gate_id!r} is duplicated")
                continue
            gates[gate_id] = gate
            gate_stage_id = gate.get("stage_id")
            if not isinstance(gate_stage_id, str) or gate_stage_id not in stages:
                errors.append(f"gates[{index}].stage_id references an unknown stage")
            if not _non_empty_string(gate.get("title")):
                errors.append(f"gates[{index}].title must be non-empty")
            gate_status = gate.get("status")
            if not isinstance(gate_status, str) or gate_status not in {
                "implemented",
                "partial",
                "planned",
            }:
                errors.append(
                    f"gates[{index}].status must be implemented, partial, or planned"
                )
            _string_list(
                gate.get("criteria"),
                f"gates[{index}].criteria",
                errors,
                allow_empty=False,
            )
            verification = gate.get("verification")
            if not isinstance(verification, list):
                errors.append(f"gates[{index}].verification must be an array")
            elif not verification:
                errors.append(f"gates[{index}].verification must not be empty")
            else:
                for evidence_index, evidence in enumerate(verification):
                    if not _is_mapping(evidence):
                        errors.append(
                            f"gates[{index}].verification[{evidence_index}] must be an object"
                        )
                        continue
                    for field in ("kind", "reference", "status"):
                        if not _non_empty_string(evidence.get(field)):
                            errors.append(
                                f"gates[{index}].verification[{evidence_index}].{field} "
                                "must be non-empty"
                            )

    for stage_id, stage in stages.items():
        for field in ("entry_gates", "exit_gates"):
            gate_ids = stage.get(field)
            if not isinstance(gate_ids, list):
                continue
            for gate_id in gate_ids:
                if not isinstance(gate_id, str) or gate_id not in gates:
                    errors.append(
                        f"stage {stage_id!r} references undeclared gate {gate_id!r}"
                    )

    transitions_value = manifest.get("transitions")
    if not isinstance(transitions_value, list):
        errors.append("transitions must be an array")
    else:
        for index, transition in enumerate(transitions_value):
            if not _is_mapping(transition):
                errors.append(f"transitions[{index}] must be an object")
                continue
            for field in ("from_stage", "to_stage"):
                stage_id = transition.get(field)
                if not isinstance(stage_id, str) or stage_id not in stages:
                    errors.append(f"transitions[{index}].{field} references an unknown stage")
            for field in ("trigger", "gate_id"):
                if not _non_empty_string(transition.get(field)):
                    errors.append(f"transitions[{index}].{field} must be non-empty")
            transition_gate_id = transition.get("gate_id")
            gate = (
                gates.get(transition_gate_id)
                if isinstance(transition_gate_id, str)
                else None
            )
            if gate is None:
                errors.append(f"transitions[{index}].gate_id references an undeclared gate")
            elif gate.get("stage_id") != transition.get("from_stage"):
                errors.append(
                    f"transitions[{index}].gate_id must be owned by from_stage"
                )

    artifact_owners_value = manifest.get("artifact_owners")
    artifact_owners: dict[str, str] = {}
    if not isinstance(artifact_owners_value, list):
        errors.append("artifact_owners must be an array")
    else:
        for index, owner in enumerate(artifact_owners_value):
            if not _is_mapping(owner):
                errors.append(f"artifact_owners[{index}] must be an object")
                continue
            artifact_type = owner.get("artifact_type")
            stage_id = owner.get("stage_id")
            if not isinstance(artifact_type, str) or not _IDENTIFIER.fullmatch(artifact_type):
                errors.append(f"artifact_owners[{index}].artifact_type must be lowercase snake_case")
            elif artifact_type in artifact_owners:
                errors.append(f"artifact_type {artifact_type!r} is duplicated")
            elif not isinstance(stage_id, str) or stage_id not in stages:
                errors.append(f"artifact_owners[{index}].stage_id references an unknown stage")
            else:
                artifact_owners[artifact_type] = stage_id

    routes_value = manifest.get("feedback_routes")
    routes: dict[str, dict[str, Any]] = {}
    if not isinstance(routes_value, list):
        errors.append("feedback_routes must be an array")
    else:
        for index, route in enumerate(routes_value):
            if not _is_mapping(route):
                errors.append(f"feedback_routes[{index}] must be an object")
                continue
            event_type = route.get("event_type")
            if not isinstance(event_type, str) or not _IDENTIFIER.fullmatch(event_type):
                errors.append(f"feedback_routes[{index}].event_type must be lowercase snake_case")
                continue
            if event_type in routes:
                errors.append(f"event_type {event_type!r} is duplicated")
                continue
            routes[event_type] = route
            target_stage = route.get("target_stage")
            if not isinstance(target_stage, str) or target_stage not in stages:
                errors.append(
                    f"feedback_routes[{index}].target_stage references an unknown stage"
                )
            route_priority = route.get("priority")
            if not isinstance(route_priority, str) or route_priority not in {
                "low",
                "normal",
                "high",
                "urgent",
            }:
                errors.append(
                    f"feedback_routes[{index}].priority must be low, normal, high, or urgent"
                )
            if not _non_empty_string(route.get("reason")):
                errors.append(f"feedback_routes[{index}].reason must be non-empty")
            source_stages = route.get("source_stages")
            _string_list(
                source_stages,
                f"feedback_routes[{index}].source_stages",
                errors,
                allow_empty=False,
            )
            if isinstance(source_stages, list):
                for source_stage in source_stages:
                    if not isinstance(source_stage, str) or source_stage not in stages:
                        errors.append(
                            f"feedback_routes[{index}].source_stages references "
                            f"unknown stage {source_stage!r}"
                        )
            _string_list(
                route.get("required_fields"),
                f"feedback_routes[{index}].required_fields",
                errors,
            )
            required_fields = route.get("required_fields")
            if isinstance(required_fields, list):
                for field in required_fields:
                    if not isinstance(field, str) or field not in _ISSUE_FORM_FIELDS:
                        errors.append(
                            f"feedback_routes[{index}].required_fields contains "
                            f"unsupported issue form field {field!r}"
                        )
            _string_list(
                route.get("labels"),
                f"feedback_routes[{index}].labels",
                errors,
            )

    missing_routes = REQUIRED_FEEDBACK_TYPES - routes.keys()
    if missing_routes:
        errors.append(
            "feedback_routes is missing required event types: "
            + ", ".join(sorted(missing_routes))
        )
    for event_type in sorted(REQUIRED_BACKWARD_FEEDBACK_TYPES & routes.keys()):
        route = routes[event_type]
        target_stage = route.get("target_stage")
        source_stages = route.get("source_stages")
        if (
            isinstance(target_stage, str)
            and target_stage in stages
            and isinstance(source_stages, list)
            and isinstance(stages[target_stage].get("order"), int)
            and not any(
                isinstance(source_stage, str)
                and source_stage in stages
                and isinstance(stages[source_stage].get("order"), int)
                and stages[target_stage]["order"] < stages[source_stage]["order"]
                for source_stage in source_stages
            )
        ):
            errors.append(
                f"feedback route {event_type!r} must return to a stage earlier "
                "than at least one source stage"
            )

    contributions_value = manifest.get("contribution_routes")
    contributions: dict[str, dict[str, Any]] = {}
    if not isinstance(contributions_value, list):
        errors.append("contribution_routes must be an array")
    else:
        for index, contribution in enumerate(contributions_value):
            if not _is_mapping(contribution):
                errors.append(f"contribution_routes[{index}] must be an object")
                continue
            contribution_type = contribution.get("contribution_type")
            if not isinstance(contribution_type, str) or not _IDENTIFIER.fullmatch(
                contribution_type
            ):
                errors.append(
                    f"contribution_routes[{index}].contribution_type "
                    "must be lowercase snake_case"
                )
                continue
            if contribution_type in contributions:
                errors.append(f"contribution_type {contribution_type!r} is duplicated")
                continue
            contributions[contribution_type] = contribution
            target_stage = contribution.get("target_stage")
            if not isinstance(target_stage, str) or target_stage not in stages:
                errors.append(
                    f"contribution_routes[{index}].target_stage references an unknown stage"
                )
            if not _non_empty_string(contribution.get("reason")):
                errors.append(f"contribution_routes[{index}].reason must be non-empty")
            priority = contribution.get("priority")
            if not isinstance(priority, str) or priority not in {
                "low",
                "normal",
                "high",
                "urgent",
            }:
                errors.append(
                    f"contribution_routes[{index}].priority must be low, normal, high, or urgent"
                )
            _string_list(
                contribution.get("required_fields"),
                f"contribution_routes[{index}].required_fields",
                errors,
            )
            required_fields = contribution.get("required_fields")
            if isinstance(required_fields, list):
                for field in required_fields:
                    if not isinstance(field, str) or field not in _ISSUE_FORM_FIELDS:
                        errors.append(
                            f"contribution_routes[{index}].required_fields contains "
                            f"unsupported issue form field {field!r}"
                        )
            _string_list(
                contribution.get("labels"),
                f"contribution_routes[{index}].labels",
                errors,
            )
    missing_contributions = REQUIRED_CONTRIBUTION_TYPES - contributions.keys()
    if missing_contributions:
        errors.append(
            "contribution_routes is missing required contribution types: "
            + ", ".join(sorted(missing_contributions))
        )

    if stages and isinstance(transitions_value, list):
        orders = {
            stage_id: stage.get("order")
            for stage_id, stage in stages.items()
            if isinstance(stage.get("order"), int) and not isinstance(stage.get("order"), bool)
        }
        backward_transition = any(
            isinstance(transition.get("from_stage"), str)
            and isinstance(transition.get("to_stage"), str)
            and transition.get("from_stage") in orders
            and transition.get("to_stage") in orders
            and orders[transition["to_stage"]] < orders[transition["from_stage"]]
            for transition in transitions_value
            if _is_mapping(transition)
        )
        backward_feedback = any(
            isinstance(route.get("target_stage"), str)
            and route.get("target_stage") in orders
            and isinstance(route.get("source_stages"), list)
            and any(
                isinstance(source_stage, str)
                and source_stage in orders
                and orders[route["target_stage"]] < orders[source_stage]
                for source_stage in route["source_stages"]
            )
            for route in routes.values()
        )
        if not backward_transition or not backward_feedback:
            errors.append(
                "workflow must declare both a backward lifecycle transition and "
                "a feedback route to an earlier stage"
            )
        ordered_stage_ids = sorted(orders, key=orders.__getitem__)
        transition_pairs = {
            (transition.get("from_stage"), transition.get("to_stage"))
            for transition in transitions_value
            if _is_mapping(transition)
            and isinstance(transition.get("from_stage"), str)
            and isinstance(transition.get("to_stage"), str)
        }
        for from_stage, to_stage in zip(ordered_stage_ids, ordered_stage_ids[1:]):
            if (from_stage, to_stage) not in transition_pairs:
                errors.append(
                    f"workflow is missing forward transition {from_stage!r} -> {to_stage!r}"
                )

    return errors


def validate_traceability_matrix(matrix: Any, manifest: Any) -> list[str]:
    """Validate requirement-to-stage/artifact/evidence links."""
    errors: list[str] = []
    if not _is_mapping(matrix):
        return ["traceability matrix must be a JSON object"]
    if matrix.get("matrix_version") != "1.0":
        errors.append("matrix_version must be '1.0'")
    stages = {
        stage.get("stage_id")
        for stage in manifest.get("stages", [])
        if _is_mapping(stage) and _non_empty_string(stage.get("stage_id"))
    } if _is_mapping(manifest) and isinstance(manifest.get("stages"), list) else set()
    requirements = matrix.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("requirements must be a non-empty array")
        return errors

    seen: set[str] = set()
    allowed_statuses = {"implemented", "partial", "planned"}
    for index, requirement in enumerate(requirements):
        if not _is_mapping(requirement):
            errors.append(f"requirements[{index}] must be an object")
            continue
        requirement_id = requirement.get("requirement_id")
        if not _non_empty_string(requirement_id):
            errors.append(f"requirements[{index}].requirement_id must be non-empty")
        elif requirement_id in seen:
            errors.append(f"requirement_id {requirement_id!r} is duplicated")
        else:
            seen.add(requirement_id)
        if not _non_empty_string(requirement.get("summary")):
            errors.append(f"requirements[{index}].summary must be non-empty")
        requirement_stage_id = requirement.get("stage_id")
        if not isinstance(requirement_stage_id, str) or requirement_stage_id not in stages:
            errors.append(f"requirements[{index}].stage_id references an unknown stage")
        requirement_status = requirement.get("status")
        if not isinstance(requirement_status, str) or requirement_status not in allowed_statuses:
            errors.append(
                f"requirements[{index}].status must be implemented, partial, or planned"
            )
        _string_list(
            requirement.get("artifacts"),
            f"requirements[{index}].artifacts",
            errors,
            allow_empty=False,
        )
        verification = requirement.get("verification")
        if not isinstance(verification, list):
            errors.append(f"requirements[{index}].verification must be an array")
            continue
        if not verification:
            errors.append(f"requirements[{index}].verification must not be empty")
            continue
        for evidence_index, evidence in enumerate(verification):
            if not _is_mapping(evidence):
                errors.append(
                    f"requirements[{index}].verification[{evidence_index}] must be an object"
                )
                continue
            for field in ("kind", "reference", "status"):
                if not _non_empty_string(evidence.get(field)):
                    errors.append(
                        f"requirements[{index}].verification[{evidence_index}].{field} "
                        "must be non-empty"
                    )
    mapped_stages = {
        requirement.get("stage_id")
        for requirement in requirements
        if _is_mapping(requirement)
        and isinstance(requirement.get("stage_id"), str)
        and requirement.get("stage_id") in stages
    }
    for stage_id in sorted(set(stages) - mapped_stages):
        errors.append(f"stage {stage_id!r} has no requirements traceability row")
    return errors


def validate_matrices(manifest: Any, traceability: Any) -> list[str]:
    errors = validate_workflow_manifest(manifest)
    errors.extend(validate_traceability_matrix(traceability, manifest))
    return errors


def _clean_form_value(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"^```[^\n]*\n|\n```$", "", cleaned, flags=re.MULTILINE).strip()
    cleaned = re.sub(r"^`(.*)`$", r"\1", cleaned, flags=re.DOTALL).strip()
    return cleaned


def parse_issue_form(body: str) -> dict[str, str]:
    """Parse GitHub Issue Forms headings into normalized key/value fields."""
    headings = list(_FORM_HEADING.finditer(body))
    fields: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        key = " ".join(heading.group(1).strip().casefold().split())
        fields[key] = _clean_form_value(body[heading.end() : end])
    return fields


def _artifact_references(value: str) -> list[str]:
    references: list[str] = []
    for line in value.splitlines():
        for item in line.split(","):
            reference = item.strip().lstrip("-* ").strip("`")
            if reference and reference.casefold() not in {"none", "n/a", "not applicable"}:
                references.append(reference)
    return list(dict.fromkeys(references))


def _workflow_indexes(
    manifest: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], ...]:
    roles = {
        role["role_id"]: role
        for role in manifest["roles"]
    }
    stages = {
        stage["stage_id"]: stage
        for stage in manifest["stages"]
    }
    routes = {
        route["event_type"]: route
        for route in manifest["feedback_routes"]
    }
    contributions = {
        route["contribution_type"]: route
        for route in manifest["contribution_routes"]
    }
    artifact_owners = {
        owner["artifact_type"]: owner["stage_id"]
        for owner in manifest["artifact_owners"]
    }
    return roles, stages, routes, contributions, artifact_owners


def route_issue_event(event_document: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    """Route a GitHub issue webhook to its accountable workflow stage.

    User-submitted form errors return a visible needs-information result.
    Manifest/schema errors raise WorkflowError instead of looking successful.
    """
    manifest_errors = validate_workflow_manifest(manifest)
    if manifest_errors:
        raise WorkflowError("; ".join(manifest_errors))
    if not _is_mapping(event_document) or not _is_mapping(event_document.get("issue")):
        raise WorkflowError("GitHub event must contain an issue object")

    issue = event_document["issue"]
    issue_number = issue.get("number")
    issue_number = (
        issue_number
        if isinstance(issue_number, int) and not isinstance(issue_number, bool)
        else None
    )
    reporter = issue.get("user", {}).get("login") if _is_mapping(issue.get("user")) else None
    issue_url = issue.get("html_url")
    body = issue.get("body")
    if not isinstance(body, str):
        body = ""
    fields = parse_issue_form(body)
    roles, stages, routes, contributions, artifact_owners = _workflow_indexes(manifest)

    feedback_type = fields.get("feedback type", "").strip().casefold()
    contribution_type = fields.get("contribution type", "").strip().casefold()
    route_kind = "contribution" if contribution_type else "feedback"
    event_type = contribution_type or feedback_type
    if feedback_type and contribution_type:
        route_kind = "feedback"
        route = None
        route_error = "Choose either a contribution type or a feedback type, not both."
    else:
        route = (
            contributions.get(contribution_type)
            if contribution_type
            else routes.get(feedback_type)
        )
        route_error = ""
    issues: list[str] = []
    missing_fields: list[str] = []
    if route is None:
        issues.append(route_error or f"{route_kind.title()} type is missing or not recognized.")
        if feedback_type and contribution_type:
            missing_fields.extend(["feedback_type", "contribution_type"])
        else:
            missing_fields.append(
                "contribution_type" if contribution_type else "feedback_type"
            )

    summary = fields.get("summary", "").strip()
    if not summary or summary.casefold() in {"_no response_", "n/a"}:
        issues.append("Summary is required.")
        missing_fields.append("summary")
    observed = fields.get("observed behavior", "").strip()
    if not observed or observed.casefold() in {"_no response_", "n/a"}:
        issues.append("Observed behavior is required.")
        missing_fields.append("observed_behavior")
    expected = fields.get("expected behavior", "").strip()
    if not expected or expected.casefold() in {"_no response_", "n/a"}:
        issues.append("Expected behavior is required.")
        missing_fields.append("expected_behavior")
    affected_artifacts = _artifact_references(fields.get("affected artifacts", ""))
    evidence_links = _artifact_references(fields.get("evidence links", ""))
    priority = fields.get("priority", "").strip().casefold()
    form_values: dict[str, Any] = {
        "summary": summary,
        "observed_behavior": observed,
        "expected_behavior": expected,
        "affected_artifacts": affected_artifacts,
        "evidence_links": evidence_links,
        "priority": priority,
    }
    for field in ("affected_artifacts", "priority"):
        if not form_values[field]:
            issues.append(f"{field.replace('_', ' ').title()} is required.")
            missing_fields.append(field)
    if route is not None:
        required_fields = set(route.get("required_fields", []))
        for field in sorted(required_fields):
            value = form_values[field]
            if not value:
                human_label = field.replace("_", " ")
                issues.append(f"{human_label.title()} is required for this request.")
                missing_fields.append(field)
    allowed_priorities = {"low", "normal", "high", "urgent"}
    if priority and priority not in allowed_priorities:
        issues.append("Priority must be low, normal, high, or urgent.")
        missing_fields.append("priority")

    if issues:
        return {
            "status": "needs_information",
            "issue_number": issue_number,
            "issue_url": issue_url,
            "reporter": reporter,
            "route_kind": route_kind,
            "event_type": event_type or "unknown",
            "target_stage": None,
            "target_role": None,
            "route_reason": " ".join(issues),
            "required_fields": list(dict.fromkeys(missing_fields)),
            "affected_artifacts": affected_artifacts,
            "evidence_links": evidence_links,
            "summary": summary,
            "labels": ["workflow:status:needs-information"],
            "notification_variable": None,
        }

    if route is None:
        raise WorkflowError("feedback route disappeared after input validation")
    target_stage = route["target_stage"]
    routing_basis = "feedback_type"
    if route_kind == "contribution":
        routing_basis = "contribution_type"
    route_reason = route["reason"]

    if route_kind == "feedback" and event_type == "release_defect":
        artifact_stages: set[str] = set()
        has_unresolved_reference = False
        for reference in affected_artifacts:
            artifact_type, separator, artifact_id = reference.partition(":")
            if separator and artifact_type in artifact_owners and artifact_id.strip():
                artifact_stages.add(artifact_owners[artifact_type])
            else:
                has_unresolved_reference = True
        if len(artifact_stages) == 1 and not has_unresolved_reference:
            target_stage = next(iter(artifact_stages))
            routing_basis = "typed_artifact_owner"
            route_reason = (
                f"{route_reason} Routed to {target_stage} from the typed artifact reference; "
                "the owner must confirm the originating stage before changing content."
            )
        elif len(artifact_stages) > 1 or has_unresolved_reference:
            routing_basis = "cross_stage_triage"
            route_reason = (
                f"{route_reason} Affected artifact references are untyped, unresolved, or span "
                "stages; post-release triage must confirm owners before splitting corrective work."
            )
        else:
            routing_basis = "post_release_triage"
            route_reason = (
                f"{route_reason} No recognized typed artifact reference was supplied; "
                "post-release triage must confirm the owner."
            )

    stage = stages[target_stage]
    owner_role = stage["owner_role"]
    role = roles[owner_role]
    routed_priority = priority or route["priority"]
    labels = list(route["labels"])
    labels.append(
        "crowd-cinema:contribution"
        if route_kind == "contribution"
        else "crowd-cinema:feedback"
    )
    if route_kind == "contribution":
        labels.append(f"workflow:contribution:{event_type}")
    labels.extend(
        [
            f"workflow:stage:{target_stage}",
            "workflow:status:routed",
            f"workflow:priority:{routed_priority}",
        ]
    )
    return {
        "status": "routed",
        "issue_number": issue_number,
        "issue_url": issue_url,
        "reporter": reporter,
        "route_kind": route_kind,
        "event_type": event_type,
        "source_stages": route.get("source_stages") if route_kind == "feedback" else None,
        "target_stage": target_stage,
        "target_role": owner_role,
        "route_reason": route_reason,
        "required_fields": [],
        "routing_basis": routing_basis,
        "affected_artifacts": affected_artifacts,
        "evidence_links": evidence_links,
        "summary": summary,
        "observed_behavior": observed,
        "expected_behavior": expected,
        "priority": routed_priority,
        "labels": list(dict.fromkeys(labels)),
        "notification_variable": role["notification_variable"],
    }


def render_workflow_board(manifest: dict[str, Any], traceability: dict[str, Any]) -> str:
    """Render a static workflow and traceability dashboard from checked-in data."""
    template_path = Path(__file__).parent / "templates" / "workflow_board.html"
    template = template_path.read_text(encoding="utf-8")
    workflow_data = json.dumps(manifest, ensure_ascii=False, indent=2)
    matrix_data = json.dumps(traceability, ensure_ascii=False, indent=2)
    workflow_data = workflow_data.translate(
        str.maketrans({"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"})
    )
    matrix_data = matrix_data.translate(
        str.maketrans({"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"})
    )
    if template.count("@@WORKFLOW_JSON@@") != 1:
        raise WorkflowError("workflow board template must contain exactly one workflow placeholder")
    if template.count("@@TRACEABILITY_JSON@@") != 1:
        raise WorkflowError("workflow board template must contain exactly one traceability placeholder")
    return template.replace("@@WORKFLOW_JSON@@", workflow_data).replace(
        "@@TRACEABILITY_JSON@@", matrix_data
    )


def build_workflow_board(
    manifest_path: str | Path,
    traceability_path: str | Path,
    output_path: str | Path,
) -> Path:
    manifest = load_json(manifest_path)
    traceability = load_json(traceability_path)
    errors = validate_matrices(manifest, traceability)
    if errors:
        raise WorkflowError("; ".join(errors))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_workflow_board(manifest, traceability),
        encoding="utf-8",
        newline="\n",
    )
    return output
