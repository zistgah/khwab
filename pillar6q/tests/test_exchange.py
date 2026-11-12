from __future__ import annotations

import hashlib
import unittest

from crowd_cinema.exchange import (
    AlreadyExistsError,
    DuplicateTakeError,
    DuplicateVoteError,
    ExchangeError,
    LocalExchange,
    NotFoundError,
)


class ExchangeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange = LocalExchange()

    def tearDown(self) -> None:
        self.exchange.close()

    def test_submissions_store_content_digest_and_reject_duplicate_content(self) -> None:
        self.exchange.create_slot("scene-1", quorum=2)
        result = self.exchange.submit_take(
            "scene-1", "take-b", "volunteer-a", "A brief scene."
        )
        self.assertEqual(
            result["content_sha256"],
            hashlib.sha256(b"A brief scene.").hexdigest(),
        )
        with self.assertRaisesRegex(DuplicateTakeError, "identical content"):
            self.exchange.submit_take(
                "scene-1", "take-c", "volunteer-a", "A brief scene."
            )
        self.assertEqual(
            self.exchange.submit_take(
                "scene-1", "take-c", "volunteer-b", "A brief scene."
            )["candidate_id"],
            "take-c",
        )

    def test_votes_are_unique_per_identity_and_take_but_allow_other_takes(self) -> None:
        self.exchange.create_slot("scene-1", quorum=2)
        self.exchange.submit_take("scene-1", "take-a", "maker-a", "First take")
        self.exchange.submit_take("scene-1", "take-b", "maker-b", "Second take")

        self.exchange.cast_vote("scene-1", "take-a", "voter-1")
        with self.assertRaisesRegex(DuplicateVoteError, "already voted"):
            self.exchange.cast_vote("scene-1", "take-a", "voter-1", approved=False)
        self.exchange.cast_vote("scene-1", "take-b", "voter-1")
        self.exchange.cast_vote("scene-1", "take-a", "voter-2")

        status = self.exchange.slot_status("scene-1")
        self.assertEqual(status["participating_voters"], 2)
        self.assertTrue(status["quorum_met"])
        self.assertEqual(status["quorum_status"], "met")

    def test_tally_uses_candidate_identifier_for_ties_and_reports_quorum(self) -> None:
        self.exchange.create_slot("scene-1", quorum=2)
        self.exchange.submit_take("scene-1", "take-z", "maker-z", "Z")
        self.exchange.submit_take("scene-1", "take-a", "maker-a", "A")
        self.exchange.cast_vote("scene-1", "take-z", "voter-1")
        self.exchange.cast_vote("scene-1", "take-a", "voter-1")

        tally = self.exchange.tally_slot("scene-1")
        self.assertFalse(tally["quorum_met"])
        self.assertEqual(tally["quorum_status"], "not_met")
        self.assertIsNone(tally["winner_id"])
        self.exchange.cast_vote("scene-1", "take-z", "voter-2")
        self.exchange.cast_vote("scene-1", "take-a", "voter-2")

        tally = self.exchange.tally_slot("scene-1")
        self.assertTrue(tally["quorum_met"])
        self.assertEqual(tally["winner_id"], "take-a")
        self.assertEqual(
            [candidate["candidate_id"] for candidate in tally["candidates"]],
            ["take-a", "take-z"],
        )

    def test_rejections_count_toward_quorum_not_approval_tally(self) -> None:
        self.exchange.create_slot("scene-1", quorum=1)
        self.exchange.submit_take("scene-1", "take-a", "maker-a", "A")
        self.exchange.cast_vote("scene-1", "take-a", "voter-1", approved=False)
        tally = self.exchange.tally_slot("scene-1")
        self.assertTrue(tally["quorum_met"])
        self.assertEqual(tally["candidates"][0]["vote_count"], 1)
        self.assertEqual(tally["candidates"][0]["approval_count"], 0)
        self.assertIsNone(tally["winner_id"])

    def test_invalid_and_missing_records_raise_clear_errors_without_partial_state(self) -> None:
        with self.assertRaisesRegex(ExchangeError, "positive integer"):
            self.exchange.create_slot("scene-1", quorum=True)
        self.exchange.create_slot("scene-1", quorum=1)
        with self.assertRaisesRegex(NotFoundError, "does not exist"):
            self.exchange.submit_take("missing", "take-a", "maker-a", "A")
        with self.assertRaisesRegex(NotFoundError, "candidate"):
            self.exchange.cast_vote("scene-1", "unknown", "voter-1")
        with self.assertRaisesRegex(AlreadyExistsError, "already exists"):
            self.exchange.create_slot("scene-1", quorum=1)
        with self.assertRaisesRegex(ExchangeError, "boolean"):
            self.exchange.cast_vote("scene-1", "unknown", "voter-1", approved=1)
        self.assertEqual(self.exchange.tally_slot("scene-1")["candidates"], [])


if __name__ == "__main__":
    unittest.main()
