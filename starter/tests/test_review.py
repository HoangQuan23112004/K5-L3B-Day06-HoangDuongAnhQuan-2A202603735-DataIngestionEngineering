"""Imported audit decisions retain provenance and never accept empty labels."""
import contextlib
import csv
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from src.prepare import ROOT
from src.review import aggregate, build


class ReviewTests(unittest.TestCase):
    def make_run(self, folder):
        source = ROOT / 'results/20261113_150013'
        target = Path(folder) / source.name
        target.mkdir()
        for name in ['coherence.csv', 'grounding.csv', 'metadata_audit.csv', 'labels.json']:
            shutil.copy2(source / name, target / name)
        return target

    def test_import_retains_ai_provenance_and_populates_page(self):
        with tempfile.TemporaryDirectory() as folder:
            out = self.make_run(folder)
            with contextlib.redirect_stdout(io.StringIO()):
                aggregate(out, out / 'labels.json')
                build(out)
            summary = json.loads((out / 'audit_summary.json').read_text(encoding='utf-8'))
            self.assertEqual('ai_assisted', summary['review_type'])
            self.assertFalse(summary['human_verified'])
            self.assertEqual(90, sum(g['n'] for g in summary['groups'].values()))
            page = (out / 'review.html').read_text(encoding='utf-8')
            self.assertIn('chưa được học viên xác nhận', page)
            self.assertEqual(90, page.count('<article '))
            with (out / 'coherence.csv').open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertTrue(all(r['score_0_2'] and r['reason'] and 'Codex' in r['reviewer'] for r in rows))

    def test_incomplete_import_does_not_change_csv_or_publish_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            out = self.make_run(folder)
            before = (out / 'coherence.csv').read_bytes()
            payload = json.loads((out / 'labels.json').read_text(encoding='utf-8'))
            payload['labels'][0]['reason'] = ''
            bad = out / 'incomplete.json'
            bad.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'coherence-0'):
                aggregate(out, bad)
            self.assertEqual(before, (out / 'coherence.csv').read_bytes())
            self.assertFalse((out / 'audit_summary.json').exists())


if __name__ == '__main__':
    unittest.main()
