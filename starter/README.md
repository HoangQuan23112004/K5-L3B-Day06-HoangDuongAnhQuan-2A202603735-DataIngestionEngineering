# Pipeline đã triển khai · FastEmbed + Qdrant local

Chạy bằng Python 3.12, không cần Docker hoặc API key. Hướng dẫn đầy đủ từng bước và cách chấm thủ công: [HUONG_DAN_EVAL.md](../HUONG_DAN_EVAL.md).

Từ thư mục gốc, tạo môi trường và cài:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r starter\requirements.txt
cd starter
..\.venv\Scripts\python.exe -m src.run --validate-only
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:HF_HUB_DISABLE_XET = '1'
..\.venv\Scripts\python.exe -m src.run --verify-reingest
..\.venv\Scripts\python.exe -m src.review
..\.venv\Scripts\python.exe -m src.report
```

Môi trường `.venv` ở **root** repo, không ở `starter/`. Nếu máy hiện tại không nhận `py`, xem lệnh gọi Python bằng đường dẫn thật trong hướng dẫn.

Corpus đã có trong `data/alice.txt` và `data/pages.jsonl`. 69 unit ≥1.500 ký tự; nguồn/quyền/hash/ràng buộc tính trang trong [manifest](../data/manifest.json). Dựng lại từ raw bằng `python -m src.prepare`.

| Module | Chức năng |
|---|---|
| `prepare.py` | Tách chương, logical units, manifest và 20 câu benchmark |
| `ingestion.py` | Chuẩn hóa NFC, giữ đoạn, đọc PDF hoặc pages JSONL |
| `chunking.py` | Fixed-size overlap; group paragraph; giữ offsets |
| `embeddings.py` | all-MiniLM-L6-v2, CPU ONNX, 384 chiều |
| `store.py` | Qdrant persistent local, cosine exact, payload filter, snapshot refresh |
| `evaluation.py` | Hit@1/Evidence Hit@3 đúng nguồn/page và đủ evidence |
| `run.py` | Protocol lock, ingest, dev selection trước test, trace/stats/audit samples |
| `query.py` | Truy xuất top-3 từ store đã lưu |
| `review.py` | HTML offline chấm 90 mẫu, nhập nhãn và tính điểm |
| `report.py` | Sinh báo cáo/experiment log từ artifacts đã đo |

Output nằm ở `../results/<run-id>/`; `../results/latest.json` trỏ tới run hoàn tất gần nhất. Trace chứa nội dung nguồn, score, metadata và gold; audit CSV để trống nhãn ban đầu. Chỉ tạo tổng hợp thủ công sau khi người chấm có điểm và lý do cho toàn bộ mẫu.

Model cache ở `.model_cache/`, store ở `.qdrant/`; cả hai được gitignore. Lần đầu cần mạng tải model. `run.json` ghi phiên bản thư viện, cấu hình, SHA trọng số, thời gian và chi phí API 0 USD. Mỗi run có `requirements-lock.txt` để tái lập môi trường cụ thể.

Các file `docker-compose.yml`, `init.sql`, `.env.example`, `scripts/check_setup.py` là bộ khung PostgreSQL gốc của đề, không dùng trong pipeline Qdrant này. Không chạy `check_setup.py` để kiểm pipeline; dùng `--validate-only` và tests ở trên.
