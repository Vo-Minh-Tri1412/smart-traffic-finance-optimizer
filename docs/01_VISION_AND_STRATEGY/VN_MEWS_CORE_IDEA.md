# VIETNAM MACRO EARLY WARNING SYSTEM (VN-MEWS)
**"Phát hiện khủng hoảng kinh tế Việt Nam trước khi nó xảy ra"**

---

## 1. BÀI TOÁN (THE PROBLEM)

### 1.1 Vấn đề cốt lõi

Mọi cuộc khủng hoảng kinh tế đều có **tín hiệu yếu (weak signals)** xuất hiện trước — nhưng chúng bị chìm trong nhiễu dữ liệu và không ai nhìn thấy tổng thể. Khi chúng trở nên rõ ràng thì đã quá muộn.

Việt Nam đã trải qua ít nhất 3 "cú sốc" có thể phát hiện sớm:

| Sự kiện | Khi công bố | Tín hiệu yếu xuất hiện từ |
|---|---|---|
| Lạm phát 2011 (18.7%) | Q1/2011 bùng nổ | Q2/2010 — tín dụng tăng 30%+, M2 bơm mạnh |
| Covid-19 Q1/2020 | Tháng 3/2020 lockdown | Tháng 1/2020 — Google Trends "covid" tăng, PMI Trung Quốc sụp |
| Căng thẳng tỷ giá 2022 | Tháng 10/2022 SBV phải tăng mạnh | Tháng 6/2022 — DXY tăng, FED pivot rõ ràng |

**Câu hỏi cốt lõi:**
> *Nếu có một hệ thống AI quét 100+ tín hiệu vĩ mô mỗi ngày, nó có thể phát hiện ra nền kinh tế đang bước vào "chế độ nguy hiểm" sớm hơn 3-6 tháng không?*

### 1.2 Tại sao bài toán này khó

1. **Không có "label" rõ ràng:** Khủng hoảng không phải 0/1. Nền kinh tế chuyển từ bình thường → căng thẳng → khủng hoảng theo gradient, không có ngày cụ thể nào để gán nhãn.
2. **Multivariate + Multi-scale:** 100+ chuỗi thời gian, tần suất khác nhau (ngày/tuần/tháng), đơn vị khác nhau, tương quan phi tuyến phức tạp.
3. **Rare event problem:** Khủng hoảng rất hiếm — chỉ có 3-5 sự kiện trong 20 năm. Không thể train supervised classifier truyền thống vì thiếu positive samples.
4. **Regime shift không thông báo trước:** Nền kinh tế vận hành theo "chế độ" (regime) khác nhau. Mô hình học từ chế độ bình thường sẽ fail hoàn toàn khi chế độ đổi.

---

## 2. GIẢI PHÁP (THE SOLUTION)

### 2.1 Triết lý thiết kế

**Không dự báo con số. Phát hiện sự thay đổi cấu trúc.**

Thay vì hỏi *"CPI tháng sau là bao nhiêu?"*, hệ thống hỏi:
> *"Cấu trúc tương quan giữa các biến vĩ mô có đang thay đổi bất thường không?"*

Khi kinh tế bình thường: các biến có tương quan ổn định, pattern quen thuộc.
Khi tiến vào khủng hoảng: **tương quan đó phá vỡ** — thứ từng cùng tăng bắt đầu phân kỳ, thứ từng độc lập bắt đầu hội tụ.

### 2.2 Kiến trúc 4 tầng

```
┌─────────────────────────────────────────────────────┐
│  TẦNG 1: DATA INGESTION (100+ signals)              │
│  GSO + SBV + IMF + Google Trends + News + BDI...    │
└─────────────────────────┬───────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  TẦNG 2: ANOMALY DETECTION ENGINE                   │
│  Isolation Forest + LSTM Autoencoder                │
│  → "Reconstruction Error" = mức độ bất thường       │
└─────────────────────────┬───────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  TẦNG 3: REGIME CLASSIFICATION                      │
│  Hidden Markov Model (HMM) + Changepoint Detection  │
│  → Phân loại: NORMAL / STRESS / CRISIS              │
└─────────────────────────┬───────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  TẦNG 4: EXPLAINABILITY + ALERT DASHBOARD           │
│  SHAP + Correlation Network + Streamlit             │
│  → "Tín hiệu nào đang kêu cứu?"                    │
└─────────────────────────────────────────────────────┘
```

---

## 3. KỸ THUẬT CHI TIẾT (TECH DEEP DIVE)

### 3.1 Tầng 1 — Dữ liệu (Data Ingestion)

**Nhóm A — Tiền tệ & Tài chính (20 biến)**
- Tỷ giá USD/VND (chợ đen vs chính thức → spread là signal quan trọng)
- M2, M1, tốc độ tăng tín dụng
- Lãi suất liên ngân hàng VNIBOR
- Dự trữ ngoại hối (tháng nhập khẩu)
- VN-Index, HNX, biến động (VIX proxy)
- FED Funds Rate, DXY index

**Nhóm B — Kinh tế thực (20 biến)**
- CPI tổng thể, CPI lõi, CPI lương thực
- PPI (chỉ số giá sản xuất — leading indicator của CPI)
- PMI Sản xuất Việt Nam
- Xuất khẩu, Nhập khẩu, Cán cân thương mại
- FDI đăng ký vs FDI giải ngân (spread = signal)
- Chỉ số sản xuất công nghiệp (IIP)

**Nhóm C — Bên ngoài (15 biến)**
- Giá dầu Brent, Natural Gas
- Giá thép, Đồng, Nhôm (commodity basket)
- Baltic Dry Index (BDI) — cước vận tải biển
- PMI Trung Quốc (leading indicator cho VN)
- Fed dot plot / market-implied rate expectations

**Nhóm D — Alternative Data (10 biến)**
- Google Trends: "lạm phát", "giá vàng", "đô la", "thất nghiệp"
- News Sentiment Score (PhoBERT on CafeF/VnEconomy)
- Giá vàng SJC premium so với thế giới (signal đặc thù VN)

### 3.2 Tầng 2 — Anomaly Detection Engine

**Module 2A: Isolation Forest (Baseline)**

Mỗi time step $t$, vector đặc trưng:
$$\mathbf{v}_t = [x_1(t), x_2(t), ..., x_n(t)] \in \mathbb{R}^n$$

Isolation Forest gán **Anomaly Score** $s(t) \in [0, 1]$:
- $s \approx 0.5$ → bình thường
- $s \rightarrow 1.0$ → bất thường cực cao

**Ưu điểm:** Không cần label. Học từ phân phối của dữ liệu bình thường.

---

**Module 2B: LSTM Autoencoder (Core ML)**

Đây là phần AI thực sự mạnh nhất:

```
Input sequence (window=12 tháng)
    ↓
[LSTM Encoder] → latent vector z (compressed representation)
    ↓
[LSTM Decoder] → reconstructed sequence x̂
    ↓
Reconstruction Error: MSE(x, x̂)
```

**Logic:** Train Autoencoder trên giai đoạn **bình thường** (2010-2018, bỏ qua 2011 spike). Khi nền kinh tế vào trạng thái bất thường, decoder không thể reconstruct lại chính xác → **Reconstruction Error tăng đột biến** → đây là early warning signal.

$$\text{AnomalyScore}(t) = \frac{1}{T}\sum_{i=t-T}^{t} ||x_i - \hat{x}_i||^2$$

**Tại sao LSTM Autoencoder hơn vanilla Autoencoder?**
- LSTM nhớ được temporal dependencies (tháng 1 ảnh hưởng tháng 3)
- Capture được "sequence pattern" chứ không chỉ snapshot tại 1 thời điểm

### 3.3 Tầng 3 — Regime Classification

**Module 3A: Hidden Markov Model (HMM)**

Giả định nền kinh tế có $K=3$ hidden states (regimes):
- **State 0: NORMAL** — kinh tế ổn định, tương quan ổn định
- **State 1: STRESS** — dấu hiệu bất ổn, biến động tăng
- **State 2: CRISIS** — khủng hoảng rõ ràng

HMM học:
- Ma trận chuyển tiếp $A$: $P(\text{state}_{t+1} | \text{state}_t)$
- Emission distribution: phân phối của các biến quan sát tại mỗi state
- **Output:** xác suất hiện tại đang ở mỗi state → P(CRISIS) là early warning indicator

```python
from hmmlearn import hmm
model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000)
model.fit(X_train)
states = model.predict(X_test)
crisis_proba = model.predict_proba(X_test)[:, 2]  # P(CRISIS state)
```

**Module 3B: Ruptures — Changepoint Detection**

Phát hiện **điểm gãy cấu trúc** trong chuỗi thời gian:

```python
import ruptures as rpt
algo = rpt.Pelt(model="rbf").fit(signal)
breakpoints = algo.predict(pen=10)
```

Khi phát hiện changepoint → thông báo: *"Cấu trúc kinh tế vừa thay đổi tại tháng X"*

**Kết hợp HMM + Ruptures:**
- HMM cho biết **đang ở chế độ nào**
- Ruptures cho biết **khi nào chế độ đổi**
- Kết hợp → timeline rõ ràng của các cuộc khủng hoảng

### 3.4 Tầng 4 — Explainability

**Correlation Network Analysis:**

Tại mỗi thời điểm, tính **correlation matrix** của 50 biến chính trong rolling window 12 tháng. Biến network thành đồ thị:
- Node = biến vĩ mô
- Edge = tương quan > threshold
- **Khi khủng hoảng đến: network density tăng** (mọi thứ đột ngột tương quan với nhau — "correlation goes to 1 in a crisis")

Đây là **systemic risk indicator** kinh điển trong tài chính.

**SHAP cho Anomaly Score:**

Giải thích tại sao Anomaly Score cao:
```
Anomaly Score = 0.87 (CRISIS territory)
 ├── Giá vàng SJC premium: +0.23
 ├── VNIBOR - chênh lệch kỳ hạn: +0.18
 ├── Tỷ giá chợ đen spread: +0.15
 ├── News sentiment tiêu cực: +0.12
 └── FDI giải ngân/đăng ký ratio: -0.09
```

---

## 4. PHÂN TÍCH KINH TẾ (ECONOMIST ANALYSIS)

### 4.1 Lý thuyết nền tảng

**4.1.1 Minsky Moment Theory**
Hyman Minsky (1986): Sự ổn định tạo ra bất ổn. Khi kinh tế ổn quá lâu, các agent chấp nhận rủi ro ngày càng cao → tích lũy leverage → đến điểm gãy.

**Implication cho VN-MEWS:**
- Giai đoạn "nguy hiểm" nhất là khi **mọi chỉ số trông có vẻ tốt** — tín dụng tăng, GDP tăng, chứng khoán tăng — nhưng các tỷ lệ rủi ro ẩn đang tích lũy.
- Hệ thống cần đặc biệt chú ý các giai đoạn "quá bình thường".

**4.1.2 Mundell-Fleming Trilemma (đặc thù VN)**
Việt Nam không thể đồng thời có: (1) tỷ giá cố định, (2) tự do dòng vốn, (3) chính sách tiền tệ độc lập.

**Implication:** Khi Fed tăng lãi suất mạnh, SBV buộc phải chọn một trong hai: (a) tăng lãi suất theo → kiềm chế tín dụng → giảm tốc tăng trưởng, hoặc (b) giữ lãi suất → dòng vốn chảy ra → phá giá VND → lạm phát nhập khẩu.

**Biến proxy:** Spread giữa VNIBOR và Fed Funds Rate → khi spread thu hẹp dưới ngưỡng → cảnh báo pressure tỷ giá.

**4.1.3 Credit Cycle Theory (Reinhart & Rogoff)**
"This Time Is Different" (2009): Tăng trưởng tín dụng nhanh (>20%/năm) là báo hiệu đáng tin cậy nhất của khủng hoảng sắp đến — trung bình 3-5 năm sau.

**Ground truth validation:**
- VN 2007-2008: tín dụng tăng 53% → khủng hoảng 2008-2009
- VN 2010-2011: tín dụng tăng 32% → lạm phát 18.7% năm 2011
- VN 2021-2022: tín dụng tăng mạnh + bất động sản → căng thẳng 2022-2023

### 4.2 Chỉ số cảnh báo sớm đặc thù Việt Nam

| Chỉ số | Ngưỡng cảnh báo | Lý thuyết kinh tế |
|---|---|---|
| Tăng trưởng tín dụng YoY | > 20% liên tục 6 tháng | Credit Cycle, Minsky |
| Giá vàng SJC premium vs thế giới | > 5% | Capital flight signal, dollarization risk |
| Tỷ giá chợ đen spread | > 2% vs tỷ giá chính thức | Currency crisis leading indicator |
| FDI giải ngân / FDI đăng ký | < 50% liên tục | Confidence collapse signal |
| VNIBOR kỳ hạn ngắn vs dài | Curve inversion | Liquidity stress |
| PPI - CPI spread | PPI tăng nhanh hơn CPI > 3% | Cost-push inflation sắp lan sang CPI |
| Dự trữ ngoại hối / Nhập khẩu | < 3 tháng | Currency crisis vulnerability (IMF standard) |

### 4.3 Backtesting với Sự kiện Lịch sử

**Test case 1: Lạm phát 2011**
- Ground truth: CPI đỉnh 18.7% tháng 8/2011
- Hypothesis: Hệ thống phát hiện STRESS state từ Q3/2010 (trễ 12 tháng)
- Tín hiệu dự kiến phát hiện: Tín dụng 32%, M2 tăng, nhập khẩu lương thực tăng

**Test case 2: Covid-19 2020**
- Ground truth: GDP Q1/2020 giảm xuống 3.68% (thấp nhất 10 năm)
- Hypothesis: Phát hiện anomaly từ tháng 1/2020
- Tín hiệu dự kiến: PMI Trung Quốc sụp, BDI giảm mạnh, Google Trends "covid", FDI dừng

**Test case 3: Căng thẳng tỷ giá 2022**
- Ground truth: SBV tăng lãi suất điều hành tháng 9/2022 và 10/2022
- Hypothesis: Phát hiện STRESS từ tháng 6/2022
- Tín hiệu dự kiến: DXY tăng mạnh, spread tỷ giá chợ đen, FED hawkish pivot

---

## 5. ĐIỂM KHÁC BIỆT SO VỚI CPI FORECASTING

| Tiêu chí | CPI Forecasting (phổ biến) | VN-MEWS (đề xuất) |
|---|---|---|
| **Câu hỏi** | "CPI tháng sau là bao nhiêu?" | "Nền kinh tế có đang vào vùng nguy hiểm không?" |
| **ML task** | Supervised regression | Unsupervised anomaly detection + sequence modeling |
| **Label** | CPI number (rõ ràng) | Không có label — học từ structure |
| **Rare event** | Không vấn đề | Đây chính là bài toán cốt lõi |
| **Số đội làm** | 30-40% | ~0% |
| **LLM suggest được?** | Ngay lập tức | Không — cần biết HMM, Ruptures, Autoencoder, systemic risk |
| **Demo** | Line chart dự báo | Dashboard với regime meter, correlation network animation, alert timeline |
| **Impact thực tế** | Tham khảo | Công cụ quản lý rủi ro thực sự |

---

## 6. TECH STACK

```
Language:     Python 3.11+
ML Core:      scikit-learn, hmmlearn, ruptures, torch (LSTM Autoencoder)
Data:         pandas, fredapi, requests (GSO API), pytrends (Google Trends)
NLP:          transformers (PhoBERT), underthesea
Explainability: shap, networkx (correlation graph)
Visualization: plotly, streamlit, pyvis (interactive network graph)
Storage:      parquet files, DVC (data versioning)
Testing:      pytest, backtesting với historical events
```

---

## 7. DELIVERABLES & DEMO

**Demo kịch bản gây chấn động:**

> *Người dùng chọn: "Replay: Vietnam 2010-2011"*
>
> Dashboard animation:
> - Tháng 6/2010: Anomaly Score = 0.45 → NORMAL (màu xanh)
> - Tháng 9/2010: Anomaly Score = 0.61 → STRESS (màu vàng) ← **ALERT BẬT LÊN**
> - Tháng 12/2010: Anomaly Score = 0.78 → STRESS HIGH
> - Tháng 3/2011: Anomaly Score = 0.91 → CRISIS (màu đỏ)
> - Tháng 8/2011: CPI chính thức công bố 18.7% ← **12 tháng sau alert**
>
> SHAP panel: "Nguyên nhân cảnh báo tháng 9/2010: 45% từ tăng trưởng tín dụng, 30% từ M2 expansion, 25% từ giá lương thực toàn cầu (FAO index)"

**Đây là thứ không đội nào có.**
