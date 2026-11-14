"""Build reproducible content units and a predeclared benchmark from PG #11."""
import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .ingestion import normalize_text
from .models import DocumentPage

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'starter' / 'data'
SOURCE = 'https://www.gutenberg.org/ebooks/11'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


# Fixed before first retrieval run. Questions are English to match the corpus/model.
# Each anchor selects an entire source paragraph, without constructing evidence.
SPECS = [
    (1, 'What was in the jar labelled ORANGE MARMALADE, and why did Alice avoid dropping it?',
     'It was empty; she feared killing someone underneath.', 'it was labelled “ORANGE MARMALADE”', False),
    (1, 'What unusual object did the White Rabbit take from its waistcoat pocket?',
     'A watch.', 'watch out of its waistcoat-pocket', False),
    (1, 'Why did Alice initially find her sister’s book uninteresting?',
     'It had no pictures or conversations.', 'Alice was beginning to get very tired', False),
    (1, 'In chapter I, what did Alice check before tasting the bottle?',
     'Whether it was marked poison.', 'see whether it’s marked', True),
    (2, 'How deep was the pool created by Alice’s tears, and how far did it extend?',
     'About four inches deep, reaching halfway down the hall.', 'four inches deep', False),
    (3, 'What did the Dodo ceremonially present to Alice as her prize?',
     'A thimble.', 'presented the thimble', False),
    (3, 'In chapter III, why did the other animals dislike hearing about Dinah?',
     'She was a cat who caught mice and ate birds.', 'Dinah’s our cat', True),
    (4, 'Who did the Rabbit mistake Alice for when ordering her to fetch things?',
     'Mary Ann.', 'Mary Ann, what _are_ you', False),
    (4, 'What did Alice threaten to do if the Rabbit burned the house down?',
     'Set Dinah at them.', 'If you do, I’ll set Dinah at you', False),
    (4, 'What was the Caterpillar doing when Alice first saw it on the mushroom?',
     'Smoking a long hookah.', 'smoking a long hookah', False),
    (5, 'What did Alice admit about eating eggs when arguing with the Pigeon?',
     'She had tasted eggs and said little girls eat them as much as serpents.', 'I _have_ tasted eggs', False),
    (6, 'What made Alice sneeze in the Duchess’s kitchen?',
     'Too much pepper in the soup.', 'too much pepper', False),
    (7, 'In chapter VII, what substance did the March Hare put in the watch?',
     'Butter, which the Hatter said did not suit the works.', 'I told you butter wouldn’t suit', True),
    (7, 'What kind of well did the Dormouse say the three sisters lived in?',
     'A treacle-well.', 'It was a treacle-well', False),
    (8, 'What served as the balls, mallets, and arches in the Queen’s croquet game?',
     'Live hedgehogs, live flamingoes, and soldiers bent over.', 'the balls were live', False),
    (9, 'Why was the Mock Turtle’s teacher called Tortoise even though he was a turtle?',
     'Because he taught us, a pun on tortoise.', 'because he taught us', False),
    (9, 'How did the number of school hours change from the first day to the second?',
     'Ten hours the first day, nine the next.', 'Ten hours the first day', False),
    (10, 'In chapter X, what does the Mock Turtle say no wise fish would travel without?',
     'A porpoise, in a pun on purpose.', 'no wise fish would go anywhere', True),
    (11, 'What did the Hatter bring when he appeared as the first witness, and why?',
     'A teacup and bread-and-butter, because he had not finished tea.', 'The first witness was the Hatter', False),
    (12, 'What rule did the King cite to make tall people leave the court?',
     'Rule Forty-two: all persons more than a mile high must leave the court.', 'All persons more than a mile high', False),
]


def main():
    raw = (DATA / 'alice.txt').read_text(encoding='utf-8-sig')
    body = raw.split('*** START OF THE PROJECT GUTENBERG EBOOK', 1)[1]
    body = body.split('*** END OF THE PROJECT GUTENBERG EBOOK', 1)[0]
    matches = list(re.finditer(r'^CHAPTER ([IVX]+)\.\s*\n([^\n]+)\n', body, re.M))
    if len(matches) != 12:
        raise ValueError(f'Expected 12 body chapters, got {len(matches)}')
    pages, chapters = [], {}
    for number, match in enumerate(matches, 1):
        end = matches[number].start() if number < len(matches) else len(body)
        text = normalize_text(body[match.end():end])
        text = re.sub(r'(?m)^\[Illustration\]\s*\n?', '', text)
        text = re.sub(r'(?m)^\*(?:\s+\*)+\s*$', '', text)
        text = normalize_text(text)
        chapters[number] = text
        # Ordered, nonoverlapping units >=1500 characters; never split a paragraph.
        units, current = [], ''
        for paragraph in text.split('\n\n'):
            current += ('\n\n' if current else '') + paragraph
            if len(current) >= 1800:
                units.append(current)
                current = ''
        if current:
            if len(current) < 1500 and units:
                units[-1] += '\n\n' + current
            else:
                units.append(current)
        cursor = 0
        for unit in units:
            start = text.index(unit, cursor)
            cursor = start + len(unit)
            pages.append(DocumentPage('pg11', SOURCE, len(pages) + 1, unit, {
                'chapter': number, 'chapter_title': match.group(2).strip(), 'language': 'en',
                'chapter_start': start, 'chapter_end': cursor}))
    if len(pages) < 30 or any(len(p.text) < 1500 for p in pages):
        raise ValueError('Corpus must contain >=30 nonoverlapping units of >=1500 chars')
    benchmark = []
    for index, (chapter, question, answer, anchor, filtered) in enumerate(SPECS, 1):
        candidates = [p for p in chapters[chapter].split('\n\n') if anchor.casefold() in p.casefold()]
        if len(candidates) != 1:
            raise ValueError(f'Q{index:02}: ambiguous/missing anchor {anchor!r}: {len(candidates)}')
        evidence = candidates[0]
        locations = [p for p in pages if p.metadata['chapter'] == chapter and evidence in p.text]
        if len(locations) != 1:
            raise ValueError(f'Q{index}: evidence must be contained in one unit')
        benchmark.append({'id': f'Q{index:02}', 'split': 'dev' if index <= 15 else 'test',
            'question': question, 'expected_answer': answer, 'gold_source_id': 'pg11',
            'gold_page': locations[0].page, 'evidence_quote': evidence,
            'filter': {'chapter': chapter} if filtered else {}})
    DATA.mkdir(exist_ok=True)
    (DATA / 'pages.jsonl').write_text(''.join(json.dumps(asdict(p), ensure_ascii=False) + '\n' for p in pages), encoding='utf-8')
    write_json(ROOT / 'benchmark/questions.json', benchmark)
    manifest_path = ROOT / 'data/manifest.json'
    raw_hash = hashlib.sha256((DATA / 'alice.txt').read_bytes()).hexdigest()
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    accessed_at = previous.get('accessed_at') if previous.get('raw_sha256') == raw_hash else None
    write_json(manifest_path, {
        'source_id': 'pg11', 'title': "Alice's Adventures in Wonderland", 'author': 'Lewis Carroll (died 1898)',
        'source_path_or_url': SOURCE, 'download_url': 'https://www.gutenberg.org/ebooks/11.txt.utf-8',
        'local_path': 'starter/data/alice.txt',
        'license_or_permission': 'Original work public domain (1865; author died 1898); PG edition declares public domain in USA. Full PG license retained in raw file. No translation or illustrations redistributed.',
        'accessed_at': accessed_at or datetime.now(timezone(timedelta(hours=7))).isoformat(),
        'raw_sha256': raw_hash,
        'snapshot': 'PG #11, Millennium Fulcrum Edition 3.0; header updated 2025-06-26',
        'page_rule': 'Logical units, not physical pages: chapter order, whole normalized paragraphs until >=1800 chars; tail <1500 merged into previous unit. No overlap. Front matter/TOC/license/illustration markers/scene ornaments excluded.',
        'count': len(pages), 'physical_pdf_pages': None,
        'pages': [{'page': p.page, 'chapter': p.metadata['chapter'], 'chars': len(p.text),
                   'chapter_start': p.metadata['chapter_start'], 'chapter_end': p.metadata['chapter_end']} for p in pages]})
    print(f'Prepared {len(pages)} units, {sum(len(p.text) for p in pages)} chars; 15 dev / 5 test.')


if __name__ == '__main__':
    main()
