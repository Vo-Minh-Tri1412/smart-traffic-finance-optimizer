# Hướng dẫn nhóm Kinh tế bằng ngôn ngữ dễ hiểu

Nhóm Kinh tế không cần code, không cần train AI, không cần hiểu chi tiết SUMO hay RL.

Vai trò chính của nhóm Kinh tế là giúp mô phỏng giống một quận thật và giúp kết quả trả lời được câu
hỏi chính sách công:

> Nếu ngân sách chỉ đủ nâng cấp một số giao lộ, nên ưu tiên giao lộ nào để tạo nhiều lợi ích kinh tế
> - xã hội nhất?

## Dịch thuật ngữ sang tiếng người

| Từ kỹ thuật | Cách hiểu đơn giản |
|---|---|
| Environment | Thành phố/quận mô phỏng nơi xe chạy. |
| Zone | Một khu vực có ý nghĩa: bệnh viện, trường, khu công nghiệp, khu dân cư. |
| OD flow | Luồng xe "từ đâu đến đâu". |
| Scenario | Một tình huống giả lập, ví dụ giờ vào ca khu công nghiệp hoặc xe cấp cứu. |
| Metric | Con số đo kết quả, ví dụ xe chờ bao lâu, đường kẹt cỡ nào. |
| Observation | Những gì AI nhìn thấy ở giao lộ, ví dụ hàng xe chờ và đèn hiện tại. Nhóm Kinh tế không cần điền phần này. |
| Reward | Điểm thưởng/phạt để AI học. CS xử lý, Kinh tế chỉ góp ý điều gì quan trọng. |
| Public finance | Cách tiêu ngân sách công sao cho đáng tiền. |
| Value of time | Một giờ bị kẹt xe gây thiệt hại khoảng bao nhiêu. |
| Benefit-cost ratio | Một đồng bỏ ra thu lại bao nhiêu giá trị. |

## Nhóm Kinh tế cần làm gì?

### 1. Chọn khu vực nào nên có trong quận mô phỏng

Không cần vẽ bản đồ kỹ thuật. Chỉ cần trả lời:

- Khu này là gì?
- Vì sao nó quan trọng?
- Nó tạo ra xe vào giờ nào?
- Nó liên quan gì đến kinh tế hoặc dịch vụ công?

Ví dụ:

| Khu vực | Vì sao cần có? | Tạo ra xe gì? |
|---|---|---|
| Khu công nghiệp | Liên quan sản xuất, công nhân, logistics. | Xe máy công nhân, xe đưa đón, xe tải. |
| Bệnh viện | Dịch vụ công quan trọng. | Xe cấp cứu, taxi, xe cá nhân, bus. |
| Trường học | Tạo ùn tắc ngắn nhưng mạnh vào sáng/chiều. | Phụ huynh, học sinh, xe bus trường. |
| Chợ/khu thương mại | Có dừng đỗ, giao hàng, mua bán. | Xe máy, xe giao hàng, xe tải nhẹ. |

### 2. Thiết kế luồng xe "từ đâu đến đâu"

Đây là việc quan trọng nhất.

Nhóm Kinh tế không cần biết xe đi qua đường nào. Chỉ cần nói:

```text
Ai đi từ đâu -> đến đâu -> vào giờ nào -> bằng loại xe gì -> vì sao chuyến đi đó quan trọng?
```

Ví dụ:

| Luồng xe | Từ đâu | Đến đâu | Giờ đông | Loại xe chính | Vì sao quan trọng? |
|---|---|---|---|---|---|
| Công nhân đi làm | Khu dân cư | Khu công nghiệp | 05:30-07:30 | xe máy, bus, shuttle | Trễ ca ảnh hưởng sản xuất. |
| Học sinh đi học | Khu dân cư | Trường học | 06:30-07:30 | xe máy, xe cá nhân, school bus | Ùn tắc ngắn nhưng ảnh hưởng nhiều hộ gia đình. |
| Xe tải giao hàng | Kho vận | Khu công nghiệp/chợ | 08:00-11:00 | xe tải nhẹ/nặng | Trễ hàng làm tăng chi phí logistics. |
| Cấp cứu | Trạm/cổng thành phố | Bệnh viện | bất kỳ | ambulance | Không được đánh đồng với xe thường. |

### 3. Nói loại xe nào nên được ưu tiên hơn

Không phải mọi xe đều giống nhau.

| Loại xe | Có nên ưu tiên hơn xe thường không? | Lý do |
|---|---|---|
| Xe cấp cứu | Rất nên | Liên quan sinh mạng/dịch vụ khẩn cấp. |
| Bus | Nên | Một xe chở nhiều người. |
| Xe đưa đón công nhân | Nên trong giờ vào/ra ca | Trễ ca có thể ảnh hưởng sản xuất. |
| Xe tải logistics | Nên ở hành lang công nghiệp | Trễ hàng tạo chi phí kinh tế. |
| Xe cá nhân | Bình thường | Là nhu cầu dân sinh nhưng không phải lúc nào cũng ưu tiên nhất. |
| Taxi/ride-hailing | Tùy tình huống | Quan trọng quanh bệnh viện/khu giải trí nhưng dễ gây dừng đỗ. |

### 4. Thiết kế tình huống giả lập

Mỗi tình huống nên trả lời:

- Chuyện gì đang xảy ra?
- Luồng xe nào tăng?
- Khu nào bị ảnh hưởng?
- Câu hỏi chính sách là gì?

Ví dụ:

| Tình huống | Chuyện gì xảy ra? | Câu hỏi chính sách |
|---|---|---|
| Giờ vào ca khu công nghiệp | Công nhân và xe tải cùng tăng. | Có nên ưu tiên đèn quanh khu công nghiệp không? |
| Xe cấp cứu giờ kẹt xe | Ambulance cần tới bệnh viện qua đường đông. | Đèn thông minh có giảm trễ cấp cứu không? |
| Giờ tan học | Phụ huynh và học sinh tập trung nhanh. | Có nên đầu tư quanh trường hay ưu tiên trục chính? |
| Tối khu giải trí | Taxi, xe cá nhân, dừng đỗ tăng. | Đèn cố định có xử lý nổi nhu cầu bất thường không? |
| Ngân sách hạn chế | Chỉ nâng cấp được vài giao lộ. | Chọn giao lộ nào đáng tiền nhất? |

### 5. Giúp định nghĩa "đáng tiền" là gì

Dự án này không nên nói đơn giản là "AI tiết kiệm ngân sách".

Cách nói đúng hơn:

> Thành phố phải bỏ tiền nâng cấp đèn. Câu hỏi là khoản đầu tư đó có tạo ra đủ lợi ích kinh tế - xã
> hội không, và nên ưu tiên chỗ nào trước.

Nhóm Kinh tế cần góp ý các phần:

- Một giờ kẹt xe của người dân nên tính thế nào?
- Một giờ trễ của xe bus có nên nhân theo số hành khách không?
- Một giờ trễ của xe tải/khu công nghiệp có ý nghĩa gì?
- Xe cấp cứu nên được tính riêng như chỉ số dịch vụ công hay quy ra tiền?
- Chi phí lắp đặt/bảo trì đèn thông minh nên giả định bao nhiêu?
- Nếu chưa có nguồn, giả định nào phải ghi là "tạm tính"?

## Những gì nhóm Kinh tế không cần làm

- Không cần code.
- Không cần train model.
- Không cần sửa repo.
- Không cần hiểu chi tiết observation space.
- Không cần chọn thuật toán RL.
- Không cần tự cào dữ liệu nếu chưa được giao.

## Output tuần 1 nên nộp

| File/bảng | Người điền gì? |
|---|---|
| Bảng khu vực | Khu nào có trong quận, ý nghĩa kinh tế/xã hội. |
| Bảng luồng xe | Xe đi từ đâu đến đâu, giờ nào, loại xe gì. |
| Bảng loại xe ưu tiên | Xe nào quan trọng hơn, vì sao. |
| Bảng tình huống | 5-7 tình huống giả lập đáng demo. |
| Bảng giả định tài chính công | Giá trị thời gian, chi phí lắp đặt, bảo trì, caveat. |
| Q&A phản biện | Những câu ban giám khảo có thể hỏi và cách trả lời. |

## Cách chia việc cho 2 bạn Kinh tế

Gợi ý nhẹ cho tuần đầu:

| Người | Việc chính | Output |
|---|---|---|
| Kinh tế A | Khu vực + luồng xe | Bảng khu vực, bảng luồng xe. |
| Kinh tế B | Tình huống + giả định tiền | Bảng tình huống, bảng giả định tài chính công. |
| Cả hai | Phản biện logic | Q&A, caveat, chỉnh câu chuyện chính sách. |

## Câu hỏi tự kiểm tra

Trước khi gửi cho CS, nhóm Kinh tế nên tự hỏi:

- Luồng xe này có giống đời thật không?
- Có khu nào bị thêm vào chỉ cho đẹp mà không tạo logic giao thông không?
- Khu công nghiệp có thật sự tạo khác biệt so với khu dân cư không?
- Xe cấp cứu/bus/xe tải có được nhìn khác xe cá nhân không?
- Nếu chỉ có tiền nâng cấp vài giao lộ, bảng này có giúp chọn được không?
- Có giả định nào đang nói quá không?
