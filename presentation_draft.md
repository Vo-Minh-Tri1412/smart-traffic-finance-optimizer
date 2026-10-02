### Slide 1: Giới thiệu

**Trên slide**

Một hệ thống mô phỏng để nghiên cứu cách vận hành đèn và chọn nơi nâng cấp.

![Hình dẫn nhập: cùng một mạng đường dẫn đến hai loại quyết định](Giay_to/presentation_assets/diagrams/slide01-two-decisions.png)

**Lời thuyết trình**

Nhóm em xin trình bày một hệ thống mô phỏng giao thông để nghiên cứu hai việc: vận hành đèn theo tình hình và chọn nút giao đáng nâng cấp khi ngân sách có hạn. Đây là một bài toán ra quyết định dựa trên mô phỏng, không phải lời khẳng định đã triển khai điều khiển ngoài đường.

### Slide 2: Vài nét về vấn đề hiện tại

**Trên slide**

**Khoảng 6 tỷ USD/năm**

Thiệt hại do ùn tắc tại TP.HCM, theo phát biểu của ĐBQH Nguyễn Văn Cảnh ngày 28/5/2025. [Nguồn: Pháp Luật TP.HCM](https://plo.vn/dai-bieu-nguyen-van-canh-tphcm-thiet-hai-khoang-6-ti-usdnam-do-un-tac-giao-thong-post852233.amp).

Phạm vi đề tài: điều khiển đèn và lựa chọn nơi nâng cấp.

![Con số bối cảnh và phạm vi nghiên cứu, không phải hiệu quả dự án](Giay_to/presentation_assets/diagrams/slide02-context-not-impact.png)

**Lời thuyết trình**

Theo tường thuật về phát biểu của đại biểu Nguyễn Văn Cảnh ngày 28/5/2025, thiệt hại do ùn tắc tại TP.HCM được nêu ở mức khoảng 6 tỷ USD mỗi năm. Con số này giúp thấy quy mô vấn đề, không phải khoản mà đề tài có thể thu hồi. Nhóm chỉ tập trung vào điều khiển đèn và lựa chọn nơi nâng cấp: một nút được ưu tiên có thể làm thay đổi cả các nút bên cạnh. Nguồn: https://plo.vn/dai-bieu-nguyen-van-canh-tphcm-thiet-hai-khoang-6-ti-usdnam-do-un-tac-giao-thong-post852233.amp

### Slide 3: Mô tả bài toán

**Trên slide**

- Vận hành đèn để giảm chi phí đi lại.
- Chọn nơi nâng cấp trong ngân sách.

**Công thức minh họa, chưa phải hàm thưởng đầy đủ.**

- f3.1. Hàm thưởng minh họa.

$$
r_t^{\text{minh họa}}=-\frac{A(t+\Delta t)-A(t)}{S}.
$$

![Hai câu hỏi vận hành và đầu tư dùng bộ đo chi phí chung](Giay_to/presentation_assets/diagrams/slide03-two-problems-one-metric.png)

**Lời thuyết trình**

Từ đó, nhóm đặt hai câu hỏi: điều khiển đèn ra sao để giảm chi phí đi lại, và đầu tư ở đâu khi tiền có hạn? Công thức trên chỉ minh họa ý tưởng: chi phí thời gian phát sinh thêm thì phần thưởng giảm. Nó chưa phải reward đầy đủ, vì còn lịch cần đến và mức phục vụ từng nhóm. Khi đánh giá đầu tư, nhóm dùng cùng bộ đo chi phí giao thông rồi trừ chi phí nâng cấp, vận hành.

### Slide 4: Bài toán chính: Tối ưu kép

**Trên slide**

![Quan hệ giữa hai cấp quyết định: QUBO chọn nút nâng cấp, RL điều khiển đèn, cùng kiểm tra bằng SUMO](Giay_to/presentation_assets/diagrams/slide04-rl-qubo-relationship.png)

**Lời thuyết trình**

RL điều khiển đèn qua chuỗi quan sát, hành động và kết quả. Mở thêm một hướng có thể giải tỏa xe trước mắt nhưng dồn xe đến nút sau, nên phải đánh giá cả chuỗi và so với đèn cố định. QUBO giải cấp quyết định khác: chọn nút nâng cấp trong ngân sách, có xét hai nút hỗ trợ nhau hoặc làm lợi ích bị tính trùng. Hai phần dùng cùng bộ đo chi phí giao thông; chưa có phương pháp nào được coi là tốt hơn trước khi chạy đối chứng.

### Slide 5: Môi trường mô phỏng giao thông

**Trên slide**

**OSM:** dữ liệu đường sá và địa điểm.

**SUMO:** mô phỏng phương tiện và đèn.

**UE:** hiển thị diễn biến bằng cảnh 3D.

![Sơ đồ hệ thống bước 1: OSM, SUMO và Unreal Engine](Giay_to/presentation_assets/diagrams/system-stage-01-environment.png)

**Lời thuyết trình**

Nhóm giữ phạm vi bản đồ Quận 7 đang nghiên cứu. OSM cung cấp mạng đường và địa điểm; SUMO mô phỏng xe, đèn và các lần chạy đối chứng. Unreal Engine là lớp hình ảnh 3D để xem lại diễn biến và hướng tới dữ liệu camera. Bridge UE đã đọc được một phần map và trace, nhưng lớp hiển thị tín hiệu và streaming chưa hoàn chỉnh. Để mô phỏng có ý nghĩa, bước tiếp theo là tạo những chuyến đi có căn cứ.

### Slide 6: Nhu cầu đi lại: Xe trên đường đến từ đâu?

**Trên slide**

Một người, một hành trình trong ngày.

Rời nhà, đưa con đi học, đi làm, ghé mua đồ rồi về nhà.

Giờ đi và phương tiện cần có căn cứ. Mô hình còn xét chuyến vào, ra và xuyên khu vực.

![Sơ đồ hệ thống bước 2: thêm nhu cầu đi lại](Giay_to/presentation_assets/diagrams/system-stage-02-demand.png)

**Lời thuyết trình**

Demand cần xuất phát từ người và lịch hoạt động, không phải một tỷ lệ xe gán cho tòa nhà. Từ giờ cần đến trường hay nơi làm việc, thời gian di chuyển và phương tiện sẵn có, nhóm mới suy ra giờ rời nhà và nối các chặng tới lúc trở về. Mô hình còn cần chuyến vào, ra và đi xuyên khu vực. Code hiện tại chưa có chuỗi hành vi đủ chi tiết hoặc OD đã hiệu chỉnh; mọi tỷ lệ phải có nguồn hoặc nhãn giả định.

### Slide 7: Công nghệ triển khai bộ điều khiển RL

**Trên slide**

SUMO + `sumo-rl`: môi trường Python. `PettingZoo` / `SuperSuit`: nhiều nút giao.

`Stable-Baselines3`: PPO; `SB3-Contrib`: RecurrentPPO.

Thiết kế: lệnh đèn qua kiểm tra an toàn. **Chưa kiểm chứng chính sách trên đúng map.**

![Sơ đồ hệ thống bước 3: thêm RL, lớp an toàn và bộ đo](Giay_to/presentation_assets/diagrams/system-stage-03-control.png)

**Lời thuyết trình**

Phần RL được triển khai bằng Python. SUMO chạy giao thông, `sumo-rl` tạo môi trường; `PettingZoo` và `SuperSuit` hỗ trợ nhiều nút; `Stable-Baselines3` và `SB3-Contrib` cung cấp PPO, RecurrentPPO. Trong vòng chạy đích, hành động phải qua kiểm tra an toàn, còn kết quả được đo từ chuyến đi chứ không từ điểm huấn luyện. Geometry và nhiễu trên sơ đồ là đường quan sát đích; hiện RL vẫn dùng quan sát mặc định của `sumo-rl`. Chưa có lần đánh giá độc lập trên map với demand hành vi và bộ đo đầy đủ.

### Slide 8: Giới hạn quan sát do che khuất

**Trên slide**

Xe buýt có thể che xe nhỏ phía sau.

Xe bị che vẫn phát sinh chi phí, nhưng vị trí thật của chúng không được cấp cho bộ chọn hành động.

Lịch sử quan sát chỉ hỗ trợ ước lượng.

![Xe buýt che xe nhỏ: camera quan sát thiếu nhưng bộ đo vẫn tính cả hai](Giay_to/presentation_assets/diagrams/slide08-occlusion.png)

**Lời thuyết trình**

Trong thiết kế đích, RL phải ra quyết định từ thông tin cảm biến có giới hạn. Xe buýt có thể che xe nhỏ suốt nhiều khung liên tiếp, nên xóa ngẫu nhiên vài xe không diễn tả đúng tình huống. Nhóm đã có mô hình hình học để thử che khuất ngoại tuyến; mô hình nhiễu theo camera và thời gian cùng đường nối vào RL còn phải xây. Vị trí thật của xe khuất chỉ dùng để đánh giá, không được lén cấp cho RL.

### Slide 9: Quan sát cho RL và nhánh CV mở rộng

**Trên slide**

Nhánh chính cần xây: SUMO → che khuất hình học → nhiễu cảm biến → quan sát ước lượng cho RL.

Nhánh mở rộng: SUMO → UE dựng ảnh → CV nhận biết xe → cùng giao diện quan sát RL.

**Trạng thái thật SUMO chỉ là đối chứng oracle; reward lấy từ bộ đo riêng. Chưa có vòng RL dùng geometry + nhiễu hay CV khép kín.**

![Geometry và nhiễu tạo quan sát chính; CV từ ảnh UE là nguồn mở rộng](Giay_to/presentation_assets/diagrams/system-stage-04-camera.png)

**Lời thuyết trình**

Trang trước cho thấy xe bị che. Trên sơ đồ, đường quan sát đích cho RL đi từ trace SUMO qua hình học che khuất, mô hình nhiễu rồi thành ước lượng theo làn. Hiện mới có mã thử hình học ngoại tuyến, còn nhiễu có cấu trúc và bộ nối RL chưa hoàn chỉnh. Đường lấy trạng thái thật là oracle để đối chứng, không phải thông tin chính sách được dùng trong thử nghiệm cảm biến. UE và CV là nhánh ảnh mở rộng, cùng đưa vào giao diện quan sát ấy.

### Slide 10: Công nghệ triển khai lựa chọn đầu tư QUBO

**Trên slide**

Python đọc hồ sơ kinh tế theo tuyến đi và tác động từng nút/cặp nút.

`map_qubo.py`: kiểm tra nguồn, đơn vị và kỳ chi phí; dựng hệ số QUBO cùng ràng buộc ngân sách.

`solve_map_qubo.py`: giải chính xác bài toán nhỏ, lưu cấu hình và nghiệm để đối chiếu. Danh mục chọn phải chạy lại trong SUMO.

**Chưa dùng thư viện hay máy tính lượng tử; chưa có hệ số tác động đo đủ trên map.**

![Sơ đồ hệ thống bước 5: bộ đo và chi phí tạo QUBO, danh mục quay lại SUMO](Giay_to/presentation_assets/diagrams/system-stage-05-investment.png)

**Lời thuyết trình**

QUBO hiện dùng Python thuần. `map_qubo.py` kiểm tra hồ sơ kinh tế theo tuyến, đơn vị và kỳ chi phí để dựng hệ số cùng ngân sách. `solve_map_qubo.py` giải chính xác bài toán nhỏ và lưu nghiệm. Nhóm chưa dùng máy tính lượng tử. Phần còn thiếu là tác động từng nút và từng cặp đo trên đúng map, nên chưa thể khuyến nghị đầu tư.

### Slide 11: QUBO được dùng trên map như thế nào?

**Trên slide**

Chạy phương án gốc, từng nút và từng cặp trên cùng kịch bản.

Lấy chênh lệch chi phí giao thông để tạo lợi ích riêng và tương tác; giữ cả tác động bất lợi.

Giải danh mục trong ngân sách → chạy lại trên kịch bản mới → so dự đoán với kết quả đo.

![Cùng map và nhu cầu: so phương án gốc, từng nút, từng cặp rồi chạy lại danh mục](Giay_to/presentation_assets/diagrams/qubo-evidence-on-map.png)

**Lời thuyết trình**

Cùng một nhu cầu đi lại, nhóm chạy phương án gốc, nâng cấp riêng từng nút rồi từng cặp. Chênh lệch chi phí cho lợi ích riêng và tương tác, kể cả tác động xấu. QUBO chọn danh mục trong ngân sách, nhưng đó vẫn là dự đoán. Nhóm phải chạy lại danh mục trên kịch bản khác để đo chi phí, chuyến dở và mức phục vụ.

### Slide 12: Giới hạn thực tế của tối ưu kép

**Trên slide**

Trong thiết kế, danh mục đầu tư quyết định những nút được phép dùng điều khiển RL.

Hệ số theo từng nút và từng cặp chỉ là mô hình gần đúng của cả mạng.

Cần tách ba câu hỏi: giải mô hình có tốt không, dự đoán có đúng không, và kết quả có ổn định khi đổi giả định không?

![Giới hạn mô hình QUBO và ba phép kiểm tra trước khi khuyến nghị](Giay_to/presentation_assets/diagrams/slide11-optimization-limits.png)

**Lời thuyết trình**

QUBO chỉ mô tả lợi ích từng nút và từng cặp, trong khi cả mạng có thể phức tạp hơn. Giải đúng mô hình chưa bảo đảm dự đoán đúng SUMO. Vì vậy nhóm kiểm tra nghiệm ở bài toán nhỏ, chạy lại danh mục, rồi đổi nhu cầu, chi phí và chất lượng quan sát để xem lựa chọn có đảo chiều không.

### Slide 13: Kế hoạch thử nghiệm có đối chứng

**Trên slide**

Giữ nguyên map; chọn trước một nhóm nhỏ nút đủ điều kiện.

Cùng nhu cầu, cùng quy tắc an toàn: so RL với đèn cố định và điều khiển theo quy tắc.

Cùng bộ đo: so danh mục QUBO với chọn lần lượt và kiểm tra đầy đủ trên bài toán nhỏ.

![Thiết kế thử nghiệm RL và QUBO trên cùng điều kiện](Giay_to/presentation_assets/diagrams/slide12-controlled-experiment.png)

**Lời thuyết trình**

Nhóm chốt map, nhu cầu và các nút ứng viên trước. RL được so với đèn cố định và điều khiển theo quy tắc trên cùng kịch bản kiểm tra, không học lại lúc chấm. QUBO được so với cách chọn lần lượt; bài toán nhỏ còn có thể xét hết tổ hợp. Mọi phương án dùng chung bộ đo, báo cả chuyến dở, mức phục vụ và độ dao động.

### Slide 14: Công nghệ và dữ liệu cho CV từ ảnh

**Trên slide**

Nhánh quan sát hình học có `geometry_camera` để thử che khuất ngoại tuyến; đây là nền của thử nghiệm quan sát có nhiễu, không phải CV.

Nhánh CV mở rộng mới có mẫu cấu trúc dữ liệu YOLO. Cần UE xuất khung hình và nhãn cùng mã lần chạy, thời điểm và camera.

`Ultralytics` và `OpenCV` được liệt kê cho nhánh CV, **chưa có bộ ảnh hoặc mô hình đã huấn luyện**. Kết quả CV phải đi vào cùng giao diện quan sát RL; vòng này chưa khép kín.

![Các bước kỹ thuật từ trace SUMO đến quan sát camera cho RL](Giay_to/presentation_assets/diagrams/slide14-cv-implementation.png)

**Lời thuyết trình**

Geometry đã có phép thử ngoại tuyến để tính xe bị che; đó là một phần của đường quan sát chính, không phải CV. Với CV mở rộng, UE cần xuất ảnh và nhãn đồng bộ với trace SUMO. OpenCV và Ultralytics sẽ xử lý xe rồi chuyển sang đúng giao diện quan sát theo làn mà RL sử dụng. Hiện chưa có bộ ảnh hay mô hình đã huấn luyện, nên chưa khẳng định nhánh ảnh hoạt động. Trạng thái thật SUMO chỉ dùng để chấm.

### Slide 15: Kiểm chứng camera bằng kết quả giao thông

**Trên slide**

Thử riêng che khuất, ánh sáng, mất khung và độ trễ; không trộn mọi lỗi thành một xác suất ngẫu nhiên.

Đo ba tầng: nhận biết xe → hàng chờ ước lượng → chi phí đi lại và mức phục vụ.

Điểm nhận biết tốt hơn chưa bảo đảm điều khiển tốt hơn.

![Các tầng kiểm tra từ ảnh camera đến chi phí giao thông](Giay_to/presentation_assets/diagrams/slide14-camera-validation.png)

**Lời thuyết trình**

Camera có thể lỗi vì che khuất, ánh sáng, mất khung hoặc độ trễ. Nhóm đo theo chuỗi: nhận biết xe, ước lượng hàng chờ, rồi kết quả điều khiển trong SUMO. Điểm nhận biết cao hơn chưa chắc giảm chi phí đi lại; việc huấn luyện lại RL phải được thử riêng.

### Slide 16: Camera ảnh hưởng quyết định đầu tư ra sao?

**Trên slide**

Một gói nâng cấp gồm thiết bị, xử lý, lắp đặt và vận hành.

Lợi ích phải đo dưới đúng chất lượng quan sát của gói ấy; chi phí và lợi ích cùng kỳ đánh giá.

Đợt đầu QUBO chọn nút nhận gói cố định, chưa tối ưu đồng thời vị trí camera và phần cứng.

![Chi phí và lợi ích đo đúng cấu hình camera đi vào QUBO](Giay_to/presentation_assets/diagrams/slide15-camera-investment.png)

**Lời thuyết trình**

Gói camera phải tính thiết bị, xử lý, lắp đặt và vận hành. Lợi ích chỉ đo khi RL dùng đúng chất lượng ảnh và độ trễ của gói. Đợt đầu QUBO chọn các gói cố định theo nút; thiếu giá thực thì chỉ báo kịch bản giả định.

### Slide 17: Tổng kết hệ thống

**Trên slide**

Demand tạo hành trình có căn cứ.

RL dùng quan sát ước lượng qua che khuất hình học và nhiễu cảm biến; CV từ ảnh là nguồn thay thế tùy chọn.

QUBO chọn nơi nâng cấp từ lợi ích đo được và chi phí.

SUMO, UE và dashboard kết nối các phần, không thay vai trò của nhau.

![Sơ đồ hệ thống đầy đủ: nhu cầu, RL, QUBO và nhánh CV](Giay_to/presentation_assets/diagrams/system-overview-preview.png)

**Lời thuyết trình**

Demand tạo chuyến đi; geometry và nhiễu giới hạn thông tin RL được thấy; RL vận hành đèn. CV từ ảnh UE có thể thay nguồn quan sát về sau. QUBO chọn nơi đầu tư từ các lần chạy đối chứng; dashboard chỉ đọc đầu vào và kết quả. Các phần phải dùng cùng mã lần chạy, còn trạng thái thật SUMO và bộ đo chỉ phục vụ đánh giá, không bị đưa lén vào chính sách.

### Slide 18: Người dùng sẽ nhìn thấy gì?

**Trên slide**

Chọn kịch bản và xem nguồn dữ liệu, giả định còn thiếu.

Chạy/so sánh cách điều khiển hoặc nhập ngân sách để thử danh mục đầu tư.

Bản đồ, số chuyến dở, chi phí, mức phục vụ và nguồn kết quả gắn với cùng mã lần chạy.

![Bản thiết kế giao diện nối đầu vào và kết quả bằng cùng mã lần chạy](Giay_to/presentation_assets/diagrams/slide17-dashboard-wireframe.png)

**Lời thuyết trình**

Người dùng chọn kịch bản và thấy nguồn nhu cầu, giả định còn thiếu. Mã lần chạy nối map, hình UE và các chỉ số. Danh mục QUBO mới giải chỉ là ứng viên; sau khi SUMO chạy lại mới có kết quả kiểm tra. Giao diện này chưa hoàn tất.

### Slide 19: Cảm ơn

**Trên slide**

**Cảm ơn Ban Giám khảo đã lắng nghe.**

Nhóm PIG4 sẵn sàng trao đổi về mô hình nhu cầu, điều khiển RL, lựa chọn đầu tư QUBO và những phần chưa được kiểm chứng.

![Trang kết thúc với lời cảm ơn và cảnh giao thông minh họa](Giay_to/presentation_assets/diagrams/slide19-thank-you.png)

**Lời thuyết trình**

Nhóm em xin cảm ơn Ban Giám khảo đã lắng nghe. Nhóm sẵn sàng trình bày rõ phần nào đã có mã, phần nào còn là thiết kế và cách sẽ kiểm chứng từng giả thuyết trên cùng map. Em xin nhận câu hỏi của Ban Giám khảo.
