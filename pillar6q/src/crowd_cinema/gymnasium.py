"""Local validation and static HTML export for instructional studio notebooks."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping


def _text(value: Any, field: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        return "".join(value)
    raise ValueError(f"{field} must be a string or a list of strings")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _nonnegative_integer(value: Any, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")


def _validate_output(output: Any, cell_index: int, output_index: int) -> None:
    prefix = f"cells[{cell_index}].outputs[{output_index}]"
    if not isinstance(output, Mapping):
        raise ValueError(f"{prefix} must be an object")
    output_type = output.get("output_type")
    if output_type == "stream":
        if output.get("name") not in {"stdout", "stderr"}:
            raise ValueError(f"{prefix}.name must be stdout or stderr")
        _text(output.get("text"), f"{prefix}.text")
    elif output_type in {"display_data", "execute_result"}:
        data = _mapping(output.get("data"), f"{prefix}.data")
        for mime_type, value in data.items():
            if not isinstance(mime_type, str) or not mime_type:
                raise ValueError(f"{prefix}.data keys must be non-empty MIME strings")
            try:
                json.dumps(value, allow_nan=False)
            except (TypeError, ValueError, RecursionError) as error:
                raise ValueError(
                    f"{prefix}.data[{mime_type!r}] must contain JSON-compatible data"
                ) from error
        _mapping(output.get("metadata"), f"{prefix}.metadata")
        if output_type == "execute_result":
            _nonnegative_integer(
                output.get("execution_count"), f"{prefix}.execution_count", nullable=True
            )
    elif output_type == "error":
        for field in ("ename", "evalue"):
            if not isinstance(output.get(field), str):
                raise ValueError(f"{prefix}.{field} must be a string")
        traceback = output.get("traceback")
        if not isinstance(traceback, list) or not all(
            isinstance(line, str) for line in traceback
        ):
            raise ValueError(f"{prefix}.traceback must be a list of strings")
    else:
        raise ValueError(f"{prefix}.output_type is unsupported")


def validate_notebook(notebook: Any) -> None:
    """Validate core nbformat 4 fields used by the local studio notebooks."""
    if not isinstance(notebook, Mapping):
        raise ValueError("notebook must be an object")
    if notebook.get("nbformat") != 4:
        raise ValueError("nbformat must be 4")
    minor = notebook.get("nbformat_minor")
    if isinstance(minor, bool) or not isinstance(minor, int) or minor < 5:
        raise ValueError("nbformat_minor must be an integer of 5 or greater")
    metadata = _mapping(notebook.get("metadata"), "metadata")
    if "title" in metadata and not isinstance(metadata["title"], str):
        raise ValueError("metadata.title must be a string")
    cells = notebook.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError("cells must be a non-empty list")

    identifiers: set[str] = set()
    for index, cell in enumerate(cells):
        prefix = f"cells[{index}]"
        if not isinstance(cell, Mapping):
            raise ValueError(f"{prefix} must be an object")
        cell_type = cell.get("cell_type")
        if cell_type not in {"markdown", "code", "raw"}:
            raise ValueError(f"{prefix}.cell_type is unsupported")
        cell_id = cell.get("id")
        if not isinstance(cell_id, str) or not cell_id.strip():
            raise ValueError(f"{prefix}.id must be a non-empty string")
        if cell_id in identifiers:
            raise ValueError(f"{prefix}.id must be unique")
        identifiers.add(cell_id)
        _text(cell.get("source"), f"{prefix}.source")
        _mapping(cell.get("metadata"), f"{prefix}.metadata")
        if cell_type == "code":
            if "execution_count" not in cell:
                raise ValueError(f"{prefix}.execution_count is required")
            _nonnegative_integer(
                cell.get("execution_count"), f"{prefix}.execution_count", nullable=True
            )
            outputs = cell.get("outputs")
            if not isinstance(outputs, list):
                raise ValueError(f"{prefix}.outputs must be a list")
            for output_index, output in enumerate(outputs):
                _validate_output(output, index, output_index)
        elif "outputs" in cell or "execution_count" in cell:
            raise ValueError(f"{prefix} non-code cells cannot have code execution fields")
        if "attachments" in cell:
            _mapping(cell["attachments"], f"{prefix}.attachments")


def load_notebook(path: str | Path) -> dict[str, Any]:
    """Load and validate a notebook JSON file."""
    notebook_path = Path(path)
    try:
        with notebook_path.open(encoding="utf-8") as source:
            notebook = json.load(source)
    except json.JSONDecodeError as error:
        raise ValueError(f"{notebook_path}: invalid notebook JSON: {error}") from error
    validate_notebook(notebook)
    return notebook


def _display_output(output: Mapping[str, Any]) -> str:
    if output["output_type"] == "stream":
        return _text(output["text"], "output.text")
    if output["output_type"] == "error":
        return "\n".join(output["traceback"]) or (
            f'{output["ename"]}: {output["evalue"]}'
        )
    data = output["data"]
    if "text/plain" in data:
        value = data["text/plain"]
        return _text(value, "output.data.text/plain")
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def _render_markdown(source: str) -> str:
    rendered: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    code_lines: list[str] | None = None

    def flush_paragraph() -> None:
        if paragraph:
            rendered.append(f"<p>{html.escape(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            rendered.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    for line in source.splitlines():
        if line.startswith("```"):
            flush_paragraph()
            flush_list()
            if code_lines is None:
                code_lines = []
            else:
                rendered.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = None
            continue
        if code_lines is not None:
            code_lines.append(line)
            continue
        heading = line.lstrip("#")
        level = len(line) - len(heading)
        if 1 <= level <= 6 and heading.startswith(" "):
            flush_paragraph()
            flush_list()
            rendered.append(
                f"<h{level}>{html.escape(heading.lstrip())}</h{level}>"
            )
        elif line.startswith("- "):
            flush_paragraph()
            list_items.append(html.escape(line[2:]))
        elif not line.strip():
            flush_paragraph()
            flush_list()
        else:
            flush_list()
            paragraph.append(line.strip())

    if code_lines is not None:
        rendered.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    flush_paragraph()
    flush_list()
    return "\n".join(rendered)


def export_html(notebook: Mapping[str, Any], title: str | None = None) -> str:
    """Render all notebook cells and saved outputs as self-contained escaped HTML."""
    validate_notebook(notebook)
    metadata = notebook["metadata"]
    page_title = title or metadata.get("title") or "Studio notebook"
    pieces = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(page_title)}</title>",
        "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#202124}"
        "section{border-top:1px solid #ddd;padding:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;"
        "background:#f5f5f5;padding:1rem;border-radius:.35rem}h1{font-size:1.6rem}"
        ".output{border-left:3px solid #999;margin:.5rem 0;padding-left:.75rem}"
        "</style></head><body>",
        f"<h1>{html.escape(page_title)}</h1>",
    ]
    for index, cell in enumerate(notebook["cells"], start=1):
        source = _text(cell["source"], f"cells[{index - 1}].source")
        pieces.append(f'<section id="cell-{html.escape(cell["id"], quote=True)}">')
        label = cell["cell_type"]
        if label == "code":
            count = cell["execution_count"]
            state = f"execution count: {count}" if count is not None else "not executed"
            label = f"{label} ({state})"
        pieces.append(f"<h2>Cell {index}: {html.escape(label)}</h2>")
        if cell["cell_type"] == "markdown":
            pieces.append(_render_markdown(source))
        else:
            pieces.append(
                f'<pre class="{html.escape(cell["cell_type"], quote=True)}">'
                f"{html.escape(source)}</pre>"
            )
        if cell["cell_type"] == "code":
            for output in cell["outputs"]:
                rendered = _display_output(output)
                pieces.append(f'<pre class="output">{html.escape(rendered)}</pre>')
        pieces.append("</section>")
    pieces.append("</body></html>")
    return "\n".join(pieces)


def export_notebook(path: str | Path, output_path: str | Path) -> Path:
    """Validate a notebook and write its self-contained static HTML export."""
    destination = Path(output_path)
    rendered = export_html(load_notebook(path))
    destination.write_text(rendered, encoding="utf-8")
    return destination
