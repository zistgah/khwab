"""Executable assurance checks for content, votes, timelines, and hazards.

These are deterministic input-validation checks. They do not authenticate
sources, establish scholarly truth, or constitute a formal proof.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from .compiler import GENRES

CANONICAL_GENRE = "CANONICAL_CLASSICAL"
SPECULATIVE_GENRE = "SPECULATIVE_ALTERNATE"
UINT32_MAX = (1 << 32) - 1
UINT64_MAX = (1 << 64) - 1


def _integer(value: Any, name: str, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        limit = f" through {maximum}" if maximum is not None else " or greater"
        raise ValueError(f"{name} must be {minimum}{limit}")
    return value


def _valid_source_uri(uri: Any) -> bool:
    if not isinstance(uri, str) or not uri or uri != uri.strip() or any(c.isspace() for c in uri):
        return False
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return False
    if parsed.scheme.lower() in {"http", "https"}:
        return bool(parsed.netloc and parsed.hostname)
    if parsed.scheme.lower() in {"doi", "urn"}:
        return bool(parsed.path)
    return False


def validate_content_safety(content: Mapping[str, Any]) -> dict[str, Any]:
    """Validate genre framing and source URI linkage without verifying sources.

    Canonical-classical content must link its declared sources to at least one
    named content field. Speculative-alternate content must include a clear
    disclosure. Optional ``source_links`` maps field labels to declared URIs.
    """
    if not isinstance(content, Mapping):
        raise ValueError("content must be a mapping")
    genre = content.get("genre")
    if not isinstance(genre, str) or genre not in GENRES:
        raise ValueError(f"genre must be one of: {', '.join(sorted(GENRES))}")

    source_uris = content.get("source_uris", [])
    if not isinstance(source_uris, list):
        raise ValueError("source_uris must be a list")
    if any(not _valid_source_uri(uri) for uri in source_uris):
        raise ValueError("source_uris must contain absolute http(s), doi, or urn URIs")
    if len(set(source_uris)) != len(source_uris):
        raise ValueError("source_uris must not contain duplicates")

    source_links = content.get("source_links", {})
    if not isinstance(source_links, Mapping):
        raise ValueError("source_links must be a mapping of content fields to source URIs")
    declared = set(source_uris)
    linked: set[str] = set()
    for field, uris in source_links.items():
        if not isinstance(field, str) or not field.strip():
            raise ValueError("source_links field names must be non-empty strings")
        if isinstance(uris, str):
            uris = [uris]
        if not isinstance(uris, list) or not uris:
            raise ValueError(f"source_links[{field!r}] must identify one or more source URIs")
        for uri in uris:
            if not _valid_source_uri(uri):
                raise ValueError(f"source link for {field!r} must be a valid absolute source URI")
            if uri not in declared:
                raise ValueError(f"source link for {field!r} is not present in source_uris")
            linked.add(uri)

    if genre == CANONICAL_GENRE:
        if not source_uris:
            raise ValueError("canonical content requires at least one source URI")
        if not source_links:
            raise ValueError("canonical content must link sources to named content fields")
        if linked != declared:
            raise ValueError("every canonical source URI must be linked to a content field")

    if genre == SPECULATIVE_GENRE:
        disclosure = content.get("speculative_disclosure")
        if not isinstance(disclosure, str) or not disclosure.strip():
            raise ValueError("speculative content requires a non-empty speculative_disclosure")

    return {
        "genre": genre,
        "source_count": len(source_uris),
        "linked_source_count": len(linked),
        "source_links_valid": True,
        "classification_disclosed": genre != SPECULATIVE_GENRE
        or bool(content["speculative_disclosure"].strip()),
        "source_authenticity_verified": False,
    }


def validate_shot_duration(
    duration_sec: Any, minimum: int = 10, maximum: int = 15
) -> int:
    """Return a valid integer duration in the inclusive configured range."""
    minimum = _integer(minimum, "minimum", 1)
    maximum = _integer(maximum, "maximum", minimum)
    return _integer(duration_sec, "duration_sec", minimum, maximum)


def validate_timeline(shots: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Check that integer-second shots have valid durations and no timeline gaps."""
    if not isinstance(shots, Sequence) or isinstance(shots, (str, bytes)) or not shots:
        raise ValueError("shots must be a non-empty sequence")
    expected_start = 0
    validated = []
    seen_ids: set[str] = set()
    for index, shot in enumerate(shots):
        if not isinstance(shot, Mapping):
            raise ValueError(f"shots[{index}] must be a mapping")
        shot_id = shot.get("shot_id")
        if not isinstance(shot_id, str) or not shot_id.strip():
            raise ValueError(f"shots[{index}].shot_id must be a non-empty string")
        if shot_id in seen_ids:
            raise ValueError(f"duplicate shot_id: {shot_id}")
        seen_ids.add(shot_id)
        start = _integer(shot.get("start_sec"), f"shots[{index}].start_sec", 0)
        duration = validate_shot_duration(shot.get("duration_sec"))
        if start != expected_start:
            raise ValueError(
                f"timeline discontinuity at {shot_id}: expected start_sec "
                f"{expected_start}, got {start}"
            )
        end = start + duration
        validated.append({"shot_id": shot_id, "start_sec": start, "end_sec": end})
        expected_start = end
    return {"shots": validated, "total_duration_sec": expected_start, "continuous": True}


def evaluate_authority_quorum(
    authority_ids: Iterable[int], approvals: Iterable[bool], threshold: int
) -> dict[str, Any]:
    """Count approved unique authorities and report whether threshold is met."""
    ids, decisions = list(authority_ids), list(approvals)
    if not ids or len(ids) != len(decisions):
        raise ValueError("authority_ids and approvals must have the same non-zero length")
    threshold = _integer(threshold, "threshold", 1, len(ids))
    for identity in ids:
        _integer(identity, "authority_id", 0, UINT32_MAX)
    if any(type(decision) is not bool for decision in decisions):
        raise ValueError("approvals must contain only booleans")
    approved_ids = [identity for identity, approved in zip(ids, decisions) if approved]
    if len(set(approved_ids)) != len(approved_ids):
        raise ValueError("duplicate approved authority identity")
    approved_count = len(approved_ids)
    return {
        "approved_count": approved_count,
        "threshold": threshold,
        "quorum_met": approved_count >= threshold,
    }


def deterministic_vote_winner(
    votes: Iterable[tuple[int, int, int]],
) -> dict[str, Any]:
    """Tally ``(voter_id, candidate_id, weight)`` rows with lowest-ID tie-break."""
    rows = list(votes)
    if not rows:
        raise ValueError("votes must be non-empty")
    tally: dict[int, int] = {}
    seen_voters: set[int] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise ValueError(f"votes[{index}] must be a (voter_id, candidate_id, weight) triple")
        voter_id = _integer(row[0], f"votes[{index}].voter_id", 0, UINT32_MAX)
        candidate_id = _integer(row[1], f"votes[{index}].candidate_id", 0, UINT32_MAX)
        weight = _integer(row[2], f"votes[{index}].weight", 0, UINT32_MAX)
        if voter_id in seen_voters:
            raise ValueError(f"duplicate voter identity: {voter_id}")
        seen_voters.add(voter_id)
        new_total = tally.get(candidate_id, 0) + weight
        if new_total > UINT64_MAX:
            raise ValueError("candidate vote weight exceeds uint64 range")
        tally[candidate_id] = new_total
    winner_id = min(tally, key=lambda candidate: (-tally[candidate], candidate))
    return {
        "winner_id": winner_id,
        "winner_weight": tally[winner_id],
        "tallies": dict(sorted(tally.items())),
    }


def build_hazard_report() -> dict[str, Any]:
    """Return a compact qualitative HAZOP/FMECA-style report with explicit limits."""
    hazards = [
        {
            "id": "H-01",
            "deviation": "Canonical content has no linked source",
            "effect": "Unsupported or misattributed material may be presented as canonical",
            "severity": 4,
            "occurrence": 3,
            "detectability": 3,
            "safeguards": ["Require declared source URIs and field-level linkage"],
            "recommended_action": "Editorially review source relevance and attribution",
        },
        {
            "id": "H-02",
            "deviation": "Speculative alternate is not disclosed",
            "effect": "Viewers may mistake invented material for a canonical account",
            "severity": 4,
            "occurrence": 3,
            "detectability": 3,
            "safeguards": ["Require explicit speculative disclosure"],
            "recommended_action": "Keep disclosure visible in downstream presentation",
        },
        {
            "id": "H-03",
            "deviation": "Votes contain duplicate voters or a missing quorum",
            "effect": "Tally may be biased or decision authority insufficient",
            "severity": 4,
            "occurrence": 2,
            "detectability": 2,
            "safeguards": ["Reject duplicate identities; count quorum deterministically"],
            "recommended_action": "Review voter eligibility outside this module",
        },
        {
            "id": "H-04",
            "deviation": "Shot duration or timeline continuity is invalid",
            "effect": "Playback may contain gaps, overlaps, or out-of-policy shots",
            "severity": 3,
            "occurrence": 3,
            "detectability": 2,
            "safeguards": ["Enforce integer duration bounds and contiguous start times"],
            "recommended_action": "Run timeline validation before render handoff",
        },
    ]
    for hazard in hazards:
        hazard["rpn"] = hazard["severity"] * hazard["occurrence"] * hazard["detectability"]
    return {
        "method": "qualitative HAZOP/FMECA-style screening",
        "rating_scale": "1 (low) to 5 (high); RPN = severity × occurrence × detectability",
        "hazards": hazards,
        "limitations": [
            "Ratings are screening estimates, not measured probabilities.",
            "No cryptographic signature verification is performed.",
            "No CBMC/Z3 or other formal proof is claimed.",
        ],
    }
