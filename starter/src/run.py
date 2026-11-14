"""CLI: validate, ingest, select on dev, freeze, evaluate test and export audits."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import canonical, evaluate_query, summarize
from .ingestion import load_pages
from .prepare import ROOT, DATA, write_json

MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
CONFIG = {'A': {'method': 'fixed', 'size': 800, 'overlap': 100, 'filter': False},
          'B': {'method': 'paragraph', 'size': 800, 'overlap': 0, 'filter': False},
          'C': {'method': 'paragraph', 'size': 800, 'overlap': 0, 'filter': True}}


def now():
    return datetime.now(timezone(timedelta(hours=7)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate():
    pages = load_pages(DATA / 'pages.jsonl')
    questions = json.loads((ROOT / 'benchmark/questions.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT / 'data/manifest.json').read_text(encoding='utf-8'))
    if len(pages) < 30 or any(len(p.text) < 1500 for p in pages):
        raise ValueError('Need >=30 valid logical units of >=1500 chars')
    if sha(DATA / 'alice.txt') != manifest['raw_sha256'] or manifest['count'] != len(pages):
        raise ValueError('Raw corpus or manifest mismatch; prepare again')
    mapping = {(p.document_id, p.page): p for p in pages}
    if len(mapping) != len(pages) or len({q['id'] for q in questions}) != len(questions):
        raise ValueError('Duplicate source units or question IDs')
    for split, minimum in [('dev', 15), ('test', 5)]:
        if sum(q['split'] == split for q in questions) < minimum:
            raise ValueError(f'Insufficient {split} questions')
    if sum(bool(q.get('filter')) for q in questions) < 3 or not any(
            q.get('filter') and q['split'] == 'test' for q in questions):
        raise ValueError('Need >=3 filters, including test')
    for q in questions:
        page = mapping[(q['gold_source_id'], q['gold_page'])]
        if not q['evidence_quote'].strip() or canonical(q['evidence_quote']) not in canonical(page.text):
            raise ValueError(f"Missing evidence: {q['id']}")
        if any(page.metadata.get(k) != v for k, v in q.get('filter', {}).items()):
            raise ValueError(f"Gold outside filter: {q['id']}")
    return pages, questions


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export_audits(out, pages, chunks_by_strategy, traces):
    coherence = []
    for page in pages[:10]:
        for strategy, chunks in chunks_by_strategy.items():
            chunk = next(c for c in chunks if c.page == page.page and c.metadata['start'] <= 100 < c.metadata['end'])
            coherence.append({'strategy': strategy, 'page': page.page, 'anchor': 100,
                'chunk_id': chunk.chunk_id, 'text': chunk.text, 'score_0_2': '', 'reason': '', 'reviewer': ''})
    grounding, metadata = [], []
    for trace in traces:
        if trace['split'] != 'test':
            continue
        grounding.append({'strategy': trace['strategy'], 'question_id': trace['id'],
            'question': trace['question'], 'expected_answer': trace['expected_answer'],
            'evidence_quote': trace['evidence_quote'],
            'hits_json': json.dumps(trace['hits'], ensure_ascii=False),
            'score_0_2': '', 'reason': '', 'reviewer': ''})
        for rank, hit in enumerate(trace['hits'], 1):
            metadata.append({'strategy': trace['strategy'], 'question_id': trace['id'], 'rank': rank,
                'chunk_id': hit['chunk_id'], 'metadata_json': json.dumps(hit['metadata'], ensure_ascii=False),
                'text': hit['text'], 'correct_0_1': '', 'reason': '', 'reviewer': ''})
    write_csv(out / 'coherence.csv', coherence)
    write_csv(out / 'grounding.csv', grounding)
    write_csv(out / 'metadata_audit.csv', metadata)


def run(out, verify_reingest):
    from .store import QdrantStore
    pages, questions = validate()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'protocol_lock.json', {
        'created_at': now().isoformat(), 'model': MODEL, 'config': CONFIG,
        'selection_rule': 'dev hit3 desc, hit1 desc, chunks asc, strategy asc',
        'sha256': {str(p.relative_to(ROOT)): sha(p) for p in [DATA / 'alice.txt', DATA / 'pages.jsonl',
            ROOT / 'benchmark/questions.json', ROOT / 'benchmark/PROTOCOL.md']}})
    chunks_by_strategy = {
        'A': [c for p in pages for c in fixed_size(p, 800, 100)],
        'B': [c for p in pages for c in by_paragraph(p, 800)]}
    chunks_by_strategy['C'] = chunks_by_strategy['B']
    print('Loading real embedding model (first run downloads weights)...', flush=True)
    started = time.perf_counter()
    embedder = MyEmbedder(MODEL)
    model_load = time.perf_counter() - started
    store = QdrantStore(ROOT / 'starter/.qdrant', embedder.dimensions)
    traces, stats, vectors_by_strategy = [], {}, {}
    try:
        for strategy, chunks in chunks_by_strategy.items():
            started = time.perf_counter()
            vectors = vectors_by_strategy['B'] if strategy == 'C' else embedder.embed_documents([c.text for c in chunks])
            embedding_seconds = time.perf_counter() - started
            vectors_by_strategy[strategy] = vectors
            started = time.perf_counter()
            store.upsert(strategy, chunks, vectors)
            count_first = store.count(strategy)
            store_seconds = time.perf_counter() - started
            if verify_reingest:
                store.upsert(strategy, chunks, vectors)
                if store.count(strategy) != count_first:
                    raise RuntimeError('Reingest produced duplicates')
            lengths = [len(c.text) for c in chunks]
            stats[strategy] = {'chunks': len(chunks), 'chars': sum(lengths), 'min_chars': min(lengths),
                'max_chars': max(lengths), 'mean_chars': sum(lengths) / len(lengths),
                'embedding_seconds': embedding_seconds, 'store_seconds': store_seconds,
                'reuses_vectors_from': 'B' if strategy == 'C' else None,
                'count_before_reingest': count_first,
                'count_after_reingest': store.count(strategy) if verify_reingest else None,
                'paid_api_cost_usd': 0}
            (out / f'chunks_{strategy}.jsonl').write_text(''.join(
                json.dumps(asdict(c), ensure_ascii=False) + '\n' for c in chunks), encoding='utf-8')
            print(f'{strategy}: {len(chunks)} chunks indexed', flush=True)
        for split in ['dev', 'test']:
            for q in questions:
                if q['split'] != split:
                    continue
                # Only the user question is embedded. Gold never enters this path.
                started = time.perf_counter()
                query_vector = embedder.embed_query(q['question'])
                query_embedding_seconds = time.perf_counter() - started
                for strategy in CONFIG:
                    started = time.perf_counter()
                    filters = q.get('filter') if CONFIG[strategy]['filter'] else None
                    hits = store.search(strategy, query_vector, top_k=3, filters=filters)
                    elapsed = time.perf_counter() - started
                    trace = evaluate_query(q, hits)
                    trace.update(strategy=strategy, applied_filter=filters or {},
                        search_seconds=elapsed, query_embedding_seconds=query_embedding_seconds)
                    traces.append(trace)
            if split == 'dev':
                dev = summarize(traces)
                chosen = min(CONFIG, key=lambda s: (-dev[f'{s}/dev']['hit3'],
                    -dev[f'{s}/dev']['hit1'], stats[s]['chunks'], s))
                # Write selection before the first test query; no tuning after test.
                write_json(out / 'selection.json', {'selected': chosen, 'selected_at': now().isoformat(),
                    'dev_metrics': dev, 'protocol_lock_sha256': sha(out / 'protocol_lock.json')})
                print(f'Dev selection frozen: {chosen}', flush=True)
        summary = summarize(traces)
        write_json(out / 'metrics.json', summary)
        (out / 'traces.jsonl').write_text(''.join(json.dumps(t, ensure_ascii=False) + '\n' for t in traces), encoding='utf-8')
        write_csv(out / 'metrics.csv', [{'strategy_split': k, **v} for k, v in summary.items()])
        export_audits(out, pages, chunks_by_strategy, traces)
        versions = {p: importlib.metadata.version(p) for p in ['fastembed', 'qdrant-client', 'onnxruntime', 'numpy', 'tokenizers']}
        write_json(out / 'run.json', {'finished_at': now().isoformat(), 'model': MODEL,
            'dimensions': embedder.dimensions, 'model_load_seconds': model_load, 'config': CONFIG,
            'python': platform.python_version(), 'versions': versions,
            'store': 'Qdrant local persistent; exact cosine', 'strategies': stats,
            'manual_audits': 'PENDING: learner must read samples, score and give reasons',
            'model_files_sha256': {str(p.relative_to(ROOT / 'starter/.model_cache')): sha(p)
                for p in (ROOT / 'starter/.model_cache').rglob('*') if p.is_file() and p.suffix in ('.onnx', '.json')}})
        with (out / 'requirements-lock.txt').open('w', encoding='utf-8') as stream:
            subprocess.run([sys.executable, '-m', 'pip', 'freeze'], stdout=stream, check=True)
        write_json(ROOT / 'results/latest.json', {'path': str(out.relative_to(ROOT))})
        print(json.dumps(summary, indent=2))
        print(f'Artifacts: {out}')
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--verify-reingest', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.validate_only:
        pages, questions = validate()
        print(f'Validation OK: {len(pages)} units, {len(questions)} questions; all evidence verified')
        return
    out = args.output or ROOT / 'results' / now().strftime('%Y%m%d_%H%M%S')
    try:
        run(out, args.verify_reingest)
    except Exception:
        if out.is_dir():
            (out / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
