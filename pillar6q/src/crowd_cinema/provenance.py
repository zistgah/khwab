"""Local, integrity-tagged attribution ledger and end-credit rendering.

Contributor labels should be non-identifying pseudonyms; this module does not
provide identity verification or a cryptographic signature.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping


ALLOWED_ROLES = frozenset(
    {
        "accessibility-review",
        "audio-description",
        "collation",
        "editorial-review",
        "storyboarding",
        "translation-review",
        "visual-design",
    }
)
_DIGEST_FIELD = "integrity_sha256"


def canonical_json(value: Any) -> str:
    """Serialize JSON data with stable key ordering and compact separators."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"value is not canonicalizable JSON: {error}") from error


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{field} must be a single line")
    return value.strip()


def _parse_timestamp(value: Any) -> datetime:
    timestamp = _text(value, "timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("timestamp must be an ISO 8601 date-time") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _utc_timestamp(value: Any) -> str:
    return _parse_timestamp(value).isoformat().replace("+00:00", "Z")


def _validate_body(manifest: Mapping[str, Any]) -> None:
    if type(manifest.get("manifest_version")) is not int or manifest["manifest_version"] != 1:
        raise ValueError("manifest_version must be 1")
    contributors = manifest.get("contributors")
    events = manifest.get("events")
    if not isinstance(contributors, list):
        raise ValueError("contributors must be a list")
    if not isinstance(events, list):
        raise ValueError("events must be a list")

    contributor_roles: dict[str, set[str]] = {}
    for contributor in contributors:
        if not isinstance(contributor, dict):
            raise ValueError("each contributor must be an object")
        contributor_id = _text(contributor.get("contributor_id"), "contributor_id")
        if contributor_id in contributor_roles:
            raise ValueError(f"duplicate contributor_id: {contributor_id}")
        _text(contributor.get("display_label"), "display_label")
        roles = contributor.get("roles")
        if not isinstance(roles, list) or not roles:
            raise ValueError(f"roles for {contributor_id} must be a non-empty list")
        validated_roles: set[str] = set()
        for role in roles:
            role = _text(role, "role")
            if role not in ALLOWED_ROLES:
                raise ValueError(f"unsupported role: {role}")
            if role in validated_roles:
                raise ValueError(f"duplicate role for {contributor_id}: {role}")
            validated_roles.add(role)
        contributor_roles[contributor_id] = validated_roles

    event_ids: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("each event must be an object")
        event_id = _text(event.get("event_id"), "event_id")
        if event_id in event_ids:
            raise ValueError(f"duplicate event_id: {event_id}")
        event_ids.add(event_id)
        _parse_timestamp(event.get("timestamp"))
        contributor_id = _text(event.get("contributor_id"), "contributor_id")
        if contributor_id not in contributor_roles:
            raise ValueError(f"unknown contributor_id: {contributor_id}")
        role = _text(event.get("role"), "role")
        if role not in ALLOWED_ROLES:
            raise ValueError(f"unsupported role: {role}")
        if role not in contributor_roles[contributor_id]:
            raise ValueError(f"{contributor_id} is not registered for role: {role}")
        _text(event.get("contribution"), "contribution")


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate ledger structure, role assignments, references, and event IDs."""
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be an object")
    _validate_body(manifest)


def _body_for_digest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key != _DIGEST_FIELD}


def create_manifest(
    contributors: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a stable ledger and attach its SHA-256 integrity digest.

    Contributor records use pseudonymous IDs and display labels, not real names.
    """
    normalized_contributors: list[dict[str, Any]] = []
    for contributor in contributors:
        if not isinstance(contributor, Mapping):
            raise ValueError("each contributor must be an object")
        roles = contributor.get("roles")
        if not isinstance(roles, list):
            raise ValueError("roles must be a list")
        normalized_roles = sorted(_text(role, "role") for role in roles)
        normalized_contributors.append(
            {
                "contributor_id": _text(contributor.get("contributor_id"), "contributor_id"),
                "display_label": _text(contributor.get("display_label"), "display_label"),
                "roles": normalized_roles,
            }
        )
    normalized_contributors.sort(key=lambda item: item["contributor_id"])

    normalized_events: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            raise ValueError("each event must be an object")
        normalized_events.append(
            {
                "event_id": _text(event.get("event_id"), "event_id"),
                "timestamp": _utc_timestamp(event.get("timestamp")),
                "contributor_id": _text(event.get("contributor_id"), "contributor_id"),
                "role": _text(event.get("role"), "role"),
                "contribution": _text(event.get("contribution"), "contribution"),
            }
        )
    normalized_events.sort(
        key=lambda item: (_parse_timestamp(item["timestamp"]), item["event_id"])
    )

    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "contributors": normalized_contributors,
        "events": normalized_events,
    }
    validate_manifest(manifest)
    manifest[_DIGEST_FIELD] = hashlib.sha256(
        canonical_json(manifest).encode("utf-8")
    ).hexdigest()
    return manifest


def verify_manifest(manifest: Mapping[str, Any]) -> bool:
    """Validate a ledger and report whether its body matches its SHA-256 digest."""
    validate_manifest(manifest)
    digest = manifest.get(_DIGEST_FIELD)
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("manifest is missing a valid integrity_sha256")
    expected = hashlib.sha256(
        canonical_json(_body_for_digest(manifest)).encode("utf-8")
    ).hexdigest()
    return digest == expected


def serialize_manifest(manifest: Mapping[str, Any]) -> str:
    """Return canonical JSON for a structurally valid, correctly tagged ledger."""
    if not verify_manifest(manifest):
        raise ValueError("manifest integrity digest does not match its contents")
    return canonical_json(manifest)


def render_credits(manifest: Mapping[str, Any]) -> str:
    """Render event credits in chronological UTC order."""
    if not verify_manifest(manifest):
        raise ValueError("manifest integrity digest does not match its contents")
    labels = {
        contributor["contributor_id"]: contributor["display_label"]
        for contributor in manifest["contributors"]
    }
    events = sorted(
        manifest["events"],
        key=lambda event: (_parse_timestamp(event["timestamp"]), event["event_id"]),
    )
    lines = ["End credits (chronological)"]
    for event in events:
        timestamp = _utc_timestamp(event["timestamp"])
        lines.append(
            f"{timestamp} — {labels[event['contributor_id']]} "
            f"({event['role']}): {event['contribution']}"
        )
    return "\n".join(lines)
