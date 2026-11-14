"""Generate an offline review page and aggregate labels with reviewer provenance."""
import argparse
import csv
import html
import json
from pathlib import Path
from .prepare import ROOT, write_json


def latest():
    return ROOT / json.loads((ROOT / 'results/latest.json').read_text(encoding='utf-8'))['path']


def samples(out):
    rows = []
    for kind, filename, maximum in [('coherence', 'coherence.csv', 2),
                                    ('grounding', 'grounding.csv', 2),
                                    ('metadata', 'metadata_audit.csv', 1)]:
        with (out / filename).open(encoding='utf-8-sig', newline='') as stream:
            for index, row in enumerate(csv.DictReader(stream)):
                rows.append({'id': f'{kind}-{index}', 'kind': kind, 'max': maximum, **row})
    return rows


def build(out):
    rows = samples(out)
    label_path = out / 'labels.json'
    initial = json.loads(label_path.read_text(encoding='utf-8')) if label_path.exists() else {}
    notice = ''
    if initial.get('review_type') == 'ai_assisted':
        notice = '<p><strong>Đánh giá do Codex (AI) hỗ trợ, chưa được học viên xác nhận.</strong> Điểm và lý do đã được nạp sẵn; bạn có thể đọc, đối chiếu và sửa. Xem review_notes.md để biết phương pháp.</p>'
    pages = {p['page']: p for p in [json.loads(line) for line in
             (ROOT / 'starter/data/pages.jsonl').read_text(encoding='utf-8').splitlines()]}
    cards = []
    for row in rows:
        context = ''
        if row['kind'] == 'coherence':
            context = pages[int(row['page'])]['text']
        elif row['kind'] == 'metadata':
            meta = json.loads(row['metadata_json'])
            context = json.dumps(pages[meta['page']], ensure_ascii=False, indent=2)
        elif row['kind'] == 'grounding':
            context = '\n\n'.join(f"#{i}: {h['text']}\n{h['metadata']}" for i, h in enumerate(json.loads(row['hits_json']), 1))
        details = '\n'.join(f'{k}: {v}' for k, v in row.items()
                            if k not in ('hits_json', 'reason', 'reviewer', 'max'))
        options = '<option value="">Chưa chấm</option>' + ''.join(
            f'<option value="{i}">{i}</option>' for i in range(row['max'] + 1))
        cards.append(f'<article data-id="{row["id"]}" data-kind="{row["kind"]}"><h2>{row["id"]} · {row["strategy"]}</h2>'
            f'<pre>{html.escape(details)}</pre><details><summary>Nguồn / top-3 để đối chiếu</summary>'
            f'<pre>{html.escape(context)}</pre></details><label>Điểm <select>{options}</select></label>'
            '<label>Lý do <textarea placeholder="Nêu ý được giữ, điều kiện bị thiếu, hoặc metadata sai/đúng"></textarea></label></article>')
    template = '''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Đánh giá Day 06</title>
<style>body{font:16px system-ui;max-width:1000px;margin:30px auto;padding:20px;background:#f5f7fb;color:#18263d}article{background:white;padding:24px;margin:20px 0;border:1px solid #d7deeb;border-radius:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}header{position:sticky;top:0;background:#e5edff;padding:18px}button,select,input,textarea{font:inherit;padding:8px}label{display:block;margin:15px 0}textarea{width:95%;min-height:70px}button{cursor:pointer}details{margin:18px 0}</style>
<h1>Chấm bằng chứng truy xuất</h1><p>Coherence: 0 bị cắt/không hiểu; 1 thiếu ngữ cảnh; 2 trọn ý. Grounding: 0 không có bằng chứng; 1 thiếu điều kiện; 2 đủ trả lời và truy nguồn. Metadata: 1 đủ và đúng sau đối chiếu nguồn; 0 sai/thiếu.</p>
REVIEW_NOTICE
<header><label>Người chấm <input id="reviewer" placeholder="Họ tên"></label><button id="download">Tải labels.json</button> <span id="progress"></span>
<label>Hiện nhóm <select id="kind"><option value="all">Tất cả</option><option>coherence</option><option>grounding</option><option>metadata</option></select></label></header>
CARDS
<script>
const initial=INITIAL_REVIEW;const key=STORAGE_KEY;const cards=[...document.querySelectorAll('article')];
let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
if(!Array.isArray(saved.labels)||!saved.labels.some(x=>Number.isInteger(x.score)&&typeof x.reason==='string'&&x.reason.trim()))saved=initial;
document.querySelector('#reviewer').value=saved.reviewer||'';
for(const c of cards){const v=(saved.labels||[]).find(x=>x.id===c.dataset.id);if(v){c.querySelector('select').value=v.score??'';c.querySelector('textarea').value=v.reason||''}}
function collect(){return {...initial,run:RUN_ID,reviewer:document.querySelector('#reviewer').value.trim(),labels:cards.map(c=>({id:c.dataset.id,score:c.querySelector('select').value===''?null:Number(c.querySelector('select').value),reason:c.querySelector('textarea').value.trim()}))}}
function save(){const v=collect();try{localStorage.setItem(key,JSON.stringify(v))}catch(e){}document.querySelector('#progress').textContent=v.labels.filter(x=>x.score!==null&&x.reason).length+'/'+cards.length+' có điểm và lý do'}
document.addEventListener('input',save);document.addEventListener('change',save);save();
document.querySelector('#kind').onchange=e=>cards.forEach(c=>c.hidden=e.target.value!=='all'&&c.dataset.kind!==e.target.value);
document.querySelector('#download').onclick=()=>{const v=collect();if(!v.reviewer){alert('Điền tên người chấm');return}const url=URL.createObjectURL(new Blob([JSON.stringify(v,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='labels.json';a.click();URL.revokeObjectURL(url)};
</script></html>'''
    template = template.replace('CARDS', '\n'.join(cards)).replace('STORAGE_KEY', json.dumps('day06-' + out.name)).replace('RUN_ID', json.dumps(out.name))
    template = template.replace('REVIEW_NOTICE', notice).replace('INITIAL_REVIEW', json.dumps(initial, ensure_ascii=False).replace('<', '\\u003c'))
    (out / 'review.html').write_text(template, encoding='utf-8')
    print(out / 'review.html')


def aggregate(out, path):
    payload = json.loads(path.read_text(encoding='utf-8'))
    expected = samples(out)
    if payload.get('run') != out.name or not payload.get('reviewer', '').strip():
        raise ValueError('Run ID / reviewer missing or mismatched')
    labels = payload['labels']
    if len({v['id'] for v in labels}) != len(labels):
        raise ValueError('Duplicate label ID')
    mapping = {v['id']: v for v in labels}
    if set(mapping) != {r['id'] for r in expected}:
        raise ValueError('Label sample IDs differ from this run')
    results = {}
    for row in expected:
        label = mapping[row['id']]
        score = label.get('score')
        if type(score) is not int or not 0 <= score <= row['max'] or not label.get('reason', '').strip():
            raise ValueError(f"Missing/invalid score or reason: {row['id']}")
        group = results.setdefault(f"{row['strategy']}/{row['kind']}", {'n': 0, 'sum': 0, 'histogram': {str(i): 0 for i in range(row['max'] + 1)}})
        group['n'] += 1
        group['sum'] += score
        group['histogram'][str(score)] += 1
    for group in results.values():
        group['mean'] = group['sum'] / group['n']
    # Keep the tabular audit artifacts consistent with the imported, attributed labels.
    for kind, filename, score_field in [('coherence', 'coherence.csv', 'score_0_2'),
                                       ('grounding', 'grounding.csv', 'score_0_2'),
                                       ('metadata', 'metadata_audit.csv', 'correct_0_1')]:
        with (out / filename).open(encoding='utf-8-sig', newline='') as stream:
            csv_rows = list(csv.DictReader(stream))
        for index, row in enumerate(csv_rows):
            label = mapping[f'{kind}-{index}']
            row.update({score_field: label['score'], 'reason': label['reason'], 'reviewer': payload['reviewer']})
        with (out / filename).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]))
            writer.writeheader()
            writer.writerows(csv_rows)
    write_json(out / 'labels.json', payload)
    write_json(out / 'audit_summary.json', {'reviewer': payload['reviewer'],
        'review_type': payload.get('review_type', 'unspecified'),
        'human_verified': payload.get('human_verified', False),
        'method': payload.get('method', ''), 'groups': results})
    print(json.dumps(results, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--labels', type=Path)
    args = parser.parse_args()
    out = args.run_dir or latest()
    aggregate(out, args.labels) if args.labels else build(out)


if __name__ == '__main__':
    main()
