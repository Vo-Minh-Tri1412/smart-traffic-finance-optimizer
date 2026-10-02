# Chỉ dẫn làm việc

## Ưu tiên công cụ

- Ưu tiên Serena cho symbol, references và refactor xuyên file khi công cụ có sẵn.
- Dùng sg cho tìm kiếm cấu trúc code; giới hạn kết quả trước khi mở nhiều file.

## Tư duy phản biện

- Ưu tiên tính đúng đắn; không mặc định đồng ý với đề xuất của người dùng.
- Nêu giả định và điểm chưa có bằng chứng; tìm phản ví dụ, rủi ro và đánh đổi.
- Phân biệt sự thật đã kiểm chứng, suy luận và ý kiến.
- Với yêu cầu mơ hồ, chọn diễn giải hợp lý và chỉ hỏi lại khi lựa chọn ảnh hưởng đáng kể.
- Phản biện thẳng thắn, tôn trọng và hướng tới giải pháp.

## Kim chỉ nam SUMO–Unreal — chốt 2026-10-02

- Mốc hiện tại là nối simulation SUMO vào Unreal trên nguyên map của dự án.
  RL, QUBO, mô hình demand nghiên cứu và việc làm đẹp thành phố không chặn mốc này.
- SUMO sở hữu tuyến, chuyển động, kích thước xe, pha đèn và thời gian simulation.
  UE nhận trạng thái đó; không dàn dựng xe/đèn rồi trình bày như simulation đã tích hợp.
- Dùng kiến trúc Unreal chuẩn: plugin/Actor/Component, Blueprint và native Data Asset.
  TCP là transport tùy biến; không gọi nó là connector SUMO chính thức của Epic.
- Cấu hình hiển thị phải sửa được trong Unreal Editor: catalog mesh/material, profile
  bố trí, camera, ánh sáng và preset cảnh. Không hardcode các lựa chọn này trong bridge.
- Data Asset là nguồn cấu hình mỹ thuật. JSON chỉ là snapshot/provenance xuất ra theo run;
  không duy trì hai nguồn cấu hình cần sửa đồng thời.
- C++ giữ transport, validation, chuyển hệ tọa độ và áp trạng thái. Cho phép Blueprint
  mở rộng phần hiển thị. Đổi mesh/material/camera không được yêu cầu sửa/build lại C++.
- Mesh thay thế phải giữ canonical physical proxy và trạng thái SUMO. Thiếu tài sản quan
  trọng phải báo lỗi hoặc fallback được đếm rõ, không thay âm thầm.
- Tách root/khung vật lý SUMO khỏi mesh hiển thị. Giữ tỉ lệ model mặc định, căn đáy xe
  đúng mặt đường; tránh ghép parent scale không đồng đều với child rotation làm méo mesh.
- Ưu tiên hoàn thành một đường chạy có thể khởi động lại bằng một lệnh. Dùng route thử
  hiện có để kiểm chứng kết nối và ghi rõ đây chưa phải demand đô thị đã hiệu chỉnh.
- Nghiệm thu bằng simulation thật trong game viewport: xe chuyển động, đèn theo SUMO,
  pose/time khớp, assets đọc được và thử sửa Data Asset có hiệu lực mà không rebuild.
  Ảnh cảnh dàn dựng hoặc ảnh tĩnh khó hiểu không thay thế bằng chứng này.
- Đọc docs/02_ARCHITECTURE/UNREAL_ASSET_PIPELINE.md trước khi thay đổi renderer.
  Sửa đặc tả/plan hiện có khi cần; không tạo roadmap song song.
