from __future__ import annotations

from pathlib import Path

import fitz
from docx import Document

from app.utils import normalize_text


def parse_file(path: Path) -> list[tuple[int, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix in {".txt", ".md"}:
        return _parse_text(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def _parse_pdf(path: Path) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    document = fitz.open(path)
    try:
        for index, page in enumerate(document, start=1):
            text = normalize_text(page.get_text("text"))
            if text:
                pages.append((index, text))
    finally:
        document.close()
    return pages


def _parse_docx(path: Path) -> list[tuple[int, str]]:
    document = Document(path)
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return [(1, normalize_text("\n\n".join(parts)))] if parts else []


def _parse_text(path: Path) -> list[tuple[int, str]]:
    encodings = ["utf-8", "latin-1"]
    last_error: UnicodeDecodeError | None = None
    for encoding in encodings:
        try:
            return [(1, normalize_text(path.read_text(encoding=encoding)))]
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []
