from __future__ import annotations

import hashlib
import importlib.util
import unittest

from crowd_cinema.attestation import (
    INVALID,
    UNVERIFIED,
    UNSUPPORTED,
    VERIFIED,
    inspect_opentimestamps_receipt,
    verify_ed25519,
    verify_sha256,
    verify_source_attestation,
)


class SourceAttestationTests(unittest.TestCase):
    # Public RFC 8032 test-vector data; no private key is included.
    public_key = bytes.fromhex(
        "d75a980182b10ab7d54bfed3c964073a"
        "0ee172f3daa62325af021a68f707511a"
    )
    other_public_key = bytes.fromhex(
        "3d4017c3e843895a92b70aa74d1b7ebc"
        "9c982ccf2ec4968cc0cd55f12af4660c"
    )
    empty_message_signature = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a"
        "84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46b"
        "d25bf5f0595bbe24655141438e7a100b"
    )

    def test_sha256_hashes_exact_bytes_and_reports_tampering(self) -> None:
        content = b"source bytes\r\n"
        digest = hashlib.sha256(content).hexdigest()
        self.assertEqual(verify_sha256(content, digest.upper())["status"], VERIFIED)

        result = verify_sha256(content + b" ", digest)
        self.assertEqual(result["status"], INVALID)
        self.assertFalse(result["matches"])
        self.assertIn("exact content bytes", result["failure"])

    def test_sha256_rejects_malformed_digest(self) -> None:
        result = verify_sha256(b"content", "not-a-sha256")
        self.assertEqual(result["status"], INVALID)
        self.assertIn("64 hexadecimal", result["failure"])

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "install the optional crypto extra")
    def test_ed25519_accepts_signature_for_supplied_key_only(self) -> None:
        valid = verify_ed25519(
            b"",
            self.empty_message_signature,
            self.public_key,
            key_id="declared-key",
            signer_id="declared-signer",
        )
        self.assertEqual(valid["status"], VERIFIED)
        self.assertEqual(valid["key_id"], "declared-key")
        self.assertEqual(valid["signer_id"], "declared-signer")
        self.assertFalse(valid["identity_authenticated"])

        wrong_key = verify_ed25519(b"", self.empty_message_signature, self.other_public_key)
        self.assertEqual(wrong_key["status"], INVALID)
        self.assertIn("does not match", wrong_key["failure"])

        tampered = verify_ed25519(b"x", self.empty_message_signature, self.public_key)
        self.assertEqual(tampered["status"], INVALID)

    def test_source_gate_requires_digest_and_signature(self) -> None:
        result = verify_source_attestation(b"source", hashlib.sha256(b"source").hexdigest(), None, None)
        self.assertEqual(result["status"], UNVERIFIED)
        self.assertEqual(result["digest"]["status"], VERIFIED)
        self.assertFalse(result["identity_authenticated"])

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "install the optional crypto extra")
    def test_source_gate_passes_only_when_digest_and_signature_match(self) -> None:
        digest = hashlib.sha256(b"").hexdigest()
        valid = verify_source_attestation(
            b"",
            digest,
            self.empty_message_signature,
            self.public_key,
            key_id="declared-key",
            signer_id="declared-signer",
        )
        self.assertEqual(valid["status"], VERIFIED)

        tampered = verify_source_attestation(
            b"tampered",
            digest,
            self.empty_message_signature,
            self.public_key,
        )
        self.assertEqual(tampered["status"], INVALID)

    def test_opentimestamps_never_claims_verification(self) -> None:
        result = inspect_opentimestamps_receipt(b"not an OpenTimestamps receipt")
        self.assertFalse(result["verified"])
        if importlib.util.find_spec("opentimestamps") is None:
            self.assertEqual(result["status"], UNSUPPORTED)
        else:
            self.assertNotEqual(result["status"], VERIFIED)


if __name__ == "__main__":
    unittest.main()
