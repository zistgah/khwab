from __future__ import annotations

import json
import unittest
from pathlib import Path

from crowd_cinema.gymnasium import export_html, load_notebook, validate_notebook


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"


class GymnasiumTests(unittest.TestCase):
    def test_studio_notebooks_have_valid_fields_and_runnable_code_cells(self) -> None:
        paths = sorted(NOTEBOOKS.glob("*.ipynb"))
        self.assertEqual(len(paths), 5)
        for path in paths:
            with self.subTest(notebook=path.name):
                notebook = load_notebook(path)
                self.assertEqual(notebook["nbformat"], 4)
                self.assertTrue(any(cell["cell_type"] == "markdown" for cell in notebook["cells"]))
                code_cells = [
                    cell for cell in notebook["cells"] if cell["cell_type"] == "code"
                ]
                self.assertTrue(code_cells)
                namespace: dict[str, object] = {"__name__": "__main__"}
                for cell in code_cells:
                    exec(compile("".join(cell["source"]), path.name, "exec"), namespace)

    def test_validator_rejects_missing_and_invalid_cell_fields(self) -> None:
        valid = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"title": "Example"},
            "cells": [
                {
                    "cell_type": "code",
                    "id": "cell-one",
                    "metadata": {},
                    "execution_count": None,
                    "outputs": [],
                    "source": "print('ok')",
                }
            ],
        }
        validate_notebook(valid)

        invalid = json.loads(json.dumps(valid))
        invalid["cells"][0]["source"] = 4
        with self.assertRaisesRegex(ValueError, r"cells\[0\]\.source"):
            validate_notebook(invalid)

        invalid = json.loads(json.dumps(valid))
        invalid["cells"][0]["outputs"] = [
            {"output_type": "stream", "name": "stdout", "text": [5]}
        ]
        with self.assertRaisesRegex(ValueError, "list of strings"):
            validate_notebook(invalid)

    def test_html_export_includes_code_and_saved_output_without_interpreting_html(self) -> None:
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"title": "Safe <studio>"},
            "cells": [
                {
                    "cell_type": "markdown",
                    "id": "intro",
                    "metadata": {},
                    "source": "An <instruction>.",
                },
                {
                    "cell_type": "code",
                    "id": "code",
                    "metadata": {},
                    "execution_count": 1,
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": "<script>alert(1)</script>",
                        }
                    ],
                    "source": "print('<script>')",
                },
            ],
        }
        rendered = export_html(notebook)
        self.assertIn("print(&#x27;&lt;script&gt;&#x27;)", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertIn("&lt;instruction&gt;", rendered)
        self.assertIn("execution count: 1", rendered)
        self.assertIn("<style>", rendered)
        self.assertNotIn("<script>", rendered)


if __name__ == "__main__":
    unittest.main()
