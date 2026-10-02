# Dataset nhu cầu đi lại cho ROI hiện tại

## Mô hình hành vi bắt buộc (cập nhật 2026-09-20)

Đơn vị sinh nhu cầu là người/hộ và hoạt động kinh tế; xe là tài nguyên thực hiện chuyến.
Code hiện tại vẫn chia volume/mix theo giờ đều, **chưa triển khai mô hình dưới đây**.
Project overlay còn lỗi tương thích schema (A1 trong báo cáo audit).

1. Sinh dân số/hộ tổng hợp, home/work/school, tuổi/việc làm và quyền sử dụng xe từ nguồn
   hoặc assumption có mẫu số. Không suy số cư dân trực tiếp từ mọi polygon.
2. Chọn tham gia hoạt động có điều kiện: ví dụ P(đi làm hôm nay | nhóm người, loại ngày).
   X% phải nói rõ là phần trăm của người, hộ, chuyến hay xe.
3. Chọn nơi đến theo chức năng, capacity, khoảng cách và ràng buộc. Home/work/school thường xuyên
   giữ nhất quán giữa ngày; gravity chỉ là một thành phần, không thay lịch hoạt động.
4. Chọn giờ cần đến và thời lượng hoạt động; suy giờ đi từ thời gian di chuyển dự kiến và buffer.
   Kiểm tra tính khả thi của toàn lịch, không lấy giờ đi/về độc lập.
5. Chọn mode theo quyền dùng xe và lịch; đi chung/đưa đón nối các người vào cùng chuyến xe.
   Không sinh một xe buýt cho mỗi người chọn transit.
6. Nối tour/leg: nhà → trường → nơi làm → mua sắm → nhà; bảo toàn vị trí người và xe.
   Có xe rỗng/reposition và carry-over qua nửa đêm; không ép mọi chuyến về trước hết cửa sổ.
7. Freight dùng đội xe, đơn hàng, time windows; emergency dùng dispatch/sự kiện riêng.
   Tách II/IE/EI/EE, external endpoint và boundary connector.

Các tỷ lệ theo loại nhà/giờ/loại xe là **kết quả tổng hợp hoặc ràng buộc hiệu chỉnh**,
không phải các phép chọn độc lập. Đối chiếu counts/OD/time/mode trên dữ liệu held-out,
báo uncertainty và sensitivity; chưa có nguồn thì ghi giả định, không bịa xác suất.
Registry dự kiến bổ sung person/household/vehicle/activity IDs (ID tổng hợp, không cần PII).
Không tự đổi schema runtime trong lượt audit tài liệu.

## Quyết định triển khai được chốt ngày 2026-09-19

Theo [kế hoạch toàn hệ thống](SYSTEM_DELIVERY_PLAN.md), tiếp tục tìm nguồn nhưng cho phép
nghiên cứu bằng demand synthetic minh bạch khi chưa có OD hiện hành đạt yêu cầu. Đây không phải
phê duyệt các giá trị số đang bỏ trống hoặc chứng nhận dataset đã hiệu chỉnh.

- Giữ nguyên net/overlay và hash; pilot 8 nút điều khiển không phải cắt mạng xuống 8 nút.
- Hoàn thiện parent-facility registry trước khi phân bổ capacity/trips. Neutral không tự sinh xe.
- Gate phải có hướng, mode và kiểm tra connectivity; không nâng nearest-edge thành cổng đã duyệt.
- Tách capacity, trip rate, lịch hoạt động, mode share, occupancy và source/evidence thành bảng.
- Giữ 11 mục đích, bin 15 phút và tour/leg liên kết; xử lý lượt về qua nửa đêm, xe rỗng và đưa đón.
- Bảo toàn II/IE/EI/EE; lưu riêng external endpoint và connector trong mô phỏng.
- Low/base/high thay đổi tham số được công bố, không tune tổng xe để tạo một mức tắc mong muốn.
- Mỗi nguồn số có locator, năm, đơn vị, phạm vi, license và phép chuyển đổi. WorldPop chỉ là prior.

Giao diện dataset cần cung cấp: scenario/day/seed, trip/tour/leg IDs, facility hoặc external-zone
nguồn/đích, gate, purpose, intended departure/desired arrival, mode, persons/occupancy, ordered route,
valuation ID, parameter version và evidence status. Đây là hợp đồng dự kiến, chưa là schema runtime
đã đăng ký. Validator phải kiểm tra uniqueness, referential integrity, tổng người/xe/chuyến và
requested/inserted/arrived/unroutable/unfinished; không loại chuyến lỗi khỏi mẫu số một cách im lặng.

Giữ train seeds 11/23/37, validation 53/71, test 101/131/167; tách thêm tập fit hệ số QUBO khỏi test.
Các split còn phải hold out ngày/profile/sự kiện, không chỉ khác seed. Không xáo trộn frame/trip
của cùng một ngày vào cả train và test.

Chế độ `research_synthetic` dự kiến cho phép thí nghiệm có giả định được ghi nhận nhưng vẫn bắt buộc
route/safety/accounting gates. Nó không biến `assumption_only` thành `available_reviewed`, không đổi
source-backed coverage và không vượt `assert_production_ready`. Các tham số volume/occupancy còn
thiếu phải được lập thành assumption register trước khi sinh tập chạy, không điền ngầm trong code.

Nghiệm thu M2: seed tái lập được, không nhân capacity theo mảnh polygon, đủ phân loại biên (zero có
lý do), route hợp lệ và mọi chuyến dự định có thể nối sang ledger đánh giá. Báo cáo nguồn phải phân
biệt thông tin quan sát, suy luận chuyển giao và giả định; chưa được kết luận lợi ích thực tế.

## Bằng chứng và thiết kế nền (2026-09-17)

Ngày kiểm chứng: 2026-09-17. Giữ nguyên net và overlay đang dùng; không thay bằng
ranh giới hành chính Quận 7. Đây là thiết kế có inventory chạy được, **chưa phải
dataset OD đã hiệu chỉnh và chưa phải route dataset hoàn chỉnh để train chính thức**.
SUMO sinh diễn biến giao thông từ nhu cầu đầu vào; SUMO không tự chứng minh nhu cầu đó đúng.

## 1. Giữ lại lập luận ban đầu của dự án

Thiết kế hiện hành giữ nguyên tắc từ spec ban đầu (spec cũ đã được thay thế):
mỗi chuyến phải bắt đầu từ nhu cầu của con người, dịch vụ hoặc cơ sở kinh tế.
Chuỗi là `chức năng nơi chốn → mục đích → OD → phương tiện → tuyến → điều khiển → tác động`.
Không thay mô hình này bằng xe ngẫu nhiên hoặc tỷ lệ xe chung cho cả map.
Config `configs/demand/current_roi_dataset.v1.json` giữ đủ 11 mục đích và giờ của
spec, đồng thời đánh dấu toàn bộ giờ là prior thiết kế cấp D, không phải thống kê.

| Mục đích | Sinh/thu hút chuyến và thời gian giả định của dự án |
|---|---|
| Đi làm | Nhà → nơi làm 06:30–08:30; nơi làm → nhà 16:30–18:30 |
| Đi học | Nhà → trường 06:30–07:30; trường → nhà 16:00–17:30 |
| Công nghiệp | Ca vào 05:30–07:30; ca ra 16:30–18:30; chưa suy ra lịch từng nhà máy |
| Logistics | Depot/cổng ngoài → nơi nhận 08:00–11:00 và 13:00–16:00; xe rỗng về là leg riêng |
| Khám bệnh | Có thể cả ngày, phân biệt nhân viên/khám ngoại trú/nội trú; không lấy phân bố đều |
| Cấp cứu | Dispatch quan sát được hoặc sự kiện thử nghiệm rõ ràng; không sinh theo diện tích bệnh viện |
| Chợ/mua sắm | 06:00–09:00 và 16:00–19:00; tách lượt đi và lượt về |
| Giải trí | 18:00–23:00; lượt về sau nửa đêm không bị cắt mất |
| Sự kiện | Chỉ có khi khai báo lịch, sức chứa và thời điểm vào/ra |
| Dịch vụ công | 08:00–11:00 và 13:30–16:00, tách nhân viên khỏi khách |

Các khung giờ là support, không phải mật độ đều. Sau này từng cơ sở có lịch riêng
sẽ ghi đè đúng dịch vụ, không ghi đè toàn bộ loại zone. Ví dụ [FV công bố](https://www.fvhospital.com/en/news/fvs-health-check-up-family-medicine-centre-now-open-from-7-am/)
trung tâm khám tổng quát/y học gia đình nhận khách từ 07:00 từ 01/05/2025.
Điều này hỗ trợ giờ khả thi của dịch vụ đó, không cho số bệnh nhân, peak đến hay giờ mọi khoa.

## 2. Kết quả inventory và dataset đã lấy

Lệnh đã chạy:

```powershell
uv run python scripts/data/prepare_demand_inventory.py --config configs/demand/current_roi_dataset.v1.json --worldpop-xyz-zip artifacts/research/20260917/vnm_ppp_2020_1km_ASCII_XYZ.zip --output artifacts/demand/20260917/inventory.json
uv run pytest tests/unit/data/test_demand_inventory.py -q
```

Overlay có 2.588 mảnh hình học, gom theo `source_element_id` thành **340 parent ứng viên**;
252 parent có nhiều mảnh. Parent chưa tương đương một cơ sở đã xác minh: campus gồm
nhiều OSM way vẫn có thể trùng chức năng. Không gán capacity cho từng mảnh rồi cộng lại.
1.234 mảnh neutral không tự phát sinh demand. Inventory giữ capacity, số chuyến và
cổng đã duyệt là null/rỗng; số dòng OD quan sát bằng 0. Khoảng cách tới edge gần nhất
không chứng minh đó là lối ra hợp pháp hay đúng chiều.

Đã tải [WorldPop Vietnam 2020 1km XYZ](https://hub.worldpop.org/geodata/summary?id=33829):
ước lượng người trên ô WGS84, 30 arc-second; nguồn công bố CC BY 4.0 và yêu cầu attribution,
đồng thời có lưu ý ODbL với sản phẩm dẫn xuất từ một số nguồn. Lưu attribution và kiểm tra
điều kiện khi phát hành dữ liệu dẫn xuất. Archive 4.684.717 byte có SHA256
`b0103420b8bdf3fc50db9f9e04cfec71c28be05c93b4c0cc56f787598389288e`.
Parser chọn 131 tâm ô nằm trong bbox chẩn đoán; tổng giá trị khoảng 890.458,27.
**Không gọi đây là dân số ROI**: chọn tâm ô không cắt phần ô theo ranh giới, bbox không
phải mặt nạ vùng phục vụ của mạng, và đây là mô hình năm 2020 chứ không phải kiểm đếm 2026.
Chỉ dùng để xem phân bố prior lịch sử; tuyệt đối không chia đều thành dân số mỗi building
hoặc nhân trực tiếp thành chuyến. Dữ liệu tải nằm trong `artifacts/research/20260917/`,
inventory ở `artifacts/demand/20260917/`; binary không commit.

[Travel source review](CURRENT_ROI_TRAVEL_SOURCE_REVIEW.md) còn ghi nhận tuyến xe buýt
38/139 của nhà khai thác, khảo sát JICA lịch sử và cổng dữ liệu giao thông thành phố.
Timetable là nguồn cung, capacity xe không phải occupancy, counts lịch sử không phải OD hiện tại.
Chưa tìm được bản tải OD building-to-building hiện hành có quyền sử dụng được xác minh;
không có nghĩa dataset ấy chắc chắn không tồn tại. Catalog nguồn ở
`data/catalog/current_roi_demand_sources.v1.csv`.

## 3. Sinh demand theo cơ sở: đề xuất thuật toán, chưa được hiệu chỉnh

1. **Entity resolution:** kiểm tra parent/campus, chức năng hỗn hợp, cửa vào/ra theo mode,
   cạnh có hướng và vị trí dừng. Giữ source ID và audit của người duyệt.
2. **Population/activity:** nhà cần residents/households; văn phòng cần jobs; trường cần
   enrollment và lịch; bệnh viện cần appointment/staff/visitors; cảng cần gate counts,
   shipments và ca. Diện tích chỉ là proxy thiếu capacity, không tự thành người.
3. **Production/attraction:** lập `P[i,p,t]` người-chuyến xuất phát và `A[j,p,t]` sức hút
   cho mục đích p/bin 15 phút. Tổng chuyến = exposure × trip rate × xác suất tham gia;
   cả ba phải có nguồn hoặc khoảng giả định. Không mặc định mọi resident đi làm/học mỗi ngày.
4. **OD:** prior `T[i,j,p,t] ∝ P[i,p,t] A[j,p,t] exp(-beta[p] * travel_cost[i,j])`
   chỉ trên cặp khả thi và đúng chức năng. Beta là tham số fit/sensitivity, không hằng số biết trước.
   Khi có marginals, dùng cân bằng hàng/cột và constraints counts; khi chưa có, kết quả vẫn synthetic.
   Không ép cân bằng riêng vùng nội bộ nếu có dòng xuyên biên.
5. **Tour/legs:** người đi làm có leg về liên kết; giờ về phụ thuộc hoạt động, không sinh hai
   OD độc lập gây nhân đôi người. School drop-off phải phân biệt học sinh, người đưa đón và
   xe; taxi empty reposition, truck empty return được ghi riêng. Xe bus theo lịch tuyến,
   hành khách chọn transit không biến thành một xe cho mỗi người.
6. **Mode/occupancy:** chọn mode theo OD/purpose/time đã có bằng chứng. Chuyển người-chuyến
   sang xe-chuyến bằng occupancy đúng mode; PCU chỉ là đơn vị chiếm dụng đường. Có đi bộ,
   transit và trip không dùng xe, không ép toàn bộ dân số lên mạng xe cơ giới.
7. **Time:** chuẩn hóa phân bố theo bin sao cho tổng đúng trip budget; học profile từ counts
   khi có. Với demo, khai báo uniform/triangular/mixture và low/base/high là lựa chọn thiết kế.
   Lấy departure = thời điểm hoạt động mong muốn − travel time dự kiến nếu mô hình theo arrival.
8. **Route/export:** lọc đường hợp pháp theo mode, hướng, connectivity, hạn chế tải và giờ;
   giữ origin/destination thực, gate, ordered edges, tour/leg IDs, purpose và source flags.
   Log requested/inserted/arrived/unroutable/teleported/unfinished, không im lặng bỏ chuyến thất bại.

Không ấn định baseline số xe khi chưa có trip rate/capacity/gates. Có thể chạy kịch bản
synthetic có tổng xe do người thiết kế chọn, nhưng phải ghi `reviewed_synthetic`, không `observed`.
Không chọn tổng demand chỉ để tạo ra mức tắc đường mong muốn rồi gọi đó là hiệu chỉnh.

## 4. Ngoài vào, trong ra và xuyên qua

| Class | Endpoint thật | Biểu diễn SUMO | Chú ý |
|---|---|---|---|
| II | Cơ sở trong → cơ sở trong | Cổng nguồn → cổng đích | Không bắt mọi chuyến ở lại ROI |
| IE | Cơ sở trong → external zone | Cổng cơ sở → exit connector | Exit không phải điểm đến thực |
| EI | External zone → cơ sở trong | Entry connector → cổng cơ sở | Giờ vào mạng không phải giờ rời nhà ngoài vùng |
| EE | External zone → external zone | Entry → exit | Đóng góp tắc đường dù không có building nội bộ |

Gate được duyệt trên đường cắt ranh giới với chiều đi và allowed modes, không lấy mọi
dead-end làm city gate. Tỷ lệ II/IE/EI/EE theo time/purpose/mode phải lấy từ cordon counts,
survey hoặc các kịch bản có khoảng nhạy cảm; không suy ra từ tỷ lệ số building.
Giữ external zone ID và in-ROI legs; một hành trình ra rồi vào lại có nhiều segment liên kết.
Đầu kỳ đã có xe trong mạng nên cần warm-up; cuối kỳ có unfinished/queue, không làm chúng biến
mất khỏi loss ledger. Không cộng lợi ích ngoài ROI khi không mô phỏng/đo được phần đó.

## 5. Kiểm định và liên kết RL/QUBO

Dataset grain tối thiểu: scenario/day/seed/tour/leg, purpose, origin/destination parent hoặc
external zone, boundary class, departure/desired arrival, mode, persons, gates, route,
parameter version, evidence grade. Bảng riêng cho nguồn, capacity, time profiles và counts.
Seed train 11/23/37, validation 53/71, test 101/131/167 chỉ chống trùng ngẫu nhiên; còn phải
hold out ngày/profile/sự kiện và bộ tham số để kiểm tra ngoài phân bố. Không tune vào test.

Check: uniqueness leg; referential integrity; bảo toàn người/xe/chuyến; balanced tours;
không trùng capacity mảnh; đủ bốn boundary class (class zero cần lý do, missing không phải zero);
sum bin bằng tổng ngày; route legal; failed-trip denominator; held-out directional counts,
travel-time distribution và occupancy. Dùng count errors theo bin/approach, không chỉ network sum.
Một tập counts không xác định duy nhất OD: kiểm tra nhiều OD phù hợp counts và báo uncertainty.

[SUMO randomTrips](https://eclipse.dev/sumo/docs/Tools/Trip.html) phù hợp smoke test có seed;
route không nối được có thể bị loại nên không coi số requested là inserted. Công cụ này không
cung cấp lý do đi lại. [Observation-route methods](https://eclipse.dev/sumo/docs/Demand/Routes_from_Observation_Points.html)
là phương án fit khi thật sự có counts, không thay thế nguồn counts.

RL và baseline chạy cùng demand/seed; QUBO lấy **chênh lệch** network cost giữa baseline,
single candidate và pair candidate trên các demand đó. Không cho phương án đầu tư thay demand
để thắng. Nếu nghiên cứu induced demand thì đó là scenario riêng. Annualization theo số ngày
đại diện có nguồn, không mặc định nhân 365. Quy tắc giá trị và anti-double-count nằm trong
[RL/QUBO objective rationale](RL_QUBO_OBJECTIVE_RATIONALE.md).

**Trạng thái bàn giao:** inventory và kiểm tra dữ liệu chạy được; 10 tests pass, Ruff sạch.
Population prior có provenance thực. Gate/capacity/OD volumes/occupancy chưa duyệt nên pipeline
không sinh tập trips mang nhãn calibrated và production gate tiếp tục đóng.
