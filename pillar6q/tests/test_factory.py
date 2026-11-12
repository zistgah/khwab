from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from crowd_cinema.broker import create_packet
from crowd_cinema.collation import collate, export_tei_apparatus, read_tei
from crowd_cinema.compiler import compile_shot, validate_shot
from crowd_cinema.subtitles import make_webvtt

ROOT = Path(__file__).resolve().parents[1]


class FactoryTests(unittest.TestCase):
    def test_collates_witnesses_from_multiple_tei_files(self) -> None:
        result = collate(
            [
                ROOT / "examples" / "tei" / "recension-a.xml",
                ROOT / "examples" / "tei" / "recension-b.xml",
            ]
        )
        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual(result["variants"][0]["variant_id"], "v1")
        witnesses = {entry["witness"] for entry in result["variants"][0]["readings"]}
        self.assertEqual(witnesses, {"#A", "#B", "#C"})

    def test_collation_exports_a_roundtrippable_tei_apparatus(self) -> None:
        result = collate(
            [
                ROOT / "examples" / "tei" / "recension-a.xml",
                ROOT / "examples" / "tei" / "recension-b.xml",
            ]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "collation.xml"
            output.write_text(export_tei_apparatus(result), encoding="utf-8")
            parsed = read_tei(output)
        self.assertEqual([variant.variant_id for variant in parsed], ["v1"])
        self.assertEqual(
            {reading.witness for reading in parsed[0].readings},
            {"#A", "#B", "#C"},
        )

    def test_rejects_invalid_duration_and_incomplete_motion_actions(self) -> None:
        specification = json.loads((ROOT / "examples" / "shot.json").read_text(encoding="utf-8"))
        specification["duration_sec"] = 16
        with self.assertRaisesRegex(ValueError, "duration_sec"):
            validate_shot(specification)
        specification["duration_sec"] = 12
        specification["crowd_action"] = " "
        with self.assertRaisesRegex(ValueError, "crowd_action"):
            validate_shot(specification)

    def test_rejects_malformed_genre_and_tei_xml(self) -> None:
        specification = json.loads((ROOT / "examples" / "shot.json").read_text(encoding="utf-8"))
        specification["genre"] = []
        with self.assertRaisesRegex(ValueError, "genre"):
            validate_shot(specification)
        with tempfile.TemporaryDirectory() as temporary_directory:
            broken_xml = Path(temporary_directory) / "broken.xml"
            broken_xml.write_text("<TEI>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid TEI XML"):
                collate([broken_xml])

    def test_compiles_shot_and_packet_digest_is_deterministic(self) -> None:
        shot = compile_shot(ROOT / "examples" / "shot.json")
        self.assertTrue(shot["actions"]["crowd"].startswith("Figures"))
        self.assertEqual(create_packet(shot), create_packet(shot))
        self.assertEqual(len(create_packet(shot)["packet_sha256"]), 64)

    def test_webvtt_uses_exact_shot_duration_and_rejects_empty_text(self) -> None:
        output = make_webvtt("sa", "उदाहरण", 12)
        self.assertIn("00:00:00.000 --> 00:00:12.000", output)
        self.assertIn("उदाहरण", output)
        with self.assertRaisesRegex(ValueError, "subtitle text"):
            make_webvtt("sa", " ", 12)

    def test_cli_writes_packet_json(self) -> None:
        import subprocess
        import sys

        process = subprocess.run(
            [sys.executable, "-m", "crowd_cinema", "packet", str(ROOT / "examples" / "shot.json")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(len(json.loads(process.stdout)["packet_sha256"]), 64)

    def test_collate_cli_writes_tei_export(self) -> None:
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "merged.xml"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "crowd_cinema",
                    "collate",
                    str(ROOT / "examples" / "tei" / "recension-a.xml"),
                    str(ROOT / "examples" / "tei" / "recension-b.xml"),
                    "--tei-output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(len(read_tei(output)), 1)


if __name__ == "__main__":
    unittest.main()
