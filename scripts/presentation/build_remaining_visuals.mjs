import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Presentation-only diagrams. Labels describe the experiment design, never a
// measured result or a claim that an unfinished pipeline is already working.
const out = resolve(import.meta.dirname, '../../Giay_to/presentation_assets/diagrams');
const ink = '#243b48';
const blue = '#247ca4';
const pale = '#eaf7fc';
const sky = '#d6f0fb';
const teal = '#218e9a';
const amber = '#fff2d8';
const muted = '#596f7c';
const white = '#ffffff';
const esc = (value) => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

function text(x, y, value, size = 30, weight = 500, color = ink, anchor = 'start') {
  return `<text x="${x}" y="${y}" fill="${color}" font-family="Arial, Noto Sans, sans-serif" font-size="${size}" font-weight="${weight}" text-anchor="${anchor}">${esc(value)}</text>`;
}
function rect(x, y, w, h, fill = white, stroke = '#a4cfdf', rx = 23, sw = 3) {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
}
function path(d, color = blue, width = 5, dash = '') {
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round" ${dash ? `stroke-dasharray="${dash}"` : ''} marker-end="url(#arrow)"/>`;
}
function pill(x, y, w, label, fill = pale, color = ink) {
  return `${rect(x, y, w, 54, fill, 'none', 27, 0)}${text(x + w / 2, y + 35, label, 22, 600, color, 'middle')}`;
}
function lines(x, y, values, size = 25, gap = 38, weight = 500, color = ink, anchor = 'start') {
  return values.map((value, i) => text(x, y + i * gap, value, size, weight, color, anchor)).join('');
}
function header(title, subtitle) {
  return `${text(65, 81, title, 47, 700)}${text(67, 127, subtitle, 25, 400, muted)}<path d="M66 151 H1534" stroke="#b8dfed" stroke-width="3"/>`;
}
function wrap(body, note) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" width="1600" height="900"><defs><linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#eef9fd"/></linearGradient><marker id="arrow" markerWidth="11" markerHeight="11" refX="8" refY="5.5" orient="auto"><path d="M1 1 L9 5.5 L1 10" fill="none" stroke="${blue}" stroke-width="2"/></marker></defs><rect width="1600" height="900" fill="url(#bg)"/>${body}<path d="M65 834 H1535" stroke="#cae7f1" stroke-width="2"/>${text(66, 867, note, 19, 400, muted)}</svg>`;
}
function save(name, body, note) {
  writeFileSync(resolve(out, name), wrap(body, note));
}

// Slide 11 / Canva page 12 — separating solver quality from actual traffic gain.
{
  let s = header('Giới hạn của tối ưu kép', 'Nghiệm QUBO tốt chưa chứng minh danh mục có lợi trên mạng giao thông');
  const boxes = [
    {x: 65, title: 'Mô hình QUBO', detail: ['Hệ số từ từng nút', 'và từng cặp nút']},
    {x: 448, title: 'Danh mục chọn', detail: ['Những nút được', 'nâng cấp trong ngân sách']},
    {x: 831, title: 'RL + SUMO', detail: ['Vận hành với đúng', 'danh mục vừa chọn']},
    {x: 1214, title: 'Kết quả đo', detail: ['Chi phí, chuyến dở,', 'mức phục vụ']},
  ];
  boxes.forEach((box, i) => {
    s += rect(box.x, 270, 320, 239, i === 3 ? pale : white);
    s += text(box.x + 160, 337, box.title, 29, 700, blue, 'middle');
    s += lines(box.x + 160, 404, box.detail, 23, 35, 400, ink, 'middle');
    if (i < 3) s += path(`M${box.x + 324} 389 H${boxes[i + 1].x - 13}`);
  });
  s += rect(66, 583, 1468, 183, amber, '#ead4a5');
  s += text(97, 631, 'BA PHÉP KIỂM TRA KHÁC NHAU', 27, 700, ink);
  s += pill(99, 666, 404, 'Bộ giải tìm nghiệm ra sao?', white);
  s += pill(548, 666, 466, 'Mô hình dự đoán đúng không?', white);
  s += pill(1059, 666, 434, 'Đổi giả định có đảo chiều?', white);
  save('slide11-optimization-limits.svg', s, 'Hệ số một và hai nút là mô hình gần đúng · danh mục cần chạy lại trong SUMO');
}

// Slides 1–3 — visual setup, with no fabricated output from the project.
{
  let s = header('Một thành phố, hai quyết định', 'Mô phỏng giao thông làm nơi thử giả thuyết trước khi kết luận');
  s += rect(87, 233, 520, 462, '#f2f9fc');
  s += `<path d="M135 451 H555 M344 281 V646" stroke="#a9cbd9" stroke-width="122"/><path d="M135 451 H555 M344 281 V646" stroke="#fff" stroke-width="4" stroke-dasharray="22 19"/>`;
  s += `<rect x="316" y="422" width="57" height="60" rx="8" fill="#fff" stroke="${blue}" stroke-width="5"/>`;
  s += `<rect x="468" y="314" width="26" height="74" rx="9" fill="${ink}"/><circle cx="481" cy="331" r="7" fill="#e6e58c"/><circle cx="481" cy="352" r="7" fill="#9fd0a9"/>`;
  s += path('M613 455 H735');
  s += rect(762, 235, 740, 192, white);
  s += pill(790, 260, 90, '01', sky, blue);
  s += lines(902, 311, ['Vận hành đèn theo tình huống', 'Quyết định lặp lại trong mô phỏng'], 30, 49);
  s += rect(762, 478, 740, 192, white);
  s += pill(790, 503, 90, '02', sky, blue);
  s += lines(902, 554, ['Chọn nơi nâng cấp khi có ngân sách', 'Quyết định đầu tư theo danh mục'], 30, 49);
  save('slide01-two-decisions.svg', s, 'Hình dẫn nhập · không đại diện cho một nút giao cụ thể trên map');
}

{
  let s = header('Ùn tắc là vấn đề lớn, nhưng cần đọc đúng con số', 'Thông tin bối cảnh không phải mức tiết kiệm mà dự án đã tạo ra');
  s += rect(82, 245, 695, 395, pale);
  s += text(430, 358, '≈ 6 tỷ USD/năm', 73, 700, blue, 'middle');
  s += lines(430, 431, ['Mức thiệt hại do ùn tắc TP.HCM', 'theo phát biểu được báo dẫn'], 28, 47, 500, ink, 'middle');
  s += rect(831, 245, 686, 395, white);
  s += text(870, 310, 'PHẠM VI NHÓM NGHIÊN CỨU', 27, 700, blue);
  s += pill(872, 348, 577, 'Cách vận hành đèn', sky, ink);
  s += pill(872, 428, 577, 'Nơi ưu tiên nâng cấp', sky, ink);
  s += lines(872, 551, ['Không suy ra rằng giải pháp sẽ', 'thu hồi được 6 tỷ USD.'], 26, 39, 600, ink);
  save('slide02-context-not-impact.svg', s, 'Nguồn con số: Pháp Luật TP.HCM, tường thuật phát biểu ngày 28/5/2025');
}

{
  let s = header('Hai câu hỏi cùng hướng về một bộ đo', 'Công thức trên slide chỉ là ký hiệu minh họa, chưa phải reward đầy đủ');
  s += rect(82, 235, 602, 255, white);
  s += pill(111, 262, 154, 'VẬN HÀNH', sky, blue);
  s += lines(117, 360, ['Đèn chuyển pha khi nào?', 'Xe và chuyến đi chịu chi phí gì?'], 30, 52);
  s += rect(915, 235, 602, 255, white);
  s += pill(944, 262, 137, 'ĐẦU TƯ', sky, blue);
  s += lines(950, 360, ['Nâng cấp những nút nào?', 'Lợi ích có vượt chi phí không?'], 30, 52);
  s += path('M385 491 V585 H777');
  s += path('M1216 491 V585 H823');
  s += path('M800 587 V606');
  s += rect(602, 612, 396, 103, pale);
  s += text(800, 674, 'Bộ đo chi phí chung', 32, 700, ink, 'middle');
  save('slide03-two-problems-one-metric.svg', s, 'Mục tiêu nghiên cứu · chưa có kết quả tối ưu hay mức cải thiện được xác nhận');
}

// Slide 8 — the physical occlusion that motivates camera-based observations.
{
  let s = header('Xe bị che vẫn ở trong bài toán', 'Camera chỉ thấy một phần hàng chờ; chi phí giao thông tính cho cả xe khuất');
  s += rect(66, 213, 970, 522, '#f2f9fc');
  s += `<path d="M115 447 H986" stroke="#b5d0dc" stroke-width="185"/><path d="M115 447 H986" stroke="#fff" stroke-width="5" stroke-dasharray="30 25"/>`;
  s += `<rect x="142" y="276" width="94" height="73" rx="12" fill="${white}" stroke="${blue}" stroke-width="5"/><circle cx="218" cy="311" r="15" fill="${sky}" stroke="${blue}" stroke-width="4"/>`;
  s += text(140, 260, 'Camera', 27, 700, blue);
  s += `<path d="M230 316 L471 386 M230 316 L471 502" fill="none" stroke="#4d9bc0" stroke-width="4" stroke-dasharray="12 10"/>`;
  s += `<rect x="464" y="390" width="285" height="114" rx="24" fill="#5c9eb6" stroke="#2c6d88" stroke-width="5"/><rect x="485" y="405" width="178" height="38" rx="8" fill="#dff5fc"/><circle cx="516" cy="509" r="18" fill="${ink}"/><circle cx="696" cy="509" r="18" fill="${ink}"/>`;
  s += text(607, 377, 'Xe buýt nhìn thấy', 25, 700, blue, 'middle');
  s += `<rect x="802" y="409" width="149" height="89" rx="20" fill="none" stroke="#b08131" stroke-width="5" stroke-dasharray="12 9"/><circle cx="835" cy="504" r="15" fill="${ink}"/><circle cx="913" cy="504" r="15" fill="${ink}"/>`;
  s += text(878, 382, 'Xe nhỏ bị che', 25, 700, '#9a6f22', 'middle');
  s += rect(1072, 213, 462, 522, white);
  s += text(1103, 267, 'DỮ LIỆU NÀO ĐƯỢC DÙNG?', 26, 700, blue);
  s += lines(1107, 331, ['Geometry tính xe bị che.', 'Nhiễu theo thời gian làm', 'quan sát kém chắc chắn.', 'RL nhận ước lượng theo làn.', 'Bộ đo vẫn tính chi phí', 'của cả hai xe.'], 25, 58);
  save('slide08-occlusion.svg', s, 'Sơ đồ hình học minh họa · nhánh geometry đang ngoại tuyến, chưa nối vào RL');
}

// Slide 12 — fair comparison: shared map, demand, seeds, safety, and metrics.
{
  let s = header('Thử nghiệm có đối chứng', 'So sánh phương pháp trong cùng điều kiện, không chọn riêng lần chạy đẹp nhất');
  s += rect(66, 184, 1468, 160, pale);
  s += text(94, 225, 'CỐ ĐỊNH TRƯỚC KHI SO SÁNH', 25, 700, blue);
  s += pill(95, 251, 286, 'Cùng map và nút');
  s += pill(405, 251, 307, 'Cùng demand / seed');
  s += pill(735, 251, 307, 'Cùng quy tắc an toàn');
  s += pill(1064, 251, 434, 'Cùng bộ đo và kỳ đánh giá');
  s += path('M800 344 V383');
  s += rect(66, 397, 1468, 169, white);
  s += pill(91, 422, 85, 'RL', sky, blue);
  s += lines(213, 446, ['Đèn cố định', 'Điều khiển theo quy tắc', 'RL đã khóa mô hình'], 24, 36);
  s += path('M650 480 H742');
  s += rect(766, 420, 720, 124, pale, '#a4cfdf', 19);
  s += lines(799, 466, ['Đo thời gian, chuyến dở, mức phục vụ', 'và độ dao động giữa các lần chạy'], 26, 38);
  s += rect(66, 590, 1468, 185, white);
  s += pill(91, 617, 135, 'QUBO', sky, blue);
  s += lines(254, 645, ['Gốc, từng nút, từng cặp → hệ số', 'So danh mục QUBO với chọn lần lượt'], 24, 38);
  s += path('M787 684 H859');
  s += rect(884, 614, 601, 140, pale, '#a4cfdf', 19);
  s += lines(912, 659, ['Chạy lại SUMO để kiểm tra;', 'bài toán nhỏ: xét hết tổ hợp'], 25, 38);
  save('slide12-controlled-experiment.svg', s, 'Sơ đồ thiết kế thí nghiệm · chưa phải kết quả thực nghiệm');
}

// Slide 14 — CV is an optional observation source, not the core geometry sensor.
{
  let s = header('CV: nguồn ảnh mở rộng cho RL', 'Geometry + nhiễu là nhánh quan sát đích; CV chỉ thay nguồn dữ liệu đầu vào');
  const boxes = [
    {x: 65, title: 'Ảnh từ UE', status: 'CHƯA XUẤT ĐỒNG BỘ', detail: ['Khung hình RGB', 'cùng run_id, camera', 'và thời điểm SUMO']},
    {x: 448, title: 'Ảnh + nhãn', status: 'MỚI CÓ KHUNG', detail: ['Mẫu dataset YOLO', 'cần nhãn xe thấy được', 'và chia tập theo run']},
    {x: 831, title: 'Nhận biết xe', status: 'CHƯA HUẤN LUYỆN', detail: ['Ultralytics / OpenCV', 'phát hiện, theo dõi', 'và đo sai số']},
    {x: 1214, title: 'Quan sát RL', status: 'CHƯA VÒNG KÍN', detail: ['Cùng giao diện', 'hàng chờ và tin cậy', 'như nhánh geometry']},
  ];
  boxes.forEach((box, i) => {
    s += rect(box.x, 258, 320, 340, white);
    s += pill(box.x + 18, 280, 284, box.status, amber, ink);
    s += text(box.x + 160, 388, box.title, 30, 700, blue, 'middle');
    s += lines(box.x + 160, 446, box.detail, 23, 36, 400, ink, 'middle');
    if (i < 3) s += path(`M${box.x + 324} 434 H${boxes[i + 1].x - 13}`);
  });
  s += rect(66, 646, 1468, 120, '#e7f5fa');
  s += text(98, 696, 'KHÓA NỐI DỮ LIỆU', 27, 700, blue);
  s += text(98, 736, 'Cùng giao diện quan sát; trạng thái thật SUMO chỉ dùng để chấm, không cấp lén cho RL.', 25, 500);
  save('slide14-cv-implementation.svg', s, 'Geometry có mã thử ngoại tuyến; CV từ ảnh UE chưa có dataset hay model đã huấn luyện');
}

// Slide 15 — distinguish camera quality from decision quality and traffic quality.
{
  let s = header('Camera phải được kiểm tra qua giao thông', 'Một điểm nhận biết tốt chưa tự chứng minh đèn vận hành tốt hơn');
  const xs = [63, 369, 675, 981, 1287];
  const labels = [
    ['Ảnh camera', 'UE dựng từ cùng', 'tình huống SUMO'],
    ['Nhận biết xe', 'Phát hiện + theo dõi', 'có thể bỏ sót xe'],
    ['Quan sát theo làn', 'Ước lượng hàng chờ', 'và độ tin cậy'],
    ['RL + an toàn', 'Quyết định pha đèn', 'trong vòng chạy'],
    ['Bộ đo SUMO', 'Thời gian, chuyến dở,', 'mức phục vụ'],
  ];
  xs.forEach((x, i) => {
    s += rect(x, 281, 250, 270, i === 4 ? pale : white);
    s += text(x + 125, 325, `${i + 1}`, 38, 700, blue, 'middle');
    s += text(x + 125, 386, labels[i][0], 28, 700, ink, 'middle');
    s += lines(x + 125, 436, labels[i].slice(1), 22, 34, 400, muted, 'middle');
    if (i < 4) s += path(`M${x + 255} 416 H${xs[i + 1] - 13}`);
  });
  s += rect(66, 609, 1468, 160, amber, '#eed7a8');
  s += text(95, 650, 'THỬ TỪNG NGUỒN LỖI RIÊNG', 26, 700, ink);
  s += pill(98, 677, 302, 'Che khuất', white);
  s += pill(424, 677, 302, 'Ánh sáng', white);
  s += pill(750, 677, 302, 'Mất khung', white);
  s += pill(1076, 677, 302, 'Độ trễ', white);
  save('slide14-camera-validation.svg', s, 'Ba tầng cần đo: nhận biết → quan sát ước lượng → kết quả giao thông');
}

// Slide 15 — pair investment cost with benefit measured under the same camera setup.
{
  let s = header('Camera đi vào bài toán đầu tư như thế nào?', 'Mỗi nút ứng viên nhận một gói nâng cấp cố định; chưa tối ưu vị trí camera');
  s += rect(68, 220, 652, 390, white);
  s += pill(96, 246, 280, 'CHI PHÍ GÓI', sky, blue);
  s += lines(110, 350, ['Thiết bị camera và xử lý', 'Lắp đặt, bảo trì, vận hành', 'Quy về cùng kỳ đánh giá'], 29, 65);
  s += rect(880, 220, 652, 390, white);
  s += pill(910, 246, 430, 'LỢI ÍCH ĐO ĐƯỢC', sky, blue);
  s += lines(924, 350, ['Quan sát đúng chất lượng gói', 'RL chạy với độ trễ của gói', 'Chạy đối chứng trên cùng SUMO'], 29, 65);
  s += path('M390 612 V666 H777');
  s += path('M1204 612 V666 H823');
  s += path('M800 667 V674');
  s += rect(595, 678, 410, 96, pale, '#8fc8dd');
  s += text(800, 738, 'QUBO: chọn gói / nút', 31, 700, ink, 'middle');
  s += path('M1008 725 H1195');
  s += text(1232, 735, 'Chạy lại SUMO', 25, 600, blue);
  save('slide15-camera-investment.svg', s, 'Không ghép lợi ích từ trạng thái SUMO hoàn hảo với chi phí camera thực');
}

// Slide 17 — a UI wireframe. Dashes are placeholders, not fabricated metrics.
{
  let s = header('Người dùng sẽ nhìn thấy gì?', 'Bản thiết kế giao diện: một mã lần chạy nối map, giả định, hình ảnh và kết quả');
  s += rect(66, 183, 1468, 611, white, '#87bed5', 20);
  s += rect(67, 184, 1466, 73, pale, '#87bed5', 18);
  s += text(96, 228, 'Bảng điều khiển thử nghiệm', 29, 700);
  s += pill(1190, 194, 315, 'Run ID: chưa chạy', white, muted);
  s += rect(93, 285, 320, 476, '#f7fcfe', '#bedfea', 17);
  s += text(116, 328, 'Đầu vào & giả định', 27, 700, blue);
  s += lines(118, 389, ['Map: bản hiện tại', 'Nguồn demand: —', 'Điều khiển: —', 'Ngân sách: —', 'Dữ liệu thiếu: —'], 23, 64);
  s += rect(440, 285, 665, 476, '#f1f9fc', '#bedfea', 17);
  s += text(466, 328, 'Bản đồ / UE phát lại', 27, 700, blue);
  s += `<path d="M485 540 H1057 M742 361 V703" stroke="#a9cbd9" stroke-width="75"/><path d="M485 540 H1057 M742 361 V703" stroke="#fff" stroke-width="3" stroke-dasharray="20 18"/>`;
  s += `<rect x="708" y="505" width="68" height="70" rx="8" fill="#ffffff" stroke="#448da8" stroke-width="5"/>`;
  s += text(769, 692, 'Cùng lần chạy', 21, 600, muted, 'middle');
  s += rect(1132, 285, 375, 476, '#f7fcfe', '#bedfea', 17);
  s += text(1157, 328, 'Kết quả & độ tin cậy', 27, 700, blue);
  s += lines(1158, 390, ['Chi phí đi lại: —', 'Chuyến dở: —', 'Mức phục vụ: —', 'Độ dao động: —'], 23, 66);
  s += pill(1159, 681, 315, 'Chưa có kết quả', amber, ink);
  save('slide17-dashboard-wireframe.svg', s, 'Wireframe mục tiêu · không phải ảnh chụp giao diện đã hoàn thiện');
}

// Slide 18 — module state and the order needed for evidence-backed conclusions.
{
  let s = header('Đã có nền, còn thiếu bằng chứng đầu-cuối', 'Không công bố hiệu quả hay nút nên đầu tư trước khi các phép kiểm tra hoàn thành');
  const cols = [
    { x: 66, w: 449, fill: pale, title: 'ĐÃ CÓ MÃ NỀN', items: ['Map + SUMO / UE', 'Mô-đun RL / QUBO', 'Kinh tế + giao diện', 'Kiểm tra cục bộ'] },
    { x: 576, w: 449, fill: amber, title: 'CÒN THIẾU', items: ['Demand đủ căn cứ', 'Bộ đo toàn mạng', 'RL đánh giá trên map', 'Hệ số QUBO + CV vòng kín'] },
    { x: 1086, w: 449, fill: '#e6f5ed', title: 'THỨ TỰ TIẾP', items: ['1. Dữ liệu & bộ đo', '2. Đối chứng & RL', '3. Tác động & QUBO', '4. Camera mở rộng'] },
  ];
  cols.forEach((col, i) => {
    s += rect(col.x, 240, col.w, 478, col.fill, '#b7d9e5', 26);
    s += text(col.x + 29, 299, col.title, 29, 700, i === 1 ? '#9a6f22' : blue);
    col.items.forEach((item, j) => {
      s += `<circle cx="${col.x + 39}" cy="${365 + j * 80}" r="9" fill="${i === 1 ? '#cb9f4c' : teal}"/>`;
      s += text(col.x + 66, 375 + j * 80, item, 25, 500);
    });
    if (i < 2) s += path(`M${col.x + col.w + 8} 478 H${cols[i + 1].x - 16}`);
  });
  save('slide18-status-roadmap.svg', s, 'Trạng thái công việc · “có mã nền” không đồng nghĩa với “đã kiểm chứng hiệu quả”');
}
