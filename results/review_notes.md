# Cách đánh giá 90 mẫu — Codex hỗ trợ

Người đánh giá: **Codex (AI)**, theo yêu cầu học viên ngày 14/11/2026 (Asia/Bangkok). Chưa có xác nhận của học viên. Không gán nhãn này cho người có tên trong bản Downloads còn trống. Không sửa corpus, benchmark, metric retrieval hoặc cấu hình đã chốt.

## Đã làm gì

- Đọc 20 chunk coherence khác nhau của A/B tại cùng 10 unit/anchor và đối chiếu ngữ cảnh. Kiểm chứng chunk C trùng B trước khi dùng cùng đánh giá: tổng 30 nhãn, không coi các bản sao là mẫu độc lập.
- Đọc text top-3 của năm câu test cho A/B và trường hợp có filter của C. Các câu C không filter được đối chiếu để xác nhận trùng B: tổng 15 nhãn grounding. Chấm dựa vào nội dung và điều kiện câu hỏi, không suy từ Evidence Hit@3.
- Đối chiếu 45 hit test với `starter/data/pages.jsonl`: document_id, source, page, chapter, chapter_title, language, ranh giới unit trong chương, start/end và text đúng lát nguồn. Mỗi nhãn metadata ghi rõ câu, rank, unit, chapter và offsets đã kiểm tra. Đây là kiểm tra bằng mã trên nguồn chuẩn hóa, không phải 45 nhãn do người học chấm tay.
- Mỗi mẫu có điểm và lý do trong `labels.json`; CSV audit có cùng nhãn và người đánh giá. `audit_summary.json` tổng hợp từ nhãn, không tự đặt số trung bình.

## 1. Coherence: đọc riêng chunk có hiểu trọn ý không?

- **0:** không hiểu được ý chính do mất chủ thể hoặc bị cắt nghiêm trọng.
- **1:** đọc được một phần, nhưng chunk có câu dở dang hoặc thiếu ngữ cảnh cần thiết.
- **2:** có thể hiểu độc lập, giữ đủ chủ thể và một ý hoàn chỉnh. Không buộc kể toàn bộ câu chuyện.

Ví dụ `coherence-0`, A/unit 1: hai đoạn đầu còn rõ Alice chán sách và thấy Rabbit, nhưng cuối chunk bị cắt giữa từ `afterwa`. Chấm **1**, vì không mất toàn bộ ý nên không phải 0, nhưng chưa trọn chunk để được 2.

Ví dụ `coherence-1`, B/unit 1: chỉ giữ hai đoạn hoàn chỉnh đó, không lấy phần hồi tưởng rồi cắt dở. Có Alice, hoàn cảnh và sự kiện nên chấm **2**. Cùng chunk của C cũng được 2.

Ví dụ `coherence-22`, B/unit 8: giữ đủ việc co nhỏ do quạt, nhưng toàn đoạn dùng `she/her`, mở bằng “As she said this”, không nêu Alice hoặc lời nói trước đó. Chấm **1**. Đây là giới hạn của paragraph chunking: trọn đoạn chưa chắc tự đủ ngữ cảnh. B/unit 9 cũng thiếu tên chủ thể nên chấm 1.

Kết quả: A = **1,00/2** (10 mức 1); B/C = **1,80/2** (hai mức 1, tám mức 2 mỗi cấu hình).

## 2. Metadata: nhãn chỉ nơi nào có đúng nơi đó không?

**1** khi các trường đủ và phản ánh đúng nguồn; **0** khi sai hoặc thiếu. Ví dụ top-1 B/Q19 thực sự nằm unit 63/chapter 11, text và offsets khớp: metadata = 1, dù hit đó chưa trả lời đúng câu hỏi. Độ liên quan được đo ở retrieval/grounding.

Q18 yêu cầu chapter X. Top-3 A/B có hit chapter IX nhưng trường `chapter: 9` đúng với đoạn được trả về, nên metadata vẫn 1. Việc trả về ngoài chapter X là lỗi **filter compliance** đã báo riêng: A/B test = 0/1, C test = 1/1. Không nhầm “metadata đúng” với “filter đã được áp dụng”.

Kết quả: **15/15 mỗi cấu hình**. Đây là tính đúng so với corpus đã chuẩn hóa, không phải bằng chứng rằng mọi nguồn trên Internet hoặc mọi hit đều hữu ích.

## 3. Grounding: top-3 có đủ để trả lời tất cả vế không?

- **0:** không có bằng chứng hỗ trợ đáp án.
- **1:** có một phần nhưng thiếu vế hoặc điều kiện cần.
- **2:** hợp top-3 có đủ đáp án, điều kiện và vị trí nguồn để truy lại.

Ví dụ A/Q19 (`grounding-9`): có chi tiết Hatter cắn teacup thay bread-and-butter, nhưng không có lý do ông mang đồ đến khi làm nhân chứng. Câu hỏi có cả “mang gì” và “vì sao”, nên chỉ **1**.

B/Q19 (`grounding-10`) và C/Q19: top-2 unit 60 nói rõ first witness là Hatter, ông cầm hai món và chưa uống trà xong khi được gọi. Có đủ cả hai vế nên **2**, dù top-1 chưa đúng cảnh.

A/Q20 (`grounding-12`): top-1 vẫn có Rule Forty-two và đủ điều kiện “more than a mile high”/“leave the court”. Phần dẫn bị cắt khiến metric gold nguyên đoạn báo 0, nhưng bằng chứng để trả lời còn đủ nên **grounding = 2**. Không thay đổi metric tự động sau khi thấy nhãn.

Kết quả: A = **1,80/2** (một mức 1, bốn mức 2); B/C = **2,00/2** (năm mức 2 mỗi cấu hình).

## Giới hạn và bước của học viên

AI đã tham gia xây pipeline/benchmark nên không độc lập với hệ thống được chấm; nhãn có thể thiên lệch. Coherence chỉ lấy 10 unit đầu, không đại diện cả tác phẩm. Test năm câu là mẫu nhỏ. B/C có nhiều hit/chunk trùng nhau. Chưa có điểm do người chấm độc lập hoặc xác nhận của học viên; nếu rubric yêu cầu chấm tay, nhãn AI hỗ trợ không thay phần xác nhận đó.

Để hiểu bài, mở `review.html`, xem ba ví dụ trên rồi đối chiếu lý do với nội dung thực tế. Có thể sửa điểm/lý do nếu không đồng ý và ghi rõ ai sửa, phương pháp sửa. Bản Downloads cũ chưa chấm không cần dùng lại; bản được nhập và tổng hợp nằm ngay trong thư mục run này.
