# Báo cáo cá nhân — Data Ingestion Engineering

Họ tên / MSSV / lớp: **học viên bổ sung trong STUDENT.md**.

## Dữ liệu và pipeline

- Chủ đề: truy xuất bằng chứng trong nguyên tác tiếng Anh *Alice’s Adventures in Wonderland* (Lewis Carroll, 1865).
- Nguồn: https://www.gutenberg.org/ebooks/11 .
- Corpus: 69 đơn vị có ý nghĩa theo thứ tự chương, mỗi đơn vị ≥1.500 ký tự. Đây là đơn vị text tương đương theo GUIDE, không phải 69 trang PDF. Loại mục lục, thông báo giấy phép, marker minh họa và dấu trang trí. Manifest lưu số ký tự, ranh giới trong từng chương và SHA-256 raw.
- Chuẩn hóa NFC, gộp khoảng trắng trong đoạn, giữ dòng trống giữa đoạn. ID document = pg11; page = ID unit toàn corpus; chapter/title được trích trực tiếp từ heading, language = en từ header. Chunk lưu offset start/end chính xác trong unit.
- Model: `sentence-transformers/all-MiniLM-L6-v2`, 384 chiều, CPU ONNX qua FastEmbed 0.7.4. Query/document cùng model; không prefix riêng, cosine trong Qdrant chuẩn hóa vector. Qdrant client 1.20.0, persistent local tại `starter/.qdrant`, exact search. Phiên bản Python 3.12.10; lock đầy đủ và SHA trọng số trong artifacts.
- Chi phí API trả phí: 0 USD; không quy đổi điện, CPU, dung lượng hoặc thời gian tải model thành tiền. Không dùng LLM sinh đáp án.
- Lưu snapshot bằng ID ổn định; nạp lại xóa các point cũ của collection A/B/C rồi nạp snapshot mới, xử lý cả tài liệu sửa/xóa. Không có giao dịch bao trọn snapshot: lỗi giữa chừng cần chạy lại; lỗi được ghi error.log.

## Cấu hình và benchmark

| Cấu hình | Chunk | Retrieval |
|---|---|---|
| A | 800 ký tự, overlap 100 | cosine top-3, không filter |
| B | nhóm đoạn tối đa 800 ký tự; đoạn dài tách câu/từ | giống A, không filter |
| C | dùng nguyên chunk và vector B | thêm filter chapter chỉ khi câu hỏi chỉ định |

- A–B thay phương pháp chunking (gồm overlap); không thể tách riêng tác động của overlap khỏi ranh giới đoạn. B–C chỉ thay filter. C tái sử dụng embedding B nên thời gian embedding gần 0 không có nghĩa thuật toán embedding nhanh hơn.
- 20 câu: 15 dev Q01–Q15 (I–VIII), 5 test Q16–Q20 (IX–XII). Filter: Q04/Q07/Q13/Q18; chương nằm trong câu hỏi, không lấy từ gold. Evidence là đoạn gốc đã kiểm chứng tồn tại; metric chấp nhận đúng nguồn + unit + đủ nguyên evidence trong một chunk.
- Tiêu chí chốt trước test: ưu tiên dev Evidence Hit@3, sau đó Hit@1, ít chunk và tên cấu hình. Đã chọn **B**, lưu selection.json trước truy xuất test. Các cấu hình còn lại vẫn chạy test để so sánh; không chỉnh theo điểm test.
- AI hỗ trợ soạn benchmark và đã thấy nội dung câu test trong lúc viết/kiểm tra gold; không tuyên bố test mù độc lập. Tách chương giảm lặp nội dung nhưng vẫn chung nhân vật/chủ đề.

## Kết quả truy xuất đo thực tế

| Strategy | Split | Hit@1 | Evidence Hit@3 | Số chunk | Embed (s) | Store (s) |
|---|---|---|---|---|---|---|
| A | dev | 2/15 (13.3%) | 9/15 (60.0%) | 225 | 10.856 | 1.416 |
| B | dev | 8/15 (53.3%) | 12/15 (80.0%) | 238 | 11.460 | 1.493 |
| C | dev | 8/15 (53.3%) | 12/15 (80.0%) | 238 | 0.000 | 1.487 |
| A | test | 3/5 (60.0%) | 3/5 (60.0%) | 225 | 10.856 | 1.416 |
| B | test | 4/5 (80.0%) | 5/5 (100.0%) | 238 | 11.460 | 1.493 |
| C | test | 4/5 (80.0%) | 5/5 (100.0%) | 238 | 0.000 | 1.487 |

Thời gian là một lượt đo trên máy hiện tại; embed/store ở bảng được lặp cho hai split để tiện đọc, không cộng hai lần. Tải model đo riêng; C dùng lại vector B.

## Coherence, metadata và grounding

- Coherence: cùng 10 unit đầu, anchor ký tự 100; mỗi cấu hình lấy chunk đầu chứa anchor. 30 mẫu, thang 0–2.
- Metadata: 5 câu test × top-3 × 3 cấu hình = 45 bản ghi. Đối chiếu source, document_id, page, chapter và offset với pages.jsonl; thang 0/1.
- Grounding: 5 câu test × 3 cấu hình = 15 mẫu; đọc cả top-3 để chấm 0/1/2. Không coi exact evidence hit là nhãn grounding hoặc coherence.

| Strategy | Coherence /2 | Metadata đúng | Grounding /2 |
|---|---|---|---|
| A | CHƯA CHẤM | CHƯA CHẤM | CHƯA CHẤM |
| B | CHƯA CHẤM | CHƯA CHẤM | CHƯA CHẤM |
| C | CHƯA CHẤM | CHƯA CHẤM | CHƯA CHẤM |

Filter compliance tự động (đối chiếu input filter, không thay audit metadata):

| Cấu hình/split | Top-3 tuân thủ / số câu yêu cầu filter |
|---|---|
| A/dev | 0/3 |
| B/dev | 1/3 |
| C/dev | 3/3 |
| A/test | 0/1 |
| B/test | 0/1 |
| C/test | 1/1 |

Trường chapter giúp thu hẹp bối cảnh giữa nhiều cảnh dùng cùng từ (trà, động vật, tarts). Page và offset giúp mở đúng đoạn gốc. Hạn chế: chapter là phạm vi rộng, không giúp phân biệt hai đoạn trong cùng chương; filter sai có thể loại hết bằng chứng.

## Tác động và ví dụ lỗi

- A–B: dev Hit@3 9/15 → 12/15; Hit@1 2/15 → 8/15; số chunk 225 → 238.
- B–C: dev Hit@3 12/15 → 12/15; Hit@1 8/15 → 8/15; số chunk 238 → 238.
- Lỗi A/Q01 (dev): gold pg11/unit 1; top-1 unit 1. Top-3 không chứa trọn đoạn gold tại đúng unit. Đọc trace để phân biệt sai chủ đề với evidence bị cắt; metric tự động không chứng minh hoàn toàn không trả lời được.
- Lỗi A/Q02 (dev): gold pg11/unit 1; top-1 unit 15. Top-3 không chứa trọn đoạn gold tại đúng unit. Đọc trace để phân biệt sai chủ đề với evidence bị cắt; metric tự động không chứng minh hoàn toàn không trả lời được.
- Đọc thực tế A/Q01: top-1 unit 1 offset 2100–2383 vẫn có jar rỗng và lý do sợ làm chết người bên dưới; nhưng phần đầu đoạn gold bị tách sang chunk 1400–2200 nên strict Evidence Hit@3 = 0. Đây là ví dụ gold nguyên đoạn khắt khe hơn lượng thông tin tối thiểu để trả lời, không nên diễn giải thành không có đáp án.
- Đọc thực tế A/Q02: top-1 unit 15 nói Rabbit mất găng tay/quạt, nhầm cảnh; top-2 unit 1 offset 700–1500 có watch trong waistcoat-pocket nhưng thiếu phần đầu gold. Vì thế vừa có lỗi xếp hạng top-1, vừa có ảnh hưởng của gold toàn đoạn. Không sửa gold/test sau khi thấy kết quả; nêu rõ giới hạn của phép đo.

Cấu hình được chọn bằng dev: **B**. Cửa sổ cố định đơn giản, có thể cắt câu/điều kiện và lặp dữ liệu do overlap. Giữ đoạn tăng tính liên tục nhưng đoạn hội thoại ngắn vẫn có thể thiếu chủ thể. Filter hữu ích khi phạm vi có sẵn, chỉ tác động bốn câu đã định nghĩa; câu khác B/C phải trùng kết quả.

## Giới hạn, AI và bước hoàn tất

- Corpus một tác phẩm tiếng Anh, model tiếng Anh nhỏ; không suy rộng sang tài liệu tiếng Việt, pháp lý hay doanh nghiệp. Không xử lý OCR trong corpus này.
- Test chỉ năm câu: mỗi câu tương đương 20 điểm phần trăm. Không kiểm định thống kê hoặc tuyên bố tốt nhất tổng quát. Exact full-paragraph gold khắt khe; diễn đạt tương đương có thể bị đánh trượt nếu chưa có nhãn xác nhận.
- Học viên phải tự đọc và chấm 90 mẫu trong review.html, tải labels.json và nhập nhãn để tổng hợp. Báo cáo giữ CHƯA CHẤM đến khi có nhãn thật; không hoàn tất phần chấm thủ công bằng số giả.
- AI sử dụng: Codex hỗ trợ code, câu hỏi, gold, phân tích chỉ số và báo cáo. Kiểm chứng bằng source paragraph, tests về metric/offset/filter/lưu bền/nạp lại, chạy thật embedding và retrieval. Học viên cần đọc lại evidence và giải thích được bài.
- Nếu mở rộng: thêm câu có điều kiện dài, corpus nhiều tài liệu; thiết kế test mới độc lập; thử overlap cố định khi so sánh phương pháp chunk để tách yếu tố nhiễu. Chỉ chỉnh trên dev.


