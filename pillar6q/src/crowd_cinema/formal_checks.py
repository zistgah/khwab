"""Bounded exhaustive checks for quorum, vote, and timeline invariants.

These are executable finite-state checks, not CBMC/Z3 proofs. Bounds and
assumptions are included in every report so callers can see what was checked.
"""

from __future__ import annotations

from itertools import product
from typing import Any

from .assurance import (
    deterministic_vote_winner,
    evaluate_authority_quorum,
    validate_timeline,
)


def _check_quorums(max_authorities: int) -> dict[str, Any]:
    checked = 0
    for authority_count in range(1, max_authorities + 1):
        authority_ids = tuple(range(authority_count))
        for approvals in product((False, True), repeat=authority_count):
            for threshold in range(1, authority_count + 1):
                approved_count = sum(approvals)
                result = evaluate_authority_quorum(
                    authority_ids,
                    approvals,
                    threshold,
                )
                if result["quorum_met"] != (approved_count >= threshold):
                    raise AssertionError("quorum decision differs from the direct threshold predicate")
                if result["approved_count"] != approved_count:
                    raise AssertionError("reported approval count differs from the direct count")
                checked += 1
    return {
        "status": "passed",
        "models_checked": checked,
        "bound": {"maximum_unique_authorities": max_authorities},
        "properties": [
            "quorum is true exactly when distinct approval count meets threshold",
            "approval count never exceeds authority count",
        ],
        "assumption": "authority IDs are unique in the enumerated models",
    }


def _check_vote_winners(max_voters: int, max_candidates: int) -> dict[str, Any]:
    rows_checked = 0
    vote_vectors = ((candidate, weight) for candidate in range(max_candidates) for weight in range(3))
    choices = tuple(vote_vectors)
    for voter_count in range(1, max_voters + 1):
        for ballots in product(choices, repeat=voter_count):
            votes = [
                (voter_id, candidate_id, weight)
                for voter_id, (candidate_id, weight) in enumerate(ballots)
            ]
            result = deterministic_vote_winner(votes)
            expected_tallies: dict[int, int] = {}
            for _, candidate_id, weight in votes:
                expected_tallies[candidate_id] = expected_tallies.get(candidate_id, 0) + weight
            expected_winner = min(
                expected_tallies,
                key=lambda candidate_id: (-expected_tallies[candidate_id], candidate_id),
            )
            if result["winner_id"] != expected_winner:
                raise AssertionError("vote winner does not match max-weight/lowest-ID tie-break")
            if result["winner_weight"] != expected_tallies[expected_winner]:
                raise AssertionError("reported winner weight differs from the direct tally")
            rows_checked += 1
    return {
        "status": "passed",
        "models_checked": rows_checked,
        "bound": {
            "maximum_voters": max_voters,
            "candidate_ids": list(range(max_candidates)),
            "weight_per_ballot": [0, 1, 2],
        },
        "properties": [
            "winner maximizes integer vote weight",
            "ties resolve to the smallest candidate identifier",
            "tallies match direct summation for unique voters",
        ],
        "assumption": "voter identities are unique and weights are in the enumerated range",
    }


def _check_timelines(max_shots: int) -> dict[str, Any]:
    checked = 0
    for shot_count in range(1, max_shots + 1):
        for durations in product((10, 12, 15), repeat=shot_count):
            start = 0
            shots = []
            for index, duration in enumerate(durations):
                shots.append(
                    {
                        "shot_id": f"shot-{index}",
                        "start_sec": start,
                        "duration_sec": duration,
                    }
                )
                start += duration
            result = validate_timeline(shots)
            if not result["continuous"] or result["total_duration_sec"] != start:
                raise AssertionError("contiguous timeline result differs from constructed timeline")
            checked += 1
    return {
        "status": "passed",
        "models_checked": checked,
        "bound": {
            "maximum_shots": max_shots,
            "durations_seconds": [10, 12, 15],
            "timeline_start_seconds": 0,
        },
        "properties": [
            "each shot duration is in the accepted 10-15 second interval",
            "contiguous ordered shots have no gaps or overlaps",
            "reported total duration equals the sum of shot durations",
        ],
    }


def run_bounded_checks(
    *,
    max_authorities: int = 5,
    max_voters: int = 4,
    max_candidates: int = 3,
    max_shots: int = 5,
) -> dict[str, Any]:
    """Run finite exhaustive models within deliberately small explicit bounds."""
    bounds = {
        "max_authorities": max_authorities,
        "max_voters": max_voters,
        "max_candidates": max_candidates,
        "max_shots": max_shots,
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in bounds.values()):
        raise ValueError("all exhaustive-check bounds must be positive integers")
    if max_candidates > 5 or max_voters > 5 or max_authorities > 8 or max_shots > 8:
        raise ValueError("bounds exceed the supported runtime-safe exhaustive limits")
    checks = {
        "quorum": _check_quorums(max_authorities),
        "votes": _check_vote_winners(max_voters, max_candidates),
        "timeline": _check_timelines(max_shots),
    }
    return {
        "status": "passed" if all(item["status"] == "passed" for item in checks.values()) else "failed",
        "method": "bounded exhaustive enumeration",
        "formal_proof": False,
        "bounds": bounds,
        "checks": checks,
        "limitations": [
            "This is not CBMC, Z3, model checking of the C source, or proof beyond the enumerated bounds.",
            "Cryptographic identity, provider behavior, media frames, optical flow, and audio/video synchronization are not modeled.",
        ],
    }
