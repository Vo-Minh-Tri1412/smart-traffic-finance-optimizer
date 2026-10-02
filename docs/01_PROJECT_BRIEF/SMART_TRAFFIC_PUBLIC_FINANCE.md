# Smart Traffic Public Finance Optimizer

## Câu hỏi nghiên cứu

Với nhu cầu đi lại có lập luận hành vi và ngân sách hữu hạn, nên điều khiển đèn thế nào,
đầu tư tại đâu, và kết quả thay đổi ra sao khi quan sát giao thông không hoàn hảo?

Bốn bài toán là Demand, RL, QUBO và CV tùy chọn. SUMO/Unreal là công cụ mô phỏng/hiển thị.

## Demand làm cơ sở

Người/hộ/doanh nghiệp thực hiện hoạt động tại cơ sở có lịch và sức chứa. Mô hình tạo tour
nhất quán về thời gian, phương tiện và địa điểm; gom lại thành OD/lưu lượng theo giờ.
Không suy dân số từ diện tích rồi tự gán tỷ lệ xe, không sinh lượt về độc lập với lượt đi.
Phải mô hình cả dòng vào, ra và xuyên qua biên map.

## Tối ưu kép

RL tối ưu vận hành với action hợp lệ. QUBO tối ưu đầu tư bằng chênh lệch chi phí dưới những
mask đã đo, trên cùng demand, checkpoint và giả định. Công thức chuẩn nằm trong
[objective rationale](../02_ARCHITECTURE/RL_QUBO_OBJECTIVE_RATIONALE.md).

Lợi ích là chi phí tránh được so baseline. Tách cost của từng trip khỏi capex/opex danh mục;
không cộng lại bus passenger cost đã nằm trong tổng, không clip tác động xấu thành zero.
Giữ an toàn tại action layer và đánh giá tiếp cận/công bằng ngoài monetary score.

## Nhánh CV

So oracle với quan sát hình học, sau đó với ảnh/detector nếu có dataset và QA.
Không suy mục đích chuyến đi hoặc giá trị hàng hóa từ lớp xe nhìn thấy.
CV là tùy chọn mở rộng, không chặn baseline Demand–RL–QUBO.

## Ranh giới hiện tại

Repository có các thành phần chạy được riêng, chưa có pipeline nghiên cứu đầu-cuối trên map.
Fixture, template và demo là công cụ kiểm tra, không phải kết quả nghiên cứu.
Trạng thái từng module và điều kiện còn thiếu nằm trong
[audit](../04_STATUS/IMPLEMENTATION_STATUS.md).

Track dự kiến: AI for Public Policy and Public Finance. Hồ sơ cuộc thi là tài liệu nguồn có ngày,
không tự xác nhận deadline hiện hành. Không cần thay map để phù hợp câu chuyện thuyết trình.
