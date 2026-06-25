# Kế hoạch Tuần 1: Khởi động & Xây dựng Baseline Anomaly Detection

## 📊 Team Kinh Tế (Economics)

**1. Nhiệm vụ cốt lõi:**
Thay vì chọn feature để dự báo CPI như dự định ban đầu, team Kinh tế sẽ tập trung vào **phân tích tín hiệu cảnh báo sớm (Early Warning Signals)** dựa trên các lý thuyết vĩ mô (Minsky, Mundell-Fleming).

* Lập danh sách 100+ chuỗi thời gian vĩ mô (Tiền tệ, Kinh tế thực, Bên ngoài, Alternative Data).
* Soạn tài liệu giải thích cơ sở lý luận kinh tế tại sao các chuỗi này lại phá vỡ tương quan khi có khủng hoảng.
* Xác định 3-5 sự kiện lịch sử làm "Ground truth" (vd: Lạm phát 2011, Covid 2020, Tỷ giá 2022) và xác định timeline chính xác của các sự kiện này.

**2. Yêu cầu đầu ra (Deliverables):**
* Một file **Excel/Google Sheets** chứa danh sách cấu trúc các Feature (100+ biến số).
* Một file **Docs (Word)** giải thích lý thuyết các tín hiệu cảnh báo sớm.
* Upload vào Folder Workspace của Team Kinh Tế trên Google Drive.

**3. Tiêu chí nghiệm thu (Acceptance Criteria):**
* [ ] File Excel có tối thiểu 50-100 features, phân nhóm rõ ràng (Tiền tệ, Kinh tế thực, Yếu tố bên ngoài, Alternative Data).
* [ ] File Docs có lập luận kinh tế cho các kịch bản đứt gãy tương quan, có mốc thời gian (timeline) của các đợt khủng hoảng lịch sử để team CS backtest.

---

## 💻 Team Kỹ Thuật (CS)

**1. Khởi động môi trường (Environment Setup):**
* Pull code từ Github về máy local.
* Thiết lập môi trường làm việc bằng `uv`. (Chưa cần cài packages ngay ở đầu tuần nếu chưa được update `pyproject.toml`, nhưng sẽ chuẩn bị tinh thần cài các thư viện cho ML: `pandas`, `numpy`, `scikit-learn`, `hmmlearn`, `ruptures`, `torch`, `shap`, vv.)
* Chạy `uv run python -m ai_quantum_hvtc doctor` để đảm bảo không bị lỗi.

**2. Nhiệm vụ cốt lõi:**
* Tạo cấu trúc thư mục mới: `data/`, `models/`, `analysis/`.
* Viết script tiền xử lý dữ liệu và **Baseline Anomaly Detection** sử dụng thuật toán **Isolation Forest** (Module 2A).
* Trong tuần 1, chỉ tập trung vào Isolation Forest để chứng minh pipeline hoạt động (Data Ingestion -> Anomaly Score -> CSV output), khoan làm Autoencoder hay HMM.
* Chạy thử mô hình trên dữ liệu rác (Dummy Data) nhưng cấu trúc giống với 100+ biến vĩ mô dự kiến.

**3. Yêu cầu đầu ra (Deliverables):**
* Script chạy Isolation Forest xuất ra `anomaly_scores.csv` và tự động đẩy vào CS Workspace trên Google Drive thông qua `sync_drive.py`.
* Toàn bộ Source Code của Baseline phải được Commit và Push lên Github.

**4. Tiêu chí nghiệm thu (Acceptance Criteria):**
* [ ] Pipeline có thể tự động chạy Isolation Forest trên dummy data mà không cần can thiệp thủ công.
* [ ] Tự động đồng bộ file `anomaly_scores.csv` lên Google Drive thành công thông qua script sync.
