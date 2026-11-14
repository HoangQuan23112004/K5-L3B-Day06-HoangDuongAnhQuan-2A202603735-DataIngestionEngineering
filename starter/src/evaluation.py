"""Strict single-chunk evidence metrics; no inferred human labels."""
import re
import unicodedata
from collections import defaultdict
from typing import Any


def canonical(text: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip()


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    golds = [{k: question[k] for k in ('gold_source_id', 'gold_page', 'evidence_quote')}]
    golds += question.get('gold_alternatives', [])
    for hit in hits:
        hit['evidence_hit'] = any(
            hit['metadata']['document_id'] == g['gold_source_id'] and
            hit['metadata']['page'] == g['gold_page'] and
            canonical(g['evidence_quote']) in canonical(hit['text']) for g in golds)
    wanted = question.get('filter', {})
    return {**question, 'hits': hits, 'hit1': bool(hits and hits[0]['evidence_hit']),
            'hit3': any(h['evidence_hit'] for h in hits),
            'filter_compliant': (len(hits) == 3 and all(
                all(h['metadata'].get(k) == v for k, v in wanted.items()) for h in hits)) if wanted else None}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    groups = defaultdict(list)
    for row in traces:
        groups[f"{row['strategy']}/{row['split']}"].append(row)
    summary = {}
    for key, rows in groups.items():
        filtered = [r for r in rows if r.get('filter')]
        summary[key] = {'n': len(rows), 'hit1_n': sum(r['hit1'] for r in rows),
            'hit3_n': sum(r['hit3'] for r in rows),
            'hit1': sum(r['hit1'] for r in rows) / len(rows),
            'hit3': sum(r['hit3'] for r in rows) / len(rows),
            'filter_n': len(filtered),
            'filter_compliant_n': sum(r['filter_compliant'] for r in filtered) if filtered else None}
    return summary
