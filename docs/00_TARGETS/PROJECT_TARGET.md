# Mục tiêu dự án

Quyết định hiện hành, cập nhật 2026-09-28. Đây là mục tiêu, không phải báo cáo hoàn thành.

Chốt lại 2026-10-02: ưu tiên trực tiếp SUMO → Unreal trên map hiện tại. Cấu hình hiển thị
phải chỉnh bằng Unreal Editor qua native Data Asset/Blueprint; đổi mesh, material hoặc camera
không yêu cầu sửa/build C++. C++ giữ transport và áp traffic truth. Kim chỉ nam được lưu trong
AGENTS.md; đặc tả thực hiện là UNREAL_ASSET_PIPELINE.md. Không dùng cảnh dàn dựng làm bằng chứng
simulation tích hợp. Các điều kiện demand/RL/QUBO không chặn mốc kết nối này.

Ưu tiên triển khai hiện tại: hoàn thiện bản đồ OSM giữ lại → mạng và lần chạy SUMO → cảnh
Unreal có thể chỉnh/sửa assets, LOD và kiểm tra hiệu năng → dashboard/UI đọc cùng map/run.
Route `randomTrips` cũ chỉ dùng để thử xe và replay; demand hành vi làm sau nền map.
RL và QUBO tạm hoãn, không chặn mốc thành phố và dashboard này. Các bài toán nghiên cứu dưới
đây vẫn là mục tiêu dài hạn, chưa phải điều kiện nghiệm thu của giai đoạn đang làm.

## Bốn bài toán

1. Demand: mô hình người/hộ/cơ sở/doanh nghiệp và chuỗi hoạt động tạo chuyến đi, giờ xuất phát,
   đích, phương tiện, đi chung và lượt về. Tỷ lệ theo building/giờ/loại xe là kết quả tổng hợp
   hoặc ràng buộc hiệu chỉnh, không phải các tỷ lệ gán độc lập.
2. RL: điều khiển tín hiệu theo trạng thái được phép quan sát, với safety thực thi tại runtime.
3. QUBO: chọn danh mục đầu tư dưới ngân sách bằng tác động đo được của cùng bộ điều khiển.
4. CV: hướng mở rộng tùy chọn, ước lượng observation từ ảnh và kiểm tra sai số closed-loop.

SUMO sở hữu chuyển động, tuyến, pha đèn và traffic state. Unreal hiển thị và hỗ trợ sensor,
không phải một bài toán nghiên cứu độc lập. Không cần ảnh/CV để bắt đầu baseline oracle.

## Phạm vi và bằng chứng

Giữ nguyên net/overlay hiện tại; không đổi ROI để đạt số lượng nút hoặc tạo nghẽn đẹp.
Pilot tối đa 8 eligible TLS trên mạng đầy đủ, các nút ngoài pilot giữ baseline.
Không đồng nhất số TLS trong inventory với số agent đã kiểm chứng.

Đánh giá trên cùng demand và bộ định giá; tách chi phí toàn mạng khỏi reward normalization.
Không lấy doanh thu building/tổng giá trị lô hàng làm phần tiết kiệm do đèn tạo ra.
An toàn không được đánh đổi bằng monetary reward; phải báo mức phục vụ và phân phối tác động.

Nguồn số phải truy được về dữ liệu hoặc giả định. Synthetic có thể nhất quán mà vẫn chưa đúng
thực tế. Chưa có hiệu chỉnh thì chỉ kết luận trong kịch bản giả định, không khuyến nghị ngân sách thật.
Không khẳng định RL tối ưu toàn cục, QUBO chính xác toàn mạng hoặc có ưu thế lượng tử.

## Thiết kế có thể thay đổi sau kiểm định

Shared policy và so PPO/frame-stack/RecurrentPPO là protocol pilot, không phải model đã thắng.
Đầu tiên freeze checkpoint khi đo QUBO; không vừa thay policy vừa so hệ số đầu tư.
Sensor geometry trước detector nếu triển khai nhánh CV. Graph policy, alternating optimization,
raw-image RL và mở rộng đầu tư toàn mạng không là yêu cầu của đợt đầu.

Xem [audit](../04_STATUS/IMPLEMENTATION_STATUS.md), [plan](../02_ARCHITECTURE/SYSTEM_DELIVERY_PLAN.md)
và [demand](../02_ARCHITECTURE/CURRENT_ROI_DEMAND_DATASET_DESIGN.md).
