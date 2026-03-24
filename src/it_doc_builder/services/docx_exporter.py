from __future__ import annotations

from io import BytesIO
from pathlib import Path

from html2docx import html2docx


def export_html_to_docx(html: str, output_path: Path, title: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = html2docx(html, title=title)
    if isinstance(document, BytesIO):
        output_path.write_bytes(document.getvalue())
    else:
        output_path.write_bytes(document)

    return output_path
