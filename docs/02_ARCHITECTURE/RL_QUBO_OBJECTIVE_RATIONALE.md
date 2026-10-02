# Reward RL và mục tiêu QUBO cho ROI hiện tại

**Hai thiết kế để so sánh:** R0 là reward thời gian cơ sở ở phần đầu; R1 là đề xuất nghiên cứu
lịch hoạt động + ràng buộc rủi ro/mức phục vụ + potential shaping ở mục 8.
R1 chưa thay runtime và chưa chứng minh tốt hơn R0. Không đồng nhất reward với lợi ích đầu tư.

## Thiết kế kế tiếp đã chốt (2026-09-19), chưa thay callback runtime

[Kế hoạch toàn hệ thống](SYSTEM_DELIVERY_PLAN.md) chọn ledger toàn mạng và shared reward làm
mục tiêu chính kế tiếp. Callback incremental cục bộ được kiểm toán ở mục 2 vẫn là code hiện tại
và sẽ giữ làm ablation; không gọi ledger cục bộ đó là tổng cost toàn mạng.

Với demand, route và occupancy cố định giữa các phương án, đặt `T_v` là thời gian từ khởi hành
dự định đến khi đến đích (bao gồm chờ chèn vào mạng), `T0_v` là mốc tham chiếu cố định của chuyến:

```text
A = sum_v n_v * w_v * T_v / 3600
C = A - sum_v n_v * w_v * T0_v / 3600
r_shared(t) = -(A_accrued(t+dt) - A_accrued(t)) / S
```

`A_accrued` tính thời gian đã phát sinh từ intended departure đến thời điểm hiện tại hoặc arrival,
chỉ cho demand đã đến giờ khởi hành. Một ledger duy nhất cho mỗi environment thu chi phí, không
thu lại một lần cho mỗi signal. Mỗi agent dùng cùng team reward; không cộng các bản sao reward
agent để báo VND. `n_v`, `w_v` được nối từ trip registry/valuation, không suy từ ảnh hoặc nhãn xe.

Khi tất cả chuyến hoàn thành, tổng reward chưa discount tỷ lệ với `-A`; `C` khác `A` bởi hằng số
không phụ thuộc policy. Vì vậy không cần thưởng arrival tùy ý. Scale `S` phải cố định trong một
experiment, fit/chọn từ tập phát triển và ghi manifest; không normalize lại riêng cho từng mask.
Đánh giá bằng `C`/person-delay không clip, không bằng discounted return. Discount/clipping có thể
làm lệch tối ưu theo tổng cost và phải được báo; tính tương đương nêu trên không áp dụng cho chúng.

Ở horizon hữu hạn, không lấy thời gian đã phát sinh của unfinished trips làm full-trip cost.
Ledger giữ pending/running/arrived/error/teleport, chạy drain-out có giới hạn và báo lower bound,
unserved demand. Không được tuyên bố tiết kiệm dựa trên tập arrived bị chọn lọc. Nếu transit có
passenger records thì dùng một quy tắc hạch toán nhất quán, không cộng trùng với occupancy xe.

`departDelay` và `timeLoss` là chẩn đoán, không phải **primary evaluator** cạnh tranh với `C`. Mốc tham chiếu cần giữ cố định theo route, speed assumptions
và scheduled stops. Không thay mốc theo tuyến mà policy tự chọn; v1 chưa nghiên cứu induced demand.

Lý do: chi phí bao phủ cả queue trước khi chèn và xe ngoài lane của agent; agent không được lợi
nhờ đẩy nghẽn khỏi vùng đo. Trade-off là credit assignment của team reward khó hơn; đo bằng ablation
với local reward, không tự thêm một tổ hợp queue/speed/priority weights để che kết quả không tốt.

Guardrails bắt buộc: legality/clearance thực thi ở action layer; phục vụ cùng demand; báo person-delay,
phân vị cao và tiếp cận thiết yếu theo nhóm bên cạnh VND. Không gắn nhãn portfolio được khuyến nghị
nếu vi phạm tiêu chí nhóm đã chốt trước test; thiếu mẫu phải báo chưa đánh giá. Không tự đặt ngưỡng
phúc lợi xã hội từ placeholder cấu hình. Các kênh reliability/cargo/emissions/schedule chưa có nguồn
không được bật mặc định. Safety không được đổi lấy monetary reward.

## Kiểm toán implementation và lập luận nền (2026-09-17)

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
C_time(x, pi, s, k) = sum_v n_v * w_OD(v) * (T_v(x, pi, s, k) - T0_v) / 3600
```

`T_v` tính intended departure → arrival; `T0_v` cố định giữa các phương án.
Giữ route, speedFactor và scheduled stops nhất quán trong pilot. Ít timeLoss không chứng minh
hành trình ngắn hơn. Chưa nghiên cứu induced demand hoặc policy tự thay routing assumptions.

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

Protocol pilot: shared policy điều kiện hóa theo mask, freeze checkpoint trước khi đo `F`.
Không train lại riêng từng mask trong protocol đã chốt. Không so model
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

## 8. Đề xuất nghiên cứu mở rộng: lịch hoạt động, rủi ro và mức phục vụ

Cập nhật 2026-09-20 theo yêu cầu nghiên cứu reward sâu hơn. **Đây là đề xuất tổng hợp của dự án,
chưa phải phương pháp mới đã được công bố, chưa hiệu chỉnh cho map, chưa tích hợp callback hoặc
chứng minh tốt hơn baseline.** Giữ công thức phần đầu làm R0; không thay ngầm cấu hình runtime.
Phần này sở hữu thiết kế R1, không tạo roadmap khác với SYSTEM_DELIVERY_PLAN.

### 8.1 Căn cứ và khoảng trống nghiên cứu

| Nguồn đã đọc | Điều dùng được | Điều không được suy ra |
|---|---|---|
| [Fosgerau & Karlström, The value of reliability, 2010](https://mpra.ub.uni-muenchen.de/42274/5/MPRA_paper_42274.pdf), §2–3 | Liên hệ thời gian hành trình, giờ mong muốn đến và biến động thời gian | Hệ số định giá của Việt Nam hoặc tính đúng của mọi phân phối |
| [Small, Valuation of travel time, 2012](https://sites.socsci.uci.edu/~ksmall/VOT%20review.pdf), §2.4 | Định giá thời gian khác theo bối cảnh; lịch và reliability có thể phản ánh phần thiệt hại trùng nhau | Thu nhập tự động là VOT; mọi khoản phạt là chi phí xã hội |
| [Ng, Harada & Russell, 1999](https://people.eecs.berkeley.edu/~pabbeel/cs287-fa09/readings/NgHaradaRussell-shaping-ICML1999.pdf), theorem về shaping | Bổ sung hiệu thế có dạng gamma*Phi(next)-Phi(current) | Bảo đảm hội tụ cho PPO nhiều agent, quan sát thiếu hoặc potential thay đổi tùy ý |
| [Achiam et al., CPO, 2017](https://proceedings.mlr.press/v70/achiam17a/achiam17a.pdf), §4–5 | Tách mục tiêu và giới hạn chi phí trong tối ưu có ràng buộc | Penalty hoặc PPO-Lagrangian tự bảo đảm an toàn từng hành động |
| [Rockafellar & Uryasev, 2000](https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf), hàm F_alpha | Công thức tối ưu CVaR qua ngưỡng eta và phần vượt ngưỡng | Một vài seed đủ để ước lượng đuôi phân phối đáng tin |
| [Prashanth, 2014, CVaR-constrained MDPs](https://arxiv.org/pdf/1405.2690), §2–5 | Học policy với ước lượng rủi ro và cập nhật biến đối ngẫu | Tự chuyển định lý trong bài sang SUMO/PPO hiện tại |
| [Wei et al., PressLight, KDD 2019](https://faculty.ist.psu.edu/jessieli/Publications/2019-KDD-presslight.pdf) | Đối chứng điều khiển dựa trên chênh lệch dòng/áp lực giữa các hướng | Throughput cao đồng nghĩa công bằng, đúng giờ hoặc lợi ích tiền cao trong mọi trường hợp |

Câu hỏi nghiên cứu: **với cùng demand hành vi và ngân sách tính toán, thêm lịch hoạt động cùng
ràng buộc đuôi chậm trễ có giảm thiệt hại và bảo vệ các nhóm chịu thiệt so với R0 hay không;
shaping có giảm số mẫu học mà không làm thay đổi bộ đánh giá không?**
Các thành phần đã có trong literature. Đóng góp cần chứng minh nằm ở cách hạch toán/ghép nối và
kiểm định trên map, không ở việc đặt tên mới cho tổng các công thức.

### 8.2 Đơn vị hạch toán và điều kiện thí nghiệm

Dùng person-leg e cho thời gian người; vehicle v cho vận hành xe; activity j cho lịch đến;
shipment k cho thiệt hại hàng hóa riêng biệt. Mỗi bản ghi có ID ổn định, nguồn/đích, thời điểm,
đơn vị và evidence. Không dùng một hệ số ưu tiên chung cho nhãn ambulance/bus/truck.

R0 occupancy-weighted tương đương person-leg khi người trên xe có cùng khoảng thời gian và VOT.
R1 cần registry người/chặng để xử lý lên/xuống xe và đổi phương tiện. Mỗi người tại một thời điểm
chỉ thuộc một trạng thái thời gian: di chuyển, chờ phục vụ chuyến, hoạt động hoặc nghỉ. Không
tính đồng thời occupancy xe và passenger records cho cùng người.

Giữ cùng danh sách người, hoạt động, cửa sổ giờ, routing assumptions và ngẫu nhiên ngoại sinh giữa
các policy. Với tour liên kết, giờ phát sinh chặng sau có thể phụ thuộc giờ đến chặng trước:
dùng cùng QUY TẮC lịch cho mọi policy, không ép phát xe trước khi người/xe có mặt.
Phân biệt planned start và actual release. Chậm từ chặng trước không được biến thành hàng chờ
ảo của chặng sau rồi tính cùng khoảng thời gian hai lần. Phần mất cơ hội hoạt động xử lý ở lịch.
Nếu runner chưa hỗ trợ liên kết này, chỉ gọi thí nghiệm fixed-leg, chưa claim activity-aware đầy đủ.

Ngoài map: giữ endpoint thật và connector. Chỉ tính đoạn thời gian trong phạm vi được mô hình hóa,
kể cả hàng chờ đầu vào. Chỉ tính trễ hẹn tại đích ngoài map nếu có mô hình đoạn ngoài đã kiểm chứng
và dùng thống nhất. Nếu không, báo giới hạn phạm vi thay vì bịa giờ đến đích.

### 8.3 Chi phí R1: thời gian và lịch hoạt động

Đặt [x]_+=max(x,0). Các mốc thời gian dùng giây, đơn giá thời gian dùng VND/người-giờ.

\[
C_{\mathrm{trip}}(\omega)=
\sum_e \frac{w_e T_e}{3600}
+\sum_j\left\{
\frac{\beta_j[E_j-a_j]_+ + \ell_j[a_j-L_j]_+}{3600}
+m_j\,{\bf1}(a_j>D_j)
\right\}.
\]

- omega: một ngày/kịch bản và seed; T_e gồm thời gian đi/chờ phục vụ của person-leg, không gồm
  thời gian đang làm việc/ở nhà. Hàng chờ insertion là thời gian của người, kể cả xe chưa vào net.
- [E_j,L_j]: cửa sổ đến chấp nhận được cho person-activity j; a_j là giờ đến thực tế.
  Không có yêu cầu đúng giờ thì không tự dựng deadline.
- beta_j, ell_j: chi phí sớm/muộn còn lại ngoài VOT di chuyển; không mặc định ell>beta nếu chưa có
  bằng chứng. Mỗi hoạt động gắn đúng người, nên không nhân occupancy thêm lần nữa.
- D_j>=L_j: hạn mất cơ hội; m_j chỉ bật nếu có thiệt hại tăng thêm thực sự tránh được.
  Bỏ lỡ cuộc hẹn không tự bằng cả doanh thu dịch vụ. Tiền phạt chuyển từ bên này sang bên kia
  không tự là mất mát xã hội. Nếu m đã gồm trễ giờ thì tách phần trùng trước khi cộng.
- Sau D, công thức trên giả định thiệt hại trễ tuyến tính còn tiếp tục ngoài khoản mất cơ hội.
  Nếu hoạt động thực sự bị hủy, phải dùng loss curve và trạng thái hủy riêng; không kéo dài
  tuyến tính vô hạn hoặc cho hủy làm chuyến biến mất. Core pilot chưa cho policy tự hủy nhu cầu.

R1 core dùng time + schedule, chưa cần missed-activity fee. Có thể thêm
C_resource (năng lượng/hao mòn) và C_external (phát thải), hoặc C_cargo theo shipment,
nhưng chỉ khi có nguồn, cùng năm giá và bảng loại trùng. Các kênh này là mở rộng có gate,
không các số 0 được gọi là đã bao phủ toàn bộ thiệt hại.

Reliability trong R1 thể hiện qua phân phối đến sớm/muộn và kiểm tra rủi ro ở §8.4.
Không cộng mặc định một khoản w_sigma*std(T) bên cạnh schedule loss.
Điều này không chứng minh đã bao phủ mọi sở thích tránh bất định; nếu cần khoản riêng,
phải ước lượng phần dư và kiểm định khả năng phân biệt tham số.

**Tính chi phí từng bước:** đặt C_acc(t) là thời gian đã phát sinh + trễ hẹn đã tích lũy
+ sự kiện đã ghi nhận. Với hoạt động chưa đến và đã qua L_j, tích lũy
ell_j*[min(t,a_j)-L_j]_+/3600 (a_j=+infinity khi chưa đến).
Chi phí đến sớm chỉ ghi một lần lúc đến; khoản m chỉ ghi một lần khi vượt D mà chưa đến.
Trạng thái cuối chuyến phải dừng tích lũy. Không chờ tới arrival mới tính toàn bộ lateness,
vì policy có thể trì hoãn arrival để né khoản phạt trong cửa sổ quan sát.

Mỗi outcome có một harm_id/ledger owner. Đến sớm rồi chờ mở cửa cần chọn một cách hạch toán:
chi phí schedule early đã bao gồm việc chờ, hoặc tách phần chờ vào time và chỉ giữ residual
schedule discomfort. Không tính cả hai toàn phần. Lịch hoạt động liên tiếp có thể chịu
nhiều thiệt hại khác nhau, nhưng cùng khoản mất thu nhập không được gán cho nhiều activity.

### 8.4 Công bằng, đuôi chậm trễ và phục vụ nhu cầu

Tối ưu chi phí kỳ vọng **với ràng buộc**, không quy mọi tiêu chí thành VND:

\[
\min_\pi \mathbb E_\omega[C_{\mathrm{trip}}^\pi(\omega)]
\quad\text{s.t.}\quad
\mathrm{CVaR}_{\alpha_g}(Z_g^\pi)\le b_g,\quad
\mathbb E[Y_h^\pi]\le d_h,\quad a_t\in\mathcal A_{\mathrm{safe}}(s_t).
\]

Z_g là số giây trễ của một person-leg/hoạt động dự định trong nhóm g. Chọn rõ loại:
max(0,T_e-T0_e) cho excess travel, hoặc max(0,a_j-L_j) cho trễ hoạt động.
T0 cố định giữa các phương án; không dùng VOT làm trọng số công bằng.
g có thể là khu vực, hướng qua biên, transit, tiếp cận trường/bệnh viện.
Không tự suy nhóm thu nhập từ địa chỉ. Nhóm giao nhau được phép trong constraints,
không làm thời gian đó được cộng nhiều lần vào chi phí tiền.

Phân phối Z_g được xác định bằng: chọn scenario với trọng số đã freeze, rồi chọn đều trong
roster người-chặng/hoạt động dự định của nhóm trong scenario đó. Đây là **trọng số theo scenario**,
không tự đồng nghĩa chọn đều mọi người trên toàn bộ các ngày. Nếu muốn person-weighted toàn bộ
thì đổi trọng số scenario theo N_g từ trước, dùng cùng quy tắc ở train/eval/QUBO.
Roster không phụ thuộc số arrived. N_g=0 là not-applicable, không thay CVaR bằng 0.

\[
\mathrm{CVaR}_{\alpha}(Z)=
\min_\eta\left[\eta+\frac{\mathbb E[(Z-\eta)_+]}{1-\alpha}\right].
\]

Công thức hinge xử lý được phân phối rời rạc. Không lấy đơn giản mean(Z>=quantile) khi có ties.
Chọn alpha và ngưỡng trước test theo độ phủ dữ liệu/mức dịch vụ; không tự tuyên bố
alpha=0.95 là tiêu chuẩn. Ít mẫu đuôi thì báo chưa đủ bằng chứng, thêm seeds/ngày.

Y_h có thể là person-mean delay hoặc tỷ lệ trễ hẹn theo nhóm. Bổ sung giới hạn
“không xấu hơn baseline quá epsilon” và giới hạn tuyệt đối khi có căn cứ.
Ngưỡng tương đối freeze từ tập development với uncertainty, không tune theo test.
Baseline tệ không tự là mức phục vụ chấp nhận được.
Không tồn tại bộ tham số thỏa constraints thì báo infeasible, không lén nới ngưỡng.

An toàn xung đột pha/clearance/minimum-green do action shield kiểm soát từng bước.
Giới hạn kỳ vọng/CVaR không bảo đảm không ai bị chờ lâu, nên cần theo dõi starvation,
hàng chờ và kiểm tra stress riêng. Không hứa maximum wait tuyệt đối nếu demand vượt capacity.

Unroutable, teleport, bị loại và unfinished đều ở ledger. Chạy drain-out với giới hạn chung.
Nếu còn chuyến dở: cost và tail-delay đã tích lũy là lower bound; không xác nhận feasible
hoặc báo tiết kiệm hoàn chỉnh từ chúng. Gate phục vụ so sánh mọi intended demand.
Policy không được tự kết thúc episode để né chi phí. Truncation do rollout không là terminal.

### 8.5 Reward mở rộng R1 và tín hiệu học

Với episode hoàn chỉnh có N bước, S>0 cố định, đề xuất:

\[
r_t^{R1}=
-\frac{C_{\mathrm{acc}}(t+1)-C_{\mathrm{acc}}(t)}{S}
-\mathbf1_{t=N-1}\,P(\omega)
+\kappa\{\gamma\Phi(\xi_{t+1})-\Phi(\xi_t)\},
\]
\[
P(\omega)=
\sum_g\lambda_g\frac{H_g(\omega;\eta_g)-b_g}{u_g}
+\sum_h\nu_h\frac{Y_h(\omega)-d_h}{v_h},
\qquad
H_g=\eta_g+\frac{\sum_{e\in g}(z_e-\eta_g)_+}{(1-\alpha_g)N_g}.
\]

H_g ước lượng theo roster đủ và eta cố định trong batch; E[H_g] là surrogate CVaR.
u_g,v_h>0 là thang đơn vị freeze, không fit lại theo policy; lambda,nu>=0 là biến đối ngẫu,
**không phải giá tiền của con người**. P có thể âm khi dư mức phục vụ, đúng dạng Lagrangian.
Không clip P về phần dương tùy ý rồi vẫn tuyên bố cùng bài toán.

Policy giảm chi phí Lagrangian, eta cập nhật để giảm surrogate CVaR,
lambda <- max(0,lambda + lr*(mean(H)-b)/u), tương tự nu.
Freeze eta/lambda/nu/kappa trong một batch rollout. Cập nhật chậm, log dao động và residual.
Không chỉ thêm biểu thức vào callback PPO rồi gọi đó là constrained optimizer đã hoàn tất.
Terminal signal thưa là trade-off thật; dùng cost critics/advantages theo constraint để giảm
variance. Chưa tuyên bố hội tụ hoặc bảo đảm feasibility của neural policy.

**Đồng nhất với evaluator:** pilot dùng gamma=1 cho episode hữu hạn đã hoàn tất, Phi(terminal)=0,
Phi đầu không phụ thuộc action, kappa cố định. Khi đó tổng reward =
-C_trip/S - P - kappa*Phi(initial), giả sử C_acc(initial)=0.
Ở đây t là chỉ số quyết định; thời gian vật lý của ledger vẫn dùng giây. Nếu có warm-up,
freeze ledger đầu đợt và dùng chênh lệch C_final-C_initial nhất quán giữa reward/evaluator;
giữ tuổi hàng chờ và trạng thái lịch, không reset chúng để xóa chi phí hoặc đếm lại sự kiện.
Đây là đẳng thức kế toán với lambda/eta cố định, không chứng minh PPO tìm được nghiệm.
Nếu gamma<1, chỉ shaping telescope theo discount; chi phí bị ưu tiên theo thời điểm nên
không còn bằng cost không discount. Phải ghi là ablation khác, không gọi tương đương.
Rollout bị cắt cần bootstrap tiếp, không đặt Phi=0 như episode đã hoàn thành.

**Potential hỗ trợ phối hợp:** thử Phi=-sum_m min(p_m^2,p_max^2),
p_m=q_in(m)/K_in(m)-q_out(m)/K_out(m), K>0 theo movement mapping.
q là lượng người chờ/ước lượng, K là sức chứa quy đổi cùng đơn vị và mode. Mapping phải tránh
tùy ý đếm một queue nhiều lần. p_max và kappa freeze trên development.
Đây là heuristic bounded dùng ý tưởng pressure, **không phải reward PressLight nguyên bản**
và không mang theo định lý throughput. Phi có thể phản tác dụng với function approximation:
phải có ablation kappa=0. Queue/spillback không được cộng thêm thành tiền trong C_trip.

xi là thông tin phù hợp sensor mode (observation history/belief nếu thiếu quan sát);
không dùng exact hidden counts làm input policy camera. Ground truth được dùng cho
training reward/evaluation riêng, nhưng actor không nhận reward/cost/lambda hay hidden ledger
qua recurrent input trong thí nghiệm camera. Critic đặc quyền nếu dùng phải khai báo riêng.

Shared reward có vấn đề credit assignment. Cost critics và shaping là hướng thử trước.
Không gọi chênh lệch local queue là tác động nhân quả của một agent. Difference reward
đúng cần counterfactual cùng state/demand với action thay thế, tốn thêm mô phỏng và ngoài core.
Nhiều bản sao reward cho nhiều agent vẫn chỉ ứng với một ledger/environment.

### 8.6 Liên kết QUBO và kiểm định danh mục

R0 và R1 đều dùng cùng paired demand và shared checkpoint theo protocol pilot.
Với R1, thay cost đầu vào F bằng kỳ vọng C_trip đã có lịch đại diện để quy đổi năm.
Giữ B_i=F(0)-F(i), I_ij=F(i)+F(j)-F(i,j)-F(0), capex/opex/discount theo §4.
Dùng cost thô và constraints, **không dùng tổng r_R1, P, potential hoặc lambda làm VND**.

CVaR không có tính cộng như kỳ vọng và không tự là đa thức bậc hai của mask.
Không cộng CVaR của từng OD rồi gọi là CVaR của toàn mạng. Không đưa tail penalty vào hệ số
map_qubo hiện tại rồi nói solver đã bảo đảm fairness.
QUBO cung cấp danh mục ứng viên; rerun trên held-out scenarios, kiểm tra mọi ràng buộc g/h
và phục vụ. Vi phạm thì loại/chưa khuyến nghị. Với pilot nhỏ, có thể kiểm tra thêm các danh mục
khả thi bằng liệt kê; chưa kiểm hết thì không claim tối ưu toàn cục dưới constraints.
Proxy rủi ro bậc hai là nghiên cứu riêng, cần kiểm tra sai số độc lập.

### 8.7 Dữ liệu tối thiểu và cách hiệu chỉnh

| Nhóm | Cần có | Nếu thiếu |
|---|---|---|
| Time | person/leg/vehicle IDs, occupancy theo chặng, planned/actual release, arrival, boundary scope | Chỉ R0 với assumption ghi rõ; không tự nhân bus=20 |
| Schedule | activity IDs, cửa sổ đến, lịch, beta/ell và source | Chỉ kịch bản minh họa/sensitivity; không claim calibrated R1 |
| Missed activity | deadline, hậu quả biên, harm_id, quy tắc hủy | Tắt riêng m, không suy từ doanh thu cơ sở |
| Fairness/risk | group roster, T0, scenario weights, alpha, ngưỡng, mẫu đuôi | Báo thiếu coverage; không gọi constraint đạt |
| Learning | S/u/v, eta/lambda/kappa, seed/split, terminal semantics, feature contract | Không train chính thức nếu chưa freeze và validate |
| Economics | price year, đơn vị, scope, bảng khoản trùng, financial calendar | Không quy đổi thành lợi ích đầu tư thật |

Time và schedule coefficients phải hiệu chỉnh chung hoặc có kiểm tra overlap.
Khảo sát lựa chọn/lịch thực tế mới có thể phân biệt sở thích thời gian; traffic counts riêng
không nhận dạng được beta/ell/m. Không lấy số hệ số nước ngoài rồi coi là dữ liệu địa phương.
Dùng same-VOT/person-time làm sensitivity công bằng, so với purpose-VOT có nguồn.
S/u/v là chuẩn hóa; beta/ell là assumptions kinh tế; b/d là quyết định mức phục vụ.
Ba loại tham số không được tune chung để tối đa lợi ích trên test.

### 8.8 Protocol kiểm chứng và phản ví dụ

Đối chứng: fixed-time, movement-aware rule/max-pressure nếu triển khai hợp lệ; local reward
legacy; R0; R0+schedule; R0+constraints; R1 không shaping; R1 có shaping.
Cùng kiến trúc, số mẫu, compute budget, seed splits, demand và safety. Mọi policy đều đánh giá
bằng C_trip đầy đủ khi dữ liệu cho phép, kèm pure person-time, không mỗi policy một thước đo.
Kiểm tra matched train budget và cost thời gian chạy; không chỉ final return.

Hypotheses có thể bác bỏ:
- Schedule giúp đúng giờ hơn ở cùng mức tổng thời gian hoặc có trade-off chấp nhận được.
- Constraints giảm tail harm/vi phạm nhóm, có thể tăng cost trung bình.
- Shaping tăng sample efficiency, không đổi ranking kế toán của trajectory hoàn chỉnh.
- R1 dẫn tới portfolio tốt hơn R0 sau rerun, không chỉ theo quadratic prediction.

Các tình huống bắt buộc:
1. Cùng travel time nhưng một activity trễ hẹn: R0 hòa, R1 phân biệt.
2. Tiết kiệm năm phút nhưng vẫn sớm hơn cửa sổ: có thể không tốt hơn; kiểm tra beta hợp lý.
3. Người cùng xe chia/ghép roster không đổi tổng time cost; người chưa đến không mất mẫu số.
4. Mean delay bằng nhau nhưng có một nhóm chịu tail lớn: CVaR phát hiện, không chỉ variance chung.
5. Đẩy xe ra hàng chờ trước cửa mạng, teleport, xóa route: không tạo savings hợp lệ.
6. Nghẽn chuyển sang nút bên cạnh/nhóm ít VOT: ledger toàn mạng và constraints cùng phát hiện.
7. Phi thay đổi dọc đường nhưng cùng initial/terminal: tổng shaping chỉ là hằng số; terminal
   chưa về 0 hoặc sai gamma phải làm test thất bại.
8. Kết quả QUBO cải thiện mean nhưng vi phạm nhóm: không được trình bày như phương án được duyệt.
9. Sensor occlusion tăng, future/deadline truth không lọt vào actor qua reward history.
10. Tour chặng trước đến trễ: chặng sau không phát sớm, không đếm hai lần cùng thời gian người.

Báo paired differences và uncertainty theo seed/ngày (cluster bootstrap theo ngày, không coi
mọi xe cùng ngày độc lập); với CVaR báo số mẫu ở đuôi và khoảng bất định.
Ba seed test trong plan chỉ là smoke khởi đầu, chưa đủ tự động kết luận tail đáng tin.
Nếu không đủ tài nguyên, báo thiếu precision thay vì ghi một tỷ lệ cải thiện chắc chắn.
Một phần hoặc toàn bộ R1 có thể không thắng; khi đó giữ kết quả âm và ưu tiên phương án đơn giản.

Script scripts/research/check_reward_design.py kiểm tra số học với dữ liệu giả tự khai báo:
không là evaluator SUMO, không chứng minh khả năng học, calibration hoặc hiệu quả trên map.
