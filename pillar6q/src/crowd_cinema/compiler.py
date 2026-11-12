"""Validation and compilation of a single short-shot blueprint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GENRES = frozenset(
    {
        "CANONICAL_CLASSICAL",
        "FOLK_RETELLING",
        "ANIMATED_KIDS",
        "SPECULATIVE_ALTERNATE",
        "PHILOSOPHICAL_ALLEGORY",
    }
)
REQUIRED_TEXT_FIELDS = (
    "shot_id",
    "start_keyframe",
    "end_keyframe",
    "foreground_action",
    "secondary_action",
    "crowd_action",
)


def validate_shot(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("shot specification must be a JSON object")
    for field in REQUIRED_TEXT_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
    genre = data.get("genre")
    if not isinstance(genre, str) or genre not in GENRES:
        raise ValueError(f"genre must be one of: {', '.join(sorted(GENRES))}")
    duration = data.get("duration_sec")
    if isinstance(duration, bool) or not isinstance(duration, int) or not 10 <= duration <= 15:
        raise ValueError("duration_sec must be an integer from 10 through 15")
    source_uris = data.get("source_uris", [])
    if not isinstance(source_uris, list) or not all(
        isinstance(uri, str) and uri.strip() for uri in source_uris
    ):
        raise ValueError("source_uris must be a list of non-empty strings")
    allowed = set(REQUIRED_TEXT_FIELDS) | {"genre", "duration_sec", "source_uris"}
    extra = set(data) - allowed
    if extra:
        raise ValueError(f"unexpected fields: {', '.join(sorted(extra))}")
    return {
        "shot_id": data["shot_id"].strip(),
        "genre": genre,
        "duration_sec": duration,
        "start_keyframe": data["start_keyframe"].strip(),
        "end_keyframe": data["end_keyframe"].strip(),
        "actions": {
            "foreground": data["foreground_action"].strip(),
            "secondary": data["secondary_action"].strip(),
            "crowd": data["crowd_action"].strip(),
        },
        "source_uris": [uri.strip() for uri in source_uris],
    }


def compile_shot(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as source:
        data = json.load(source)
    return validate_shot(data)
