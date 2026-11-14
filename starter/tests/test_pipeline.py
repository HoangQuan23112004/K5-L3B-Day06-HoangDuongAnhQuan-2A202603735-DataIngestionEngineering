"""Invariant tests use tiny synthetic vectors; benchmark always uses real ONNX."""
import tempfile
import unittest
from pathlib import Path
from src.chunking import by_paragraph, fixed_size
from src.evaluation import evaluate_query
from src.ingestion import normalize_text
from src.models import DocumentPage
from src.run import validate
from src.store import QdrantStore


class PipelineTests(unittest.TestCase):
    def test_corpus_and_evidence(self):
        pages, questions = validate()
        self.assertGreaterEqual(len(pages), 30)
        self.assertEqual(20, len(questions))

    def test_normalization_and_chunk_offsets(self):
        text = normalize_text('Tie\u0302\u0301ng   Vie\u0323\u0302t\r\nline\r\n\r\nSecond paragraph. ' * 30)
        self.assertIn('\n\n', text)
        page = DocumentPage('test', 'source', 1, text, {'chapter': 2})
        for chunks in [fixed_size(page, 80, 10), by_paragraph(page, 80)]:
            covered = set()
            for chunk in chunks:
                start, end = chunk.metadata['start'], chunk.metadata['end']
                self.assertEqual(chunk.text, text[start:end])
                self.assertLessEqual(len(chunk.text), 80)
                covered.update(range(start, end))
            self.assertTrue(all(i in covered for i, c in enumerate(text) if not c.isspace()))
        with self.assertRaises(ValueError):
            fixed_size(page, 80, 80)

    def test_metric_requires_full_evidence_and_source(self):
        q = {'gold_source_id': 'doc', 'gold_page': 2, 'evidence_quote': 'subject condition result'}
        def hit(text, page=2):
            return {'text': text, 'metadata': {'document_id': 'doc', 'page': page}}
        self.assertFalse(evaluate_query(q, [hit('subject condition'), hit('condition result')])['hit3'])
        self.assertFalse(evaluate_query(q, [hit('subject condition result', 1)])['hit3'])
        self.assertTrue(evaluate_query(q, [hit('wrong'), hit('subject condition result')])['hit3'])
        self.assertFalse(evaluate_query(q, [hit('wrong'), hit('subject condition result')])['hit1'])

    def test_store_filter_replacement_and_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            pages = [DocumentPage('test', 'url', i, f'paragraph {i}', {'chapter': i}) for i in [1, 2]]
            chunks = [fixed_size(p, 80, 0)[0] for p in pages]
            store = QdrantStore(Path(folder) / 'db', 2)
            try:
                store.upsert('A', chunks, [[1., 0.], [0., 1.]])
                store.upsert('A', chunks, [[1., 0.], [0., 1.]])
                self.assertEqual(2, store.count('A'))
                hits = store.search('A', [1., 0.], filters={'chapter': 2})
                self.assertEqual(2, hits[0]['metadata']['chapter'])
                # Shrinking a source removes the obsolete page instead of leaving stale hits.
                store.upsert('A', chunks[:1], [[1., 0.]])
                self.assertEqual(1, store.count('A'))
                self.assertEqual([], store.search('A', [1., 0.], filters={'chapter': 2}))
            finally:
                store.close()
            reopened = QdrantStore(Path(folder) / 'db', 2)
            try:
                self.assertEqual(1, reopened.count('A'))
                self.assertEqual('paragraph 1', reopened.search('A', [1., 0.])[0]['text'])
            finally:
                reopened.close()


if __name__ == '__main__':
    unittest.main()
