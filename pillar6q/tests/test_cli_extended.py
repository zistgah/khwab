from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExtendedCliTests(unittest.TestCase):
    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "crowd_cinema", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_attestation_cli_reports_digest_without_claiming_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            content_path = Path(temporary_directory) / "source.txt"
            content_path.write_bytes(b"exact source bytes")
            digest = hashlib.sha256(content_path.read_bytes()).hexdigest()

            process = self._run(
                "verify-attestation",
                str(content_path),
                "--sha256",
                digest,
            )

            self.assertEqual(process.returncode, 1, process.stderr)
            report = json.loads(process.stdout)
            self.assertEqual(report["status"], "unverified")
            self.assertEqual(report["digest"]["status"], "verified")
            self.assertFalse(report["identity_authenticated"])

    def test_timeline_cli_writes_deterministic_otio_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "clips.json"
            output_path = Path(temporary_directory) / "timeline.otio"
            input_path.write_text(
                json.dumps(
                    {
                        "clips": [
                            {
                                "shot_id": "one",
                                "media_uri": "one.mp4",
                                "pts": 0,
                                "duration_pts": 24,
                                "time_base": {"numerator": 1, "denominator": 24},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            process = self._run(
                "timeline",
                "--input",
                str(input_path),
                "--otio-output",
                str(output_path),
            )

            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(process.stdout)
            self.assertTrue(report["continuity"]["continuous"])
            timeline = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(timeline["OTIO_SCHEMA"], "Timeline.1")

    def test_gymnasium_cli_checks_and_exports_local_notebook(self) -> None:
        notebook = ROOT / "notebooks" / "01-tei-collation.ipynb"
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "studio.html"
            checked = self._run("gymnasium", "check", str(notebook))
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout)["status"], "valid")

            exported = self._run(
                "gymnasium",
                "export",
                str(notebook),
                "--output",
                str(output_path),
            )
            self.assertEqual(exported.returncode, 0, exported.stderr)
            html = output_path.read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", html)
            self.assertIn("TEI", html)


if __name__ == "__main__":
    unittest.main()
