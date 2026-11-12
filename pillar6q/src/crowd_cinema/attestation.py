"""Pure source-attestation checks for exact bytes and detached signatures.

SHA-256 and Ed25519 verification establish byte integrity and that a signature
matches the supplied public key. They do not authenticate key or signer
identifiers, establish a signer's real-world identity or authority, or establish
scholarly truth. OpenTimestamps receipts are only parsed when its library is
available; parsing alone is never reported as timestamp verification.
"""

from __future__ import annotations

import hashlib
import io
import re
import struct
from typing import Any


VERIFIED = "verified"
INVALID = "invalid"
UNVERIFIED = "unverified"
UNSUPPORTED = "unsupported"

_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}\Z")
_ED25519_PUBLIC_KEY_BYTES = 32
_ED25519_SIGNATURE_BYTES = 64


def verify_sha256(content: bytes, expected_digest: str) -> dict[str, Any]:
    """Compare a declared SHA-256 digest with the hash of the exact input bytes."""
    if not isinstance(content, bytes):
        return {
            "status": INVALID,
            "algorithm": "sha256",
            "expected_digest": expected_digest if isinstance(expected_digest, str) else None,
            "actual_digest": None,
            "matches": False,
            "failure": "content must be bytes",
        }

    actual_digest = hashlib.sha256(content).hexdigest()
    if not isinstance(expected_digest, str) or not _SHA256_RE.fullmatch(expected_digest):
        return {
            "status": INVALID,
            "algorithm": "sha256",
            "expected_digest": expected_digest if isinstance(expected_digest, str) else None,
            "actual_digest": actual_digest,
            "matches": False,
            "failure": "expected_digest must contain exactly 64 hexadecimal characters",
        }

    matches = actual_digest == expected_digest.lower()
    return {
        "status": VERIFIED if matches else INVALID,
        "algorithm": "sha256",
        "expected_digest": expected_digest,
        "actual_digest": actual_digest,
        "matches": matches,
        "failure": None if matches else "SHA-256 digest does not match the exact content bytes",
    }


def verify_ed25519(
    content: bytes,
    signature: bytes,
    public_key: bytes,
    *,
    key_id: str | None = None,
    signer_id: str | None = None,
) -> dict[str, Any]:
    """Verify a detached Ed25519 signature using caller-supplied raw public-key bytes.

    ``key_id`` and ``signer_id`` are carried through as declared labels only.
    This function does not resolve, validate, or authenticate either identifier.
    Install the optional ``crypto`` extra to enable Ed25519 verification.
    """
    result: dict[str, Any] = {
        "status": UNVERIFIED,
        "algorithm": "Ed25519",
        "key_id": key_id,
        "signer_id": signer_id,
        "identity_authenticated": False,
        "failure": None,
    }
    if key_id is not None and (not isinstance(key_id, str) or not key_id.strip()):
        result.update(status=INVALID, failure="key_id must be a non-empty declared identifier")
        return result
    if signer_id is not None and (not isinstance(signer_id, str) or not signer_id.strip()):
        result.update(status=INVALID, failure="signer_id must be a non-empty declared identifier")
        return result
    if not isinstance(content, bytes):
        result.update(status=INVALID, failure="content must be bytes")
        return result
    if not isinstance(signature, bytes) or len(signature) != _ED25519_SIGNATURE_BYTES:
        result.update(status=INVALID, failure="Ed25519 signature must be exactly 64 bytes")
        return result
    if not isinstance(public_key, bytes) or len(public_key) != _ED25519_PUBLIC_KEY_BYTES:
        result.update(status=INVALID, failure="Ed25519 public key must be exactly 32 raw bytes")
        return result

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        result.update(
            status=UNSUPPORTED,
            failure="Ed25519 verifier unavailable; install the optional 'crypto' extra",
        )
        return result

    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, content)
    except InvalidSignature:
        result.update(status=INVALID, failure="Ed25519 signature does not match this content and public key")
    except ValueError:
        result.update(status=INVALID, failure="invalid Ed25519 public key")
    else:
        result.update(status=VERIFIED)
    return result


def verify_source_attestation(
    content: bytes,
    expected_sha256: str,
    signature: bytes | None,
    public_key: bytes | None,
    *,
    key_id: str | None = None,
    signer_id: str | None = None,
) -> dict[str, Any]:
    """Verify a source's exact-byte digest and, when provided, its Ed25519 signature.

    The aggregate ``status`` is suitable for a source-attestation gate:
    ``verified`` means both checks passed, ``invalid`` means a supplied check
    failed, ``unsupported`` means required cryptography is unavailable, and
    ``unverified`` means a signature or public key was not supplied.
    """
    digest_result = verify_sha256(content, expected_sha256)
    if signature is None and public_key is None:
        signature_result: dict[str, Any] = {
            "status": UNVERIFIED,
            "algorithm": "Ed25519",
            "key_id": key_id,
            "signer_id": signer_id,
            "identity_authenticated": False,
            "failure": "signature and public key were not supplied",
        }
    elif signature is None or public_key is None:
        signature_result = {
            "status": UNVERIFIED,
            "algorithm": "Ed25519",
            "key_id": key_id,
            "signer_id": signer_id,
            "identity_authenticated": False,
            "failure": "both signature and public key are required",
        }
    else:
        signature_result = verify_ed25519(
            content,
            signature,
            public_key,
            key_id=key_id,
            signer_id=signer_id,
        )

    checks = (digest_result["status"], signature_result["status"])
    if INVALID in checks:
        status = INVALID
    elif UNSUPPORTED in checks:
        status = UNSUPPORTED
    elif all(check == VERIFIED for check in checks):
        status = VERIFIED
    else:
        status = UNVERIFIED

    return {
        "status": status,
        "digest": digest_result,
        "signature": signature_result,
        "identity_authenticated": False,
    }


def inspect_opentimestamps_receipt(receipt: bytes) -> dict[str, Any]:
    """Parse an OpenTimestamps receipt if its library is installed, without verifying it."""
    if not isinstance(receipt, bytes):
        return {
            "status": INVALID,
            "format": "opentimestamps",
            "parsed": False,
            "verified": False,
            "failure": "receipt must be bytes",
        }

    try:
        from opentimestamps.core.timestamp import DetachedTimestampFile
    except ImportError:
        return {
            "status": UNSUPPORTED,
            "format": "opentimestamps",
            "parsed": False,
            "verified": False,
            "failure": "OpenTimestamps parser unavailable; receipt was not checked",
        }

    deserialize = getattr(DetachedTimestampFile, "deserialize", None)
    if not callable(deserialize):
        return {
            "status": UNSUPPORTED,
            "format": "opentimestamps",
            "parsed": False,
            "verified": False,
            "failure": "installed OpenTimestamps library exposes no supported receipt parser",
        }
    try:
        deserialize(io.BytesIO(receipt))
    except (ValueError, EOFError, TypeError, struct.error, IndexError):
        return {
            "status": INVALID,
            "format": "opentimestamps",
            "parsed": False,
            "verified": False,
            "failure": "receipt could not be parsed",
        }
    return {
        "status": UNVERIFIED,
        "format": "opentimestamps",
        "parsed": True,
        "verified": False,
        "failure": "parsing does not verify calendar attestations or prove a timestamp",
    }
