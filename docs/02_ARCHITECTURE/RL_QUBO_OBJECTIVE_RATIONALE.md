# Reward RL và mục tiêu QUBO cho ROI hiện tại

Ngày rà soát: 2026-09-17. Phạm vi là map hiện tại đã được người dùng giữ nguyên, không phải
khẳng định ranh giới hành chính Quận 7. Đây là thiết kế mục tiêu và kiểm toán code, **không phải
báo cáo model đã huấn luyện, dữ liệu OD đã hiệu chỉnh hoặc lợi ích kinh tế đã được kiểm chứng**.

## 1. Quyết định cốt lõi

Hai lớp tối ưu cùng hướng tới **giảm chi phí xã hội của nhu cầu di chuyển cố định trên toàn ROI**:

- RL chọn pha đèn hợp lệ theo thời gian; mục tiêu vận hành là giảm chi phí di chuyển.
- QUBO chọn vị trí đầu tư trong ngân sách; mục tiêu là giá trị hiện tại của phần chi phí giảm
  được so với baseline, trừ chi phí đầu tư/vận hành.

Không lấy giá trị bất động sản, doanh thu bệnh viện, tổng giá trị hàng hóa hay nhãn “xe tải” làm
lợi ích do đèn thông minh tạo ra. Một chuyến hàng 100 triệu đồng đến sớm hơn không tạo ra lợi ích
100 triệu đồng. Chỉ phần tiết kiệm thời gian, chi phí tồn kho/hư hỏng thực sự tránh được hoặc
chi phí vận hành biên có căn cứ mới được tính. Đây là lựa chọn mô hình, không phải số liệu quan sát.

Map-specific nghĩa là giữ được **facility nguồn → facility đích → mục đích → giờ khởi hành →
tuyến đường → số người/hàng → kết quả SUMO**, không phải gắn một hệ số tùy ý cho từng tòa nhà.
Hai OD có thể cùng đơn giá thời gian nhưng vẫn có lợi ích khác nhau vì lưu lượng, số người,
thời gian tiết kiệm, lịch đến hạn và mức ảnh hưởng của can thiệp khác nhau.

## 2. Công thức đang có trong code

Với xe/chuyến `v`, valuation OD có số người `n_v`, giá trị thời gian `w_v` (VND/người-giờ),
đơn giá độ tin cậy `q_v`, hai hệ số `m_service`, `m_flow`:

```text
c_v = n_v * m_service * m_flow
      * (w_v * delta_timeLoss_v + q_v * delta_reliability_v) / 3600
r_a,t = clip(-sum(c_v for sampled vehicles at signal a) / S_RL, r_min, r_max)
```

Đã triển khai trong `ai_quantum_hvtc/map_economics/reward.py` và
`ai_quantum_hvtc/rl/map_economic_reward.py`:

- Dùng hiệu của `getTimeLoss()` giữa hai lần nhìn thấy xe tại cùng agent, không cộng lại tổng
  tích lũy mỗi bước. Lần nhìn thấy đầu tiên chỉ đặt mốc; delta âm/reset được đặt lại mốc.
- Callback chỉ thu xe trên các lane của agent tại thời điểm lấy mẫu. Xe rời đi giữa hai mẫu
  và chi phí trước lần nhìn thấy đầu tiên không được ghi đầy đủ.
- Ledger tiền chưa clip được lưu riêng; clip áp dụng sau khi cộng chi phí của signal.
- API thuần cho phép delta reliability, nhưng callback SUMO-RL hiện không cung cấp nó, nên
  thành phần này bằng 0. Không gọi timeLoss thông thường là “độ tin cậy”.
- Định danh flow/OD và route được dùng để tra valuation. Thứ tự fallback: OD, building đích/nguồn,
  zone đích/nguồn, corridor, global. Callback hiện chủ yếu truyền flow ID, zone và route;
  không tự suy ra facility đích bằng hình ảnh hoặc vị trí xe.
- Các bản sao vector environment giữ ledger riêng; không được cộng ledger của một callback gốc
  rồi gọi đó là toàn bộ chi phí run.

Theo [SUMO TripInfo](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html), `timeLoss` là
thời gian mất do chạy chậm hơn tốc độ lý tưởng của xe; dừng theo lịch không được tính. Chờ trước
khi được chèn vào mạng là `departDelay`, một trường khác. TripInfo mặc định chỉ xuất xe đã đến;
phải xử lý xe chưa hoàn thành khi đánh giá một horizon hữu hạn.

**Kết luận kiểm toán:** reward hiện tại là tín hiệu huấn luyện cục bộ có diễn giải kinh tế, không
phải bộ kế toán toàn mạng. SUMO timeLoss tăng dần nên reward này chủ yếu không dương; điều đó
không sai: model học cách nhận ít chi phí âm hơn. Nhưng giảm cost bằng cách làm xe không xuất hiện
trong vùng quan sát là failure mode cần chặn bằng bộ đánh giá độc lập.

### Khác biệt RL/QUBO cần kiểm soát

RL có nhân hai multiplier; QUBO v1 cố ý không nhân chúng vào công thức thời gian. Baseline dùng
chung đặt cả hai bằng đúng 1 trong `configs/economics/district7_map_economic_assumptions.v1.example.json`
(cập nhật và kiểm thử do integrator thực hiện), giữ nhãn assumption,
và không gọi đây là premium có nguồn. Nếu dùng multiplier khác 1 về sau, cần một quy tắc định giá
biên đã duyệt áp dụng giống nhau ở cả hai lớp và test parity; chỉ đổi config RL sẽ làm lệch mục tiêu.

Clipping và RL discount cũng làm mất tính tương đương với tổng VND không chiết khấu. Giữ scale cố
định trong một experiment, báo tỷ lệ bước bị clip, đánh giá policy bằng cost gốc. Không chọn policy
hoặc portfolio bằng tổng reward đã clip. `gamma` RL là tham số credit assignment, không phải lãi suất
chiết khấu tài chính năm. Không cộng capex vào mỗi bước RL khi investment mask đang cố định.

## 3. Mục tiêu đánh giá chung được đề xuất

Cho scenario `s`, seed `k`, investment mask `x`, policy `pi`, giữ cùng danh sách nhu cầu dự định
`D_s,k`, thời gian xuất phát, occupancy và routing assumptions khi so baseline/candidate.
Cost pilot ít giả định nhất là:

```text
C_time(x, pi, s, k) = sum_v n_v * w_OD(v) * d_v(x, pi, s, k) / 3600
```

Ở thí nghiệm **tuyến cố định**, `d_v = departDelay_v + timeLoss_v` là đại lượng đề xuất để
không thưởng việc ngăn xe vào mạng. Giữ speedFactor và các dừng theo lịch nhất quán. Nếu cho phép
đổi tuyến, timeLoss thấp chưa chắc tổng thời gian ngắn: tuyến vòng dài nhưng chạy nhanh có thể
ít timeLoss. Khi đó dùng tổng thời gian từ khởi hành dự định đến đến nơi trừ một mốc OD cố định,
hoặc so tổng thời gian của cùng OD; không dùng mốc free-flow thay đổi theo tuyến của từng policy.

Đây là **đặc tả bộ đánh giá cần bổ sung**, không phải khẳng định callback đã đo đủ. Cần ledger
nhu cầu dự định để nối xe đã hoàn thành, đang chạy, chưa được chèn, bị loại/teleport và lỗi route.
Sau cửa sổ phát sinh demand, chạy drain-out với giới hạn rõ ràng. Nếu không giải tỏa hết, báo phần
chưa phục vụ và giới hạn dưới của chi phí; không so riêng tập xe hoàn thành hoặc gán phần còn lại
bằng 0. Chỉ kết luận tiết kiệm khi đạt tiêu chí phục vụ tương đương đã định trước.

Sau khi có bằng chứng, mở rộng theo các kênh riêng:

```text
C_public = C_time + C_reliability + C_vehicle_operation + C_environment
           + C_cargo_marginal + C_schedule
```

Đây là menu thành phần, không phải yêu cầu bật tất cả. Mỗi kênh cần định nghĩa, đơn vị, nguồn,
năm giá và test chống trùng. Reliability dùng biến thiên thời gian của cùng OD/time bin trên nhiều
ngày/seed hoặc độ trễ đến hạn có định nghĩa; không suy ra từ một bước xe chậm. Không tính đồng thời
reliability/schedule penalty nếu cùng phản ánh một thiệt hại. Không vừa dùng VOC đã chứa nhiên liệu
vừa cộng nhiên liệu lần nữa. Giá trị hàng hóa chỉ cho phép chi phí cơ hội tồn kho/hư hỏng biên,
không cộng tổng giá trị vận chuyển. VOT/người nhân occupancy một lần; VOT/xe đã bao gồm occupancy
không được nhân lại. Các kênh chưa có dữ liệu phải tắt, không diễn giải bằng 0 là “không có hại”.

Nguồn kinh tế địa phương và giới hạn chuyển giao nằm trong
[economic source review](MAP_ECONOMIC_SOURCE_RESEARCH.md). Các báo cáo lịch sử là bằng chứng
phương pháp, chưa phải bảng giá OD hiện tại. Income/người/tháng không tự động bằng VOT lao động.

## 4. Từ cùng cost sang QUBO

Đặt `F(x)` là chi phí vận hành xã hội **một năm đại diện** sau khi tổng hợp scenario/seed bằng lịch
ngày làm việc, cuối tuần, ca kíp và trọng số đã công bố. Không nhân một peak 900 giây với 365 ngày.
`F(0)` dùng fixed-time/rule-based baseline đã chốt; các điểm không đầu tư tiếp tục baseline.

```text
B_i  = F(0) - F(e_i)
I_ij = F(e_i) + F(e_j) - F(e_i + e_j) - F(0)
B_hat(x) = sum_i B_i*x_i + sum_(i<j) I_ij*x_i*x_j

min E0(x) = [sum_i (alpha*capex_i + P_O*opex_i - P_B*B_i)*x_i
             - P_B*sum_(i<j) I_ij*x_i*x_j] / S_Q
```

`I_ij` là phần lợi ích đôi còn lại sau khi trừ hai singleton, **không phải toàn bộ lợi ích khi
đầu tư cả đôi**. Dương là bổ trợ, âm là trùng lợi ích hoặc nghẽn chuyển chỗ. Ví dụ số giả minh họa:
singleton tiết kiệm 10 và 8, đôi tiết kiệm 15 thì interaction là -3, không phải +15. Giữ các tác
động âm lên OD hàng xóm; đừng chỉ thu các tuyến được cải thiện.

QUBO hiện có các hệ số, input provenance, ba chế độ interval và budget slack như
[MAP_AWARE_QUBO](MAP_AWARE_QUBO.md). `P_B`, `P_O` phải là hệ số hiện giá công khai; với lợi ích
hằng năm không đổi có thể tính từ tổng `1/(1+r)^y` trên horizon đã duyệt. Dòng tiền thay đổi theo
năm cần tính riêng, không ép thành một hệ số tùy ý. `alpha=1` cho diễn giải net public value thông
thường; khác 1 là trọng số chính sách và cần diễn giải, không gọi là net benefit tiền thuần.

```text
E(x, z) = E0(x) + lambda*(sum_i ceil(capex_i/U)*x_i + slack(z) - floor(Budget/U))^2
```

Slack cho phép không tiêu hết ngân sách. Bộ build dùng bound an toàn để penalty ngân sách lớn
hơn mức giảm năng lượng thuận lợi tối đa; rounding bảo thủ có thể loại một phương án vẫn vừa
ngân sách VND thực. Đây là ràng buộc ngân sách đã có, **không phải ràng buộc công bằng đã có**.

QUBO là xấp xỉ bậc hai của hệ thống giao thông phi tuyến. Missing pair hiện bằng 0 không có nghĩa
là không tương tác. Cần chạy singleton, các đôi có đường đi chung/quan hệ upstream-downstream,
và mask giữ lại để kiểm tra sai số. Sau tối ưu phải chạy lại mask được chọn trong SUMO trên demand
và seed chưa dùng để dựng hệ số. Nếu sai số lớn, bổ sung pair hoặc tối ưu black-box/classical;
không khẳng định QUBO chính xác toàn mạng hay có ưu thế lượng tử.

### RL policy trong thí nghiệm investment mask

Chốt một protocol trước khi đo `F`: policy shared điều kiện hóa theo mask, hoặc train lại cho từng
mask với cùng ngân sách huấn luyện/seed. Hai protocol trả lời hai câu hỏi khác nhau. Không so model
được train kỹ ở mask A với model chưa thích nghi ở mask B rồi quy mọi khác biệt thành hiệu quả đầu tư.
Kiểm tra fixed-time, rule-based, RL-full và RL-budget trên cùng demand; full-upgrade chỉ là comparator,
không giả định luôn tốt nhất. Pipeline train/evaluate theo mask hiện chưa hoàn thiện trong repository.

## 5. An toàn, tiếp cận thiết yếu và công bằng

Đề xuất dùng hai tầng: an toàn pha đèn là điều kiện hành động hợp lệ; công bằng/tiếp cận là điều
kiện chấp nhận policy/portfolio. Không dùng một reward tiền lớn để cho phép đánh đổi xung đột pha.
Giữ yellow/all-red/minimum-green; ưu tiên khẩn cấp chỉ khi tương thích clearance. Ví dụ TOML hiện
có emergency action filter `pending_implementation`: training gate không đồng nghĩa filter đã chạy,
và ghi `max_wait_seconds=0` không chứng minh có thể phục vụ tức thì an toàn.

Hai guardrail nhóm chính cần báo, ngưỡng phải được duyệt trước đánh giá:

1. An toàn/phục vụ: hành động không hợp lệ, xung đột clearance, xe teleport/route lỗi, demand chưa
   chèn/chưa hoàn thành, starvation và spillback. Không chấp nhận “tốt hơn” do giảm nhu cầu được phục vụ.
2. Phân phối: person-delay và phân vị cao theo zone, trường học/bệnh viện, hướng vào/ra và transit;
   kiểm tra vùng được lợi và chịu thiệt, không chỉ trung bình toàn mạng. Thiếu mẫu phải báo thiếu mẫu.

Chưa có ngưỡng thực nghiệm thì không bịa giới hạn định lượng. Có thể dùng cùng VOT người-phút làm
baseline công bằng và chạy sensitivity VOT theo mục đích; không mặc định ưu tiên người thu nhập cao.
VOT suy từ thu nhập có thể hạ trọng số chuyến của người thu nhập thấp hoặc hành khách bus:
chính sách tối đa VND khi đó chưa chắc tối đa phúc lợi công bằng. Báo thêm person-delay không nhân
VOT, access và tác động theo nhóm; không dùng VOT thấp để cho phép starvation của một nhóm.
Tỷ lệ bus capacity không bằng số hành khách. Với transit phải tránh cộng cả delay của bus nhân số
người và delay của chính các passenger records thêm lần nữa. Hạn đến lớp/ca làm/lịch giao hàng
cần lịch thực hoặc assumption rõ ràng, không tự suy ra từ nhãn education/industrial.

## 6. Hợp đồng dataset để objective có ý nghĩa

Mỗi trip/demand row cần ít nhất: parent facility hoặc boundary connector nguồn/đích, directed OD,
mục đích, departure time bin, mode, volume/expansion weight, occupancy, route, valuation ID,
nguồn/assumption và calendar. Một campus/cảng bị chia polygon chỉ có một tổng demand trước phân bổ
cổng; không nhân tổng facility vào từng mảnh. Building không có population/jobs/enrollment không
có bằng chứng để tự tạo “số xe thực tế”; diện tích chỉ là proxy cần sensitivity.

Phải tách bốn loại: trong→trong, ngoài→trong, trong→ngoài, ngoài→ngoài đi xuyên ROI. Endpoint cắt
ở ranh giới là connector, không phải tòa nhà giả. Bảo toàn hướng và các phần chuyến đi quan sát được.
Với chuyến xuyên biên giới, lợi ích đo được chỉ thuộc phạm vi mô phỏng; không tuyên bố lợi ích toàn
chuyến ngoài map. Nếu đầu tư làm dồn hàng chờ ra ngoài ROI thì bộ đếm inflow/outflow/uninserted
phải phát hiện, không coi là giảm tắc nghẽn.

Sinh SUMO là hợp lý để kiểm soát counterfactual và tạo nhãn chính xác **trong mô hình**. Nó không
biến assumption thành điều tra thực địa. Phân bố giờ phải gắn activity/calendar: đi học, ca làm,
giao hàng, lượt thăm bệnh và dịch vụ đêm có cơ chế khác nhau; departure thường là arrival target
trừ travel-time ước lượng với độ phân tán, không tất cả tòa nhà phát xe đồng loạt lúc 07:00.
Khối lượng cần khớp các tổng kiểm soát/count có nguồn nếu có. Nếu chưa có, sinh các low/base/high
scenario minh bạch, không dùng chữ calibrated/observed. Xem
[travel source review](CURRENT_ROI_TRAVEL_SOURCE_REVIEW.md) cho nguồn và giới hạn truy cập cụ thể.

Train/validation/test phải tách ở mức ngày/scenario/seed, không chỉ xáo trộn các trip của cùng
trace. Dựng hệ số QUBO bằng tập fit riêng, giữ mask và demand stress chưa thấy để kiểm định.
Dùng seed demand chung cho baseline/intervention giúp giảm nhiễu, nhưng phải ghi nhận quá trình
ngẫu nhiên nội bộ có thể phân kỳ khi điều khiển khác nhau. Báo khoảng bất định qua paired runs,
không coi bounds tham số thấp/cao là confidence interval thống kê.

## 7. Tiêu chí báo cáo và phần chưa xong

Primary KPI là tổng person-delay và cost VND chưa clip cho cùng nhu cầu, sau đó net public value
của portfolio so baseline trên test scenarios. Driver là cost theo OD/time bin và served-demand
accounting. Guardrail là hai nhóm ở mục 5. Không cần một rổ điểm thưởng queue/speed/throughput có
trọng số tùy ý khi chúng chỉ mô tả lại cùng delay; dùng chúng làm chẩn đoán và constraint khi cần.

| Thành phần | Trạng thái qua code audit |
|---|---|
| OD-aware incremental VND evaluator và reward SUMO-RL lấy mẫu | Có; không phải full-network ledger |
| QUBO chi phí/lợi ích biên, pair effects, budget slack, interval modes | Có; cần input hiệu ứng có bằng chứng |
| Multiplier baseline thống nhất bằng 1 | Quy tắc tích hợp; không phải giá trị kinh tế được đo |
| Cost accounting đầy đủ gồm insertion/unfinished/cross-boundary | Đặc tả đề xuất, chưa hoàn tất |
| Reliability/cargo/deadline/VOC/emissions cho reward runtime | Chưa tích hợp đầy đủ; không claim |
| Safety action filter và portfolio equity constraints | Chưa hoàn tất; gate không thay enforcement |
| OD hiện tại có dữ liệu quan sát và VOT đã hiệu chỉnh | Chưa được chứng minh trong các source reviews |
| Training/evaluation full ROI và tác động singleton/pair thực đo | Chưa có kết quả để báo lợi ích |

Đọc code nguồn, tài liệu economics/QUBO, source reviews và cấu hình reward là cơ sở cho trạng thái
trên. Đề xuất thiết kế trong tài liệu này không tự đổi status profile thành approved và không bỏ
production gate. SUMO official docs được mở kiểm tra ngày rà soát; các nguồn kinh tế/travel nằm
trong hai báo cáo nguồn với locator, phạm vi, tuổi dữ liệu và access caveats riêng.
