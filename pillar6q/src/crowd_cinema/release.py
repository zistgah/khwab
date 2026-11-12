"""Reproducible, local release bundles with per-artifact integrity digests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from typing import Any
import zipfile

_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_MANIFEST_NAME = "release-manifest.json"


def build_release_bundle(
    project_root: str | Path,
    artifact_paths: list[str],
    version: str,
    output_path: str | Path,
) -> dict[str, Any]:
    """Build a deterministic ZIP bundle and return its digest and inventory.

    The bundle records content integrity and the supplied version string. It
    does not publish artifacts, sign the bundle, or attest to release approval.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ValueError(f"project_root is not a directory: {root}")
    match = _VERSION_PATTERN.fullmatch(version) if isinstance(version, str) else None
    if match is None or any(
        identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0")
        for identifier in (match.group(4) or "").split(".")
    ):
        raise ValueError("version must be semantic MAJOR.MINOR.PATCH with valid optional prerelease/build metadata")
    if not isinstance(artifact_paths, list) or not artifact_paths:
        raise ValueError("artifact_paths must be a non-empty list")

    normalized_paths: list[tuple[str, Path]] = []
    seen_paths: set[str] = set()
    for raw_path in artifact_paths:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("each artifact path must be a non-empty string")
        archive_name = PurePosixPath(raw_path.replace("\\", "/"))
        if archive_name.is_absolute() or any(part in {"", ".", ".."} for part in archive_name.parts):
            raise ValueError(f"artifact path must be a normalized relative path: {raw_path}")
        archive_path = archive_name.as_posix()
        if archive_path == _MANIFEST_NAME:
            raise ValueError(f"artifact path is reserved: {_MANIFEST_NAME}")
        if archive_path in seen_paths:
            raise ValueError(f"duplicate artifact path: {archive_path}")
        seen_paths.add(archive_path)
        source = root.joinpath(*archive_name.parts)
        current = root
        if source.is_symlink():
            raise ValueError(f"artifact must be a regular, non-symlink file: {raw_path}")
        for component in archive_name.parts[:-1]:
            current = current / component
            if current.is_symlink():
                raise ValueError(f"artifact must be a regular, non-symlink file: {raw_path}")
        source = source.resolve()
        try:
            source.relative_to(root)
        except ValueError as error:
            raise ValueError(f"artifact path escapes project_root: {raw_path}") from error
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"artifact must be a regular, non-symlink file: {raw_path}")
        normalized_paths.append((archive_path, source))

    entries = []
    artifacts: list[tuple[str, Path, int, str]] = []
    for archive_path, source in sorted(normalized_paths):
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as artifact_file:
            while chunk := artifact_file.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        artifact_digest = digest.hexdigest()
        artifacts.append((archive_path, source, size, artifact_digest))
        entries.append(
            {
                "path": archive_path,
                "size_bytes": size,
                "sha256": artifact_digest,
            }
        )
    manifest = {
        "format": "crowd-cinema-release-bundle-v1",
        "version": version,
        "artifacts": entries,
        "limitations": [
            "This local bundle is not published or signed.",
            "The supplied version is not an approval or semantic-version policy check.",
        ],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )

    destination = Path(output_path)
    if destination.is_symlink():
        raise ValueError(f"output path must not be a symlink: {destination}")
    resolved_destination = destination.resolve()
    if any(resolved_destination == source for _, source in normalized_paths):
        raise ValueError("output path must not overwrite an included artifact")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    ) as temporary_file:
        temporary_destination = Path(temporary_file.name)
    try:
        with zipfile.ZipFile(temporary_destination, "w", compression=zipfile.ZIP_STORED) as archive:
            for archive_path, source, expected_size, expected_digest in artifacts:
                digest = hashlib.sha256()
                size = 0
                with source.open("rb") as source_file, archive.open(
                    _deterministic_info(archive_path), "w"
                ) as archive_file:
                    while chunk := source_file.read(1024 * 1024):
                        digest.update(chunk)
                        size += len(chunk)
                        archive_file.write(chunk)
                if size != expected_size or digest.hexdigest() != expected_digest:
                    raise ValueError(f"artifact changed while building release bundle: {archive_path}")
            archive.writestr(_deterministic_info(_MANIFEST_NAME), manifest_bytes)
        os.replace(temporary_destination, destination)
    finally:
        if temporary_destination.exists():
            temporary_destination.unlink()

    bundle_digest = hashlib.sha256()
    bundle_size = 0
    with destination.open("rb") as bundle_file:
        while chunk := bundle_file.read(1024 * 1024):
            bundle_digest.update(chunk)
            bundle_size += len(chunk)
    return {
        "status": "built",
        "version": version,
        "path": str(destination),
        "size_bytes": bundle_size,
        "sha256": bundle_digest.hexdigest(),
        "artifact_count": len(entries),
        "manifest": manifest,
        "published": False,
        "signed": False,
    }


def _deterministic_info(path: str) -> zipfile.ZipInfo:
    entry = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_STORED
    entry.create_system = 3
    entry.external_attr = (stat.S_IFREG | 0o644) << 16
    return entry
