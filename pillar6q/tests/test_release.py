from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from crowd_cinema.release import build_release_bundle


class ReleaseBundleTests(unittest.TestCase):
    def test_builds_reproducible_bundle_with_verified_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "project"
            root.mkdir()
            (root / "spec.json").write_text('{"revision":1}\n', encoding="utf-8")
            (root / "notes.txt").write_text("reviewed locally\n", encoding="utf-8")
            first = Path(temporary_directory) / "first.zip"
            second = Path(temporary_directory) / "second.zip"

            first_result = build_release_bundle(root, ["notes.txt", "spec.json"], "1.2.3", first)
            second_result = build_release_bundle(root, ["spec.json", "notes.txt"], "1.2.3", second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first_result["sha256"], second_result["sha256"])
            self.assertFalse(first_result["published"])
            self.assertFalse(first_result["signed"])
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["notes.txt", "spec.json", "release-manifest.json"],
                )
                manifest = json.loads(archive.read("release-manifest.json"))
                for entry in manifest["artifacts"]:
                    self.assertEqual(
                        hashlib.sha256(archive.read(entry["path"])).hexdigest(),
                        entry["sha256"],
                    )

    def test_rejects_traversal_duplicates_invalid_versions_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "project"
            root.mkdir()
            (root / "artifact.txt").write_text("safe", encoding="utf-8")
            outside = Path(temporary_directory) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "normalized relative"):
                build_release_bundle(root, ["../outside.txt"], "1.0.0", root / "release.zip")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                build_release_bundle(root, ["artifact.txt", "artifact.txt"], "1.0.0", root / "release.zip")
            with self.assertRaisesRegex(ValueError, "semantic"):
                build_release_bundle(root, ["artifact.txt"], "latest", root / "release.zip")
            with self.assertRaisesRegex(ValueError, "semantic"):
                build_release_bundle(root, ["artifact.txt"], "1.0.0-01", root / "release.zip")
            with self.assertRaisesRegex(ValueError, "must not overwrite"):
                build_release_bundle(root, ["artifact.txt"], "1.0.0", root / "artifact.txt")
            try:
                (root / "link.txt").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaisesRegex(ValueError, "regular, non-symlink"):
                build_release_bundle(root, ["link.txt"], "1.0.0", root / "release.zip")

    def test_release_bundle_cli_reports_local_unsigned_state(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary_directory:
            artifact = Path(temporary_directory) / "artifact.txt"
            artifact.write_text("artifact", encoding="utf-8")
            output = Path(temporary_directory) / "release.zip"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "crowd_cinema",
                    "release-bundle",
                    "--root",
                    temporary_directory,
                    "--output",
                    str(output),
                    "1.0.0",
                    "artifact.txt",
                ],
                cwd=repository_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result["status"], "built")
            self.assertFalse(result["published"])


if __name__ == "__main__":
    unittest.main()
