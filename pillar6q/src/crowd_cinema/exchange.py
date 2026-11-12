"""A small SQLite-backed local exchange for shot slots, takes, and votes.

This module stores content and vote records locally. It does not provide real
identity verification or Sybil resistance, call external APIs, generate video,
or stitch submissions into a film.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any


class ExchangeError(ValueError):
    """Base error for invalid exchange operations."""


class NotFoundError(ExchangeError):
    """Raised when a requested slot or candidate does not exist."""


class AlreadyExistsError(ExchangeError):
    """Raised when an operation would create a duplicate record."""


class DuplicateTakeError(AlreadyExistsError):
    """Raised when a submitter repeats identical content in a slot."""


class DuplicateVoteError(AlreadyExistsError):
    """Raised when an identity votes more than once on the same take."""


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExchangeError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ExchangeError(f"{field} must be a positive integer")
    return value


class LocalExchange:
    """Manage a local volunteer exchange backed by a SQLite database.

    Quorum is the number of distinct voter identities who have cast at least
    one vote in a slot. Each identity can vote once for each candidate take;
    this is a database uniqueness rule, not proof that identities are unique.
    """

    def __init__(self, database: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(database))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS slots (
                slot_id TEXT PRIMARY KEY,
                quorum INTEGER NOT NULL CHECK (quorum > 0)
            );
            CREATE TABLE IF NOT EXISTS takes (
                take_id INTEGER PRIMARY KEY,
                slot_id TEXT NOT NULL REFERENCES slots(slot_id) ON DELETE CASCADE,
                candidate_id TEXT NOT NULL,
                submitter_id TEXT NOT NULL,
                content TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                UNIQUE (slot_id, candidate_id),
                UNIQUE (slot_id, submitter_id, content_sha256)
            );
            CREATE TABLE IF NOT EXISTS votes (
                take_id INTEGER NOT NULL REFERENCES takes(take_id) ON DELETE CASCADE,
                voter_id TEXT NOT NULL,
                approved INTEGER NOT NULL CHECK (approved IN (0, 1)),
                PRIMARY KEY (take_id, voter_id)
            );
            """
        )

    def close(self) -> None:
        """Close the database connection."""
        self._connection.close()

    def __enter__(self) -> LocalExchange:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def create_slot(self, slot_id: str, quorum: int) -> dict[str, Any]:
        """Create a slot with a minimum distinct-voter quorum."""
        slot_id = _identifier(slot_id, "slot_id")
        quorum = _positive_integer(quorum, "quorum")
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO slots (slot_id, quorum) VALUES (?, ?)",
                    (slot_id, quorum),
                )
        except sqlite3.IntegrityError as exc:
            raise AlreadyExistsError(f"slot {slot_id!r} already exists") from exc
        return {"slot_id": slot_id, "quorum_required": quorum}

    def submit_take(
        self,
        slot_id: str,
        candidate_id: str,
        submitter_id: str,
        content: str,
    ) -> dict[str, Any]:
        """Submit content for a slot and return its stable SHA-256 digest."""
        slot_id = _identifier(slot_id, "slot_id")
        candidate_id = _identifier(candidate_id, "candidate_id")
        submitter_id = _identifier(submitter_id, "submitter_id")
        if not isinstance(content, str) or not content.strip():
            raise ExchangeError("content must be a non-empty string")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

        try:
            with self._connection:
                if self._connection.execute(
                    "SELECT 1 FROM slots WHERE slot_id = ?", (slot_id,)
                ).fetchone() is None:
                    raise NotFoundError(f"slot {slot_id!r} does not exist")
                try:
                    cursor = self._connection.execute(
                        """
                        INSERT INTO takes
                            (slot_id, candidate_id, submitter_id, content, content_sha256)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (slot_id, candidate_id, submitter_id, content, digest),
                    )
                except sqlite3.IntegrityError as exc:
                    duplicate = self._connection.execute(
                        """
                        SELECT 1 FROM takes
                        WHERE slot_id = ? AND submitter_id = ? AND content_sha256 = ?
                        """,
                        (slot_id, submitter_id, digest),
                    ).fetchone()
                    if duplicate is not None:
                        raise DuplicateTakeError(
                            "this submitter already submitted identical content to this slot"
                        ) from exc
                    raise AlreadyExistsError(
                        f"candidate {candidate_id!r} already exists in slot {slot_id!r}"
                    ) from exc
                take_id = cursor.lastrowid
        except ExchangeError:
            raise

        return {
            "take_id": take_id,
            "slot_id": slot_id,
            "candidate_id": candidate_id,
            "submitter_id": submitter_id,
            "content_sha256": digest,
        }

    def cast_vote(
        self,
        slot_id: str,
        candidate_id: str,
        voter_id: str,
        approved: bool = True,
    ) -> dict[str, Any]:
        """Record one approval or rejection by an identity for a candidate take."""
        slot_id = _identifier(slot_id, "slot_id")
        candidate_id = _identifier(candidate_id, "candidate_id")
        voter_id = _identifier(voter_id, "voter_id")
        if not isinstance(approved, bool):
            raise ExchangeError("approved must be a boolean")

        with self._connection:
            row = self._connection.execute(
                """
                SELECT take_id FROM takes
                WHERE slot_id = ? AND candidate_id = ?
                """,
                (slot_id, candidate_id),
            ).fetchone()
            if row is None:
                exists = self._connection.execute(
                    "SELECT 1 FROM slots WHERE slot_id = ?", (slot_id,)
                ).fetchone()
                if exists is None:
                    raise NotFoundError(f"slot {slot_id!r} does not exist")
                raise NotFoundError(
                    f"candidate {candidate_id!r} does not exist in slot {slot_id!r}"
                )
            try:
                self._connection.execute(
                    "INSERT INTO votes (take_id, voter_id, approved) VALUES (?, ?, ?)",
                    (row["take_id"], voter_id, int(approved)),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateVoteError(
                    f"voter {voter_id!r} has already voted on candidate {candidate_id!r}"
                ) from exc
        return {
            "slot_id": slot_id,
            "candidate_id": candidate_id,
            "voter_id": voter_id,
            "approved": approved,
        }

    def slot_status(self, slot_id: str) -> dict[str, Any]:
        """Return the explicit quorum status for a slot."""
        slot_id = _identifier(slot_id, "slot_id")
        with self._connection:
            slot = self._connection.execute(
                "SELECT quorum FROM slots WHERE slot_id = ?", (slot_id,)
            ).fetchone()
            if slot is None:
                raise NotFoundError(f"slot {slot_id!r} does not exist")
            voters = self._connection.execute(
                """
                SELECT COUNT(DISTINCT v.voter_id)
                FROM votes AS v
                JOIN takes AS t ON t.take_id = v.take_id
                WHERE t.slot_id = ?
                """,
                (slot_id,),
            ).fetchone()[0]
        quorum_met = voters >= slot["quorum"]
        return {
            "slot_id": slot_id,
            "quorum_required": slot["quorum"],
            "participating_voters": voters,
            "quorum_met": quorum_met,
            "quorum_status": "met" if quorum_met else "not_met",
        }

    def tally_slot(self, slot_id: str) -> dict[str, Any]:
        """Tally approvals and choose a deterministic winner when quorum is met.

        Ties are resolved by the lexicographically smallest candidate identifier.
        No winner is reported when quorum is unmet or no candidate has approvals.
        """
        slot_id = _identifier(slot_id, "slot_id")
        status = self.slot_status(slot_id)
        with self._connection:
            rows = self._connection.execute(
                """
                SELECT
                    t.candidate_id,
                    t.submitter_id,
                    t.content_sha256,
                    COUNT(v.voter_id) AS vote_count,
                    COALESCE(SUM(v.approved), 0) AS approval_count
                FROM takes AS t
                LEFT JOIN votes AS v ON v.take_id = t.take_id
                WHERE t.slot_id = ?
                GROUP BY t.take_id
                ORDER BY approval_count DESC, t.candidate_id COLLATE BINARY ASC
                """,
                (slot_id,),
            ).fetchall()
        candidates = [
            {
                "candidate_id": row["candidate_id"],
                "submitter_id": row["submitter_id"],
                "content_sha256": row["content_sha256"],
                "vote_count": row["vote_count"],
                "approval_count": row["approval_count"],
            }
            for row in rows
        ]
        winner_id = None
        if status["quorum_met"] and candidates and candidates[0]["approval_count"] > 0:
            winner_id = candidates[0]["candidate_id"]
        return {**status, "winner_id": winner_id, "candidates": candidates}
