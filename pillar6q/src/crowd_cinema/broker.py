"""Deterministic local render-packet serialization."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def create_packet(shot: dict[str, Any]) -> dict[str, Any]:
    body = {
        "packet_version": 1,
        "slot_id": shot["shot_id"],
        "genre": shot["genre"],
        "duration_sec": shot["duration_sec"],
        "start_keyframe": shot["start_keyframe"],
        "end_keyframe": shot["end_keyframe"],
        "motion_directives": shot["actions"],
        "source_uris": shot["source_uris"],
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**body, "packet_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()}
