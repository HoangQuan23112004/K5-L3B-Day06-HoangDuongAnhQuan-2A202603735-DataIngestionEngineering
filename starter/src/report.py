"""Write a report from measured artifacts, marking unaudited fields explicitly."""
import argparse
import json
from pathlib import Path
from .prepare import ROOT
from .review import latest
from .run import write_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path)
    args = parser.parse_args()
    out = args.run_dir or latest()
    read = lambda name: json.loads((out / name).read_text(encoding='utf-8'))
    metrics, run, selection = read('metrics.json'), read('run.json'), read('selection.json')
    traces = [json.loads(line) for line in (out / 'traces.jsonl').read_text(encoding='utf-8').splitlines()]
    rel = out.relative_to(ROOT).as_posix()
    lines = ['# Báo cáo cá nhân — Data Ingestion Engineering', '',
        'Họ tên / MSSV / lớp: **học viên bổ sung trong STUDENT.md**.', '',
        '## Dữ liệu và pipeline', '',
        '- Chủ đề: truy xuất bằng chứng trong nguyên tác tiếng Anh *Alice’s Adventures in Wonderland* (Lewis Carroll, 1865; tác giả mất 1898).',
        '- Nguồn: https://www.gutenberg.org/ebooks/11 . Bản gốc thuộc public domain; giữ nguyên thông báo/giấy phép Project Gutenberg trong file raw, không đưa minh họa hoặc bản dịch vào corpus.',
        '- Corpus: 69 đơn vị có ý nghĩa theo thứ tự chương, mỗi đơn vị ≥1.500 ký tự. Đây là đơn vị text tương đương theo GUIDE, không phải 69 trang PDF. Loại mục lục, thông báo giấy phép, marker minh họa và dấu trang trí. Manifest lưu số ký tự, ranh giới trong từng chương và SHA-256 raw.',
        '- Chuẩn hóa NFC, gộp khoảng trắng trong đoạn, giữ dòng trống giữa đoạn. ID document = pg11; page = ID unit toàn corpus; chapter/title được trích trực tiếp từ heading, language = en từ header. Chunk lưu offset start/end chính xác trong unit.',
        f"- Model: `{run['model']}`, {run['dimensions']} chiều, CPU ONNX qua FastEmbed {run['versions']['fastembed']}. Query/document cùng model; không prefix riêng, cosine trong Qdrant chuẩn hóa vector. Qdrant client {run['versions']['qdrant-client']}, persistent local tại `starter/.qdrant`, exact search. Phiên bản Python {run['python']}; lock đầy đủ và SHA trọng số trong artifacts.",
        '- Chi phí API trả phí: 0 USD; không quy đổi điện, CPU, dung lượng hoặc thời gian tải model thành tiền. Không dùng LLM sinh đáp án.',
        '- Lưu snapshot bằng ID ổn định; nạp lại xóa các point cũ của collection A/B/C rồi nạp snapshot mới, xử lý cả tài liệu sửa/xóa. Không có giao dịch bao trọn snapshot: lỗi giữa chừng cần chạy lại; lỗi được ghi error.log.', '',
        '## Cấu hình và benchmark', '',
        '| Cấu hình | Chunk | Retrieval |', '|---|---|---|',
        '| A | 800 ký tự, overlap 100 | cosine top-3, không filter |',
        '| B | nhóm đoạn tối đa 800 ký tự; đoạn dài tách câu/từ | giống A, không filter |',
        '| C | dùng nguyên chunk và vector B | thêm filter chapter chỉ khi câu hỏi chỉ định |', '',
        '- A–B thay phương pháp chunking (gồm overlap); không thể tách riêng tác động của overlap khỏi ranh giới đoạn. B–C chỉ thay filter. C tái sử dụng embedding B nên thời gian embedding gần 0 không có nghĩa thuật toán embedding nhanh hơn.',
        '- 20 câu: 15 dev Q01–Q15 (I–VIII), 5 test Q16–Q20 (IX–XII). Filter: Q04/Q07/Q13/Q18; chương nằm trong câu hỏi, không lấy từ gold. Evidence là đoạn gốc đã kiểm chứng tồn tại; metric chấp nhận đúng nguồn + unit + đủ nguyên evidence trong một chunk.',
        f"- Tiêu chí chốt trước test: ưu tiên dev Evidence Hit@3, sau đó Hit@1, ít chunk và tên cấu hình. Đã chọn **{selection['selected']}**, lưu selection.json trước truy xuất test. Các cấu hình còn lại vẫn chạy test để so sánh; không chỉnh theo điểm test.",
        '- AI hỗ trợ soạn benchmark và đã thấy nội dung câu test trong lúc viết/kiểm tra gold; không tuyên bố test mù độc lập. Tách chương giảm lặp nội dung nhưng vẫn chung nhân vật/chủ đề.', '',
        '## Kết quả truy xuất đo thực tế', '',
        '| Strategy | Split | Hit@1 | Evidence Hit@3 | Số chunk | Embed (s) | Store (s) |',
        '|---|---|---|---|---|---|---|']
    for key, m in metrics.items():
        strategy, split = key.split('/')
        stat = run['strategies'][strategy]
        lines.append(f"| {strategy} | {split} | {m['hit1_n']}/{m['n']} ({m['hit1']:.1%}) | {m['hit3_n']}/{m['n']} ({m['hit3']:.1%}) | {stat['chunks']} | {stat['embedding_seconds']:.3f} | {stat['store_seconds']:.3f} |")
    lines += ['', 'Thời gian là một lượt đo trên máy hiện tại; embed/store ở bảng được lặp cho hai split để tiện đọc, không cộng hai lần. Tải model đo riêng; C dùng lại vector B.', '',
        '## Coherence, metadata và grounding', '',
        '- Coherence: cùng 10 unit đầu, anchor ký tự 100; mỗi cấu hình lấy chunk đầu chứa anchor. 30 mẫu, thang 0–2.',
        '- Metadata: 5 câu test × top-3 × 3 cấu hình = 45 bản ghi. Đối chiếu source, document_id, page, chapter và offset với pages.jsonl; thang 0/1.',
        '- Grounding: 5 câu test × 3 cấu hình = 15 mẫu; đọc cả top-3 để chấm 0/1/2. Không coi exact evidence hit là nhãn grounding hoặc coherence.', '',
        '| Strategy | Coherence /2 | Metadata đúng | Grounding /2 |', '|---|---|---|---|']
    audit_info = read('audit_summary.json') if (out / 'audit_summary.json').exists() else None
    audit = audit_info['groups'] if audit_info else None
    if audit_info:
        attribution = f"Người đánh giá: **{audit_info['reviewer']}**. "
        if audit_info.get('review_type') == 'ai_assisted':
            attribution += 'Đây là nhãn AI hỗ trợ sau khi đọc mẫu, không phải nhãn do học viên chấm độc lập; chưa được học viên xác nhận. Phương pháp và ví dụ: `review_notes.md` trong thư mục run.'
        lines[-2:-2] = [attribution, '']
    for s in 'ABC':
        if audit:
            co, me, gr = [audit[f'{s}/{kind}'] for kind in ['coherence', 'metadata', 'grounding']]
            lines.append(f"| {s} | {co['mean']:.2f} (n={co['n']}) | {me['sum']}/{me['n']} | {gr['mean']:.2f}, mức 0/1/2={gr['histogram']} |")
        else:
            lines.append(f'| {s} | CHƯA CHẤM | CHƯA CHẤM | CHƯA CHẤM |')
    lines += ['', 'Filter compliance tự động (đối chiếu input filter, không thay audit metadata):', '',
        '| Cấu hình/split | Top-3 tuân thủ / số câu yêu cầu filter |', '|---|---|']
    for key, m in metrics.items():
        lines.append(f"| {key} | {m['filter_compliant_n']}/{m['filter_n']} |")
    lines += ['', 'Trường chapter giúp thu hẹp bối cảnh giữa nhiều cảnh dùng cùng từ (trà, động vật, tarts). Page và offset giúp mở đúng đoạn gốc. Hạn chế: chapter là phạm vi rộng, không giúp phân biệt hai đoạn trong cùng chương; filter sai có thể loại hết bằng chứng.', '',
        '## Tác động và ví dụ lỗi', '']
    for left, right in [('A', 'B'), ('B', 'C')]:
        lm, rm = metrics[f'{left}/dev'], metrics[f'{right}/dev']
        lines.append(f"- {left}–{right}: dev Hit@3 {lm['hit3_n']}/15 → {rm['hit3_n']}/15; Hit@1 {lm['hit1_n']}/15 → {rm['hit1_n']}/15; số chunk {run['strategies'][left]['chunks']} → {run['strategies'][right]['chunks']}.")
    failures = [t for t in traces if not t['hit3']]
    for t in failures[:2]:
        top = t['hits'][0] if t['hits'] else None
        lines.append(f"- Lỗi {t['strategy']}/{t['id']} ({t['split']}): gold pg11/unit {t['gold_page']}; top-1 unit {top['metadata']['page'] if top else 'không có'}. Top-3 không chứa trọn đoạn gold tại đúng unit. Đọc trace để phân biệt sai chủ đề với evidence bị cắt; metric tự động không chứng minh hoàn toàn không trả lời được.")
    if len(failures) < 2:
        lines.append('- Chưa có đủ hai lỗi Hit@3; không tự tạo ví dụ. Có thể phân tích lỗi top-1 hoặc trường hợp thiếu ngữ cảnh trong audit.')
    if any(t['strategy'] == 'A' and t['id'] == 'Q01' for t in failures):
        lines.append('- Đọc thực tế A/Q01: top-1 unit 1 offset 2100–2383 vẫn có jar rỗng và lý do sợ làm chết người bên dưới; nhưng phần đầu đoạn gold bị tách sang chunk 1400–2200 nên strict Evidence Hit@3 = 0. Đây là ví dụ gold nguyên đoạn khắt khe hơn lượng thông tin tối thiểu để trả lời, không nên diễn giải thành không có đáp án.')
    if any(t['strategy'] == 'A' and t['id'] == 'Q02' for t in failures):
        lines.append('- Đọc thực tế A/Q02: top-1 unit 15 nói Rabbit mất găng tay/quạt, nhầm cảnh; top-2 unit 1 offset 700–1500 có watch trong waistcoat-pocket nhưng thiếu phần đầu gold. Vì thế vừa có lỗi xếp hạng top-1, vừa có ảnh hưởng của gold toàn đoạn. Không sửa gold/test sau khi thấy kết quả; nêu rõ giới hạn của phép đo.')
    lines += ['', f"Cấu hình được chọn bằng dev: **{selection['selected']}**. Cửa sổ cố định đơn giản, có thể cắt câu/điều kiện và lặp dữ liệu do overlap. Giữ đoạn tăng tính liên tục nhưng đoạn hội thoại ngắn vẫn có thể thiếu chủ thể. Filter hữu ích khi phạm vi có sẵn, chỉ tác động bốn câu đã định nghĩa; câu khác B/C phải trùng kết quả.", '',
        '## Giới hạn, AI và bước hoàn tất', '',
        '- Corpus một tác phẩm tiếng Anh, model tiếng Anh nhỏ; không suy rộng sang tài liệu tiếng Việt, pháp lý hay doanh nghiệp. Không xử lý OCR trong corpus này.',
        '- Test chỉ năm câu: mỗi câu tương đương 20 điểm phần trăm. Không kiểm định thống kê hoặc tuyên bố tốt nhất tổng quát. Exact full-paragraph gold khắt khe; diễn đạt tương đương có thể bị đánh trượt nếu chưa có nhãn xác nhận.',
        ('- Đã có 90 nhãn kèm lý do và danh tính người đánh giá trong labels.json; học viên cần kiểm tra và giải thích được các nhận định. Nhãn AI hỗ trợ không thay thế xác nhận của học viên hoặc chấm thủ công độc lập.' if audit else '- Chưa có nhãn; học viên cần đọc/chấm mẫu hoặc công khai phương pháp đánh giá có AI hỗ trợ. Báo cáo giữ CHƯA CHẤM đến khi có nhãn có lý do và người đánh giá rõ ràng.'),
        '- AI sử dụng: Codex hỗ trợ code, câu hỏi, gold, phân tích chỉ số và báo cáo. Kiểm chứng bằng source paragraph, tests về metric/offset/filter/lưu bền/nạp lại, chạy thật embedding và retrieval. Học viên cần đọc lại evidence và giải thích được bài.',
        '- Nếu mở rộng: thêm câu có điều kiện dài, corpus nhiều tài liệu; thiết kế test mới độc lập; thử overlap cố định khi so sánh phương pháp chunk để tách yếu tố nhiễu. Chỉ chỉnh trên dev.', '',
        f'Artifacts: `{rel}/` gồm metrics, run config/version/hash, top-3 trace, chunk snapshots, dev selection, protocol lock và audit CSV/HTML. Lệnh tái lập: xem `HUONG_DAN_EVAL.md`.']
    path = ROOT / 'report/individual/BAO_CAO_DU_AN.md'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    rows = []
    for s in 'ABC':
        d, t = metrics[f'{s}/dev'], metrics[f'{s}/test']
        rows.append({'strategy': s, 'chunking': 'fixed' if s == 'A' else 'paragraph',
            'chunk_size': 800, 'overlap': 100 if s == 'A' else 0,
            'metadata': 'document_id,source,page,chapter,language,start,end',
            'filter': 'chapter if supplied in question' if s == 'C' else 'none',
            'vectorizer': run['model'], 'hypothesis': {'A': 'simple overlapping baseline',
            'B': 'paragraph boundaries retain meaning', 'C': 'chapter scope reduces distractors'}[s],
            'dev_hit1': d['hit1'], 'dev_hit3': d['hit3'], 'test_hit1': t['hit1'],
            'test_hit3': t['hit3'], 'notes': f'Measured artifacts: {rel}; audit ' +
                ('AI-assisted; human verification pending' if audit_info and audit_info.get('review_type') == 'ai_assisted'
                 else 'labels imported; see reviewer provenance' if audit else 'pending')})
    write_csv(ROOT / 'artifacts/experiment_log.csv', rows)
    print(path)


if __name__ == '__main__':
    main()
