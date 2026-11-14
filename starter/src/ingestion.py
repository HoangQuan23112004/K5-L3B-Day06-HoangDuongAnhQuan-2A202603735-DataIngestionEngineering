"""Normalize Unicode and preserve paragraph structure and physical PDF pages."""
import json
import re
import unicodedata
from pathlib import Path
from .models import DocumentPage


def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFC', text).replace('\r\n', '\n').replace('\r', '\n')
    return '\n\n'.join(re.sub(r'\s+', ' ', p).strip() for p in re.split(r'\n\s*\n', text) if p.strip())


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    from pypdf import PdfReader
    pages = []
    for number, page in enumerate(PdfReader(path).pages, 1):
        text = normalize_text(page.extract_text() or '')
        if not text:
            raise ValueError(f'{path}: page {number} has no text; OCR or explicitly exclude it')
        pages.append(DocumentPage(document_id, source, number, text))
    return pages


def load_pages(path: Path) -> list[DocumentPage]:
    return [DocumentPage(**json.loads(line)) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
