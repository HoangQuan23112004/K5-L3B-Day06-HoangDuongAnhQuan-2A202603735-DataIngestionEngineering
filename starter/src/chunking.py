"""Chunk within pages; offsets are exact in normalized page text."""
import hashlib
import re
from .models import Chunk, DocumentPage


def make_chunk(page: DocumentPage, start: int, end: int) -> Chunk:
    text = page.text[start:end]
    identity = f'{page.document_id}:{page.page}:{start}:{end}:{text}'
    return Chunk(hashlib.sha256(identity.encode()).hexdigest(), page.document_id,
                 page.source, page.page, text,
                 {**page.metadata, 'start': start, 'end': end})


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError('Require size > 0 and 0 <= overlap < size')
    chunks = []
    for start in range(0, len(page.text), size - overlap):
        chunks.append(make_chunk(page, start, min(start + size, len(page.text))))
        if start + size >= len(page.text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError('max_size must be positive')
    spans = []
    for match in re.finditer(r'[^\n]+(?:\n(?!\n)[^\n]+)*', page.text):
        start, end = match.span()
        while end - start > max_size:
            window = page.text[start:start + max_size]
            boundaries = list(re.finditer(r'[.!?][”\"\u2019]?\s+', window))
            cut = boundaries[-1].end() if boundaries else window.rfind(' ')
            cut = cut if cut > 0 else max_size
            spans.append((start, start + cut))
            start += cut
        if end > start:
            spans.append((start, end))
    groups = []
    for start, end in spans:
        if groups and end - groups[-1][0] <= max_size:
            groups[-1] = (groups[-1][0], end)
        else:
            groups.append((start, end))
    return [make_chunk(page, start, end) for start, end in groups]
