from __future__ import annotations

import unittest
import json
import subprocess
import sys
from pathlib import Path

from crowd_cinema.formal_checks import run_bounded_checks


class BoundedFormalCheckTests(unittest.TestCase):
    def test_exhaustive_bounded_checks_report_pass_and_limits(self) -> None:
        report = run_bounded_checks(
            max_authorities=3,
            max_voters=3,
            max_candidates=2,
            max_shots=3,
        )
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["formal_proof"])
        self.assertTrue(all(check["models_checked"] > 0 for check in report["checks"].values()))
        self.assertTrue(any("not CBMC" in limit for limit in report["limitations"]))

    def test_invalid_or_unbounded_parameters_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integers"):
            run_bounded_checks(max_voters=True)
        with self.assertRaisesRegex(ValueError, "runtime-safe"):
            run_bounded_checks(max_shots=9)

    def test_cli_emits_machine_readable_bounded_check_report(self) -> None:
        root = Path(__file__).resolve().parents[1]
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "crowd_cinema",
                "formal-check",
                "--max-authorities",
                "2",
                "--max-voters",
                "2",
                "--max-candidates",
                "2",
                "--max-shots",
                "2",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["formal_proof"])


if __name__ == "__main__":
    unittest.main()
