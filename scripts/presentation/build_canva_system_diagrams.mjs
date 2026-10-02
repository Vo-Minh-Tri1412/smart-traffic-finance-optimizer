import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

// Logic-first diagrams for the 10-minute deck. The road drawings are schematic;
// they do not claim to be measured coordinates or results from the retained map.
const out = "Giay_to/presentation_assets/diagrams";
const ink = "#273A45";
const muted = "#526C7B";
const sky = "#62BDE8";
const light = "#D9F2FC";
const pale = "#F2FBFF";
const white = "#FFFFFF";
const esc = (s) => String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const T = (x, y, s, size = 29, weight = 600, anchor = "middle", fill = ink) =>
  `<text x="${x}" y="${y}" text-anchor="${anchor}" font-family="Segoe UI,Arial,sans-serif" font-size="${size}" font-weight="${weight}" fill="${fill}">${esc(s)}</text>`;
const R = (x, y, w, h, fill = white, stroke = ink, rx = 18, sw = 3) =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
const C = (x, y, r, fill = white, stroke = ink, sw = 3) =>
  `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
const P = (d, stroke = ink, sw = 3, fill = "none", extra = "") =>
  `<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" ${extra}/>`;
const A = (d, label = "", x = 0, y = 0, color = ink) =>
  P(d, color, 4, "none", 'marker-end="url(#arrow)"') + (label ? T(x, y, label, 25, 600, "middle", muted) : "");
const car = (x, y, fill = sky) =>
  `<g transform="translate(${x} ${y})">${R(-27, -12, 54, 24, fill, ink, 8, 2)}${C(-16, 15, 4, ink, ink, 1)}${C(16, 15, 4, ink, ink, 1)}</g>`;
const lightSignal = (x, y) =>
  `<g transform="translate(${x} ${y})">${R(-14, -42, 28, 84, white, ink, 11, 3)}${C(0, -23, 6, white, ink, 1)}${C(0, 0, 6, sky, ink, 1)}${C(0, 23, 6, white, ink, 1)}</g>`;
const traffic = (x, y, w, h, caption = "SUMO: giao thông đang chạy") => {
  const cx = x + w / 2, cy = y + h / 2 + 13;
  return R(x, y, w, h, white, sky, 22, 4)
    + T(x + 22, y + 43, caption, 27, 700, "start")
    + P(`M${x + 24} ${cy} H${x + w - 24}`, light, 50)
    + P(`M${cx} ${y + 65} V${y + h - 24}`, light, 50)
    + P(`M${x + 24} ${cy} H${x + w - 24} M${cx} ${y + 65} V${y + h - 24}`, ink, 2)
    + car(x + 100, cy - 18) + car(x + w - 90, cy + 21, white)
    + lightSignal(cx + 33, cy - 70);
};
const box = (x, y, w, h, title, subtitle = "") =>
  R(x, y, w, h, pale, sky, 20, 4)
  + T(x + w / 2, y + 49, title, 29, 700)
  + (subtitle ? T(x + w / 2, y + 85, subtitle, 24, 500, "middle", muted) : "");
const SVG = (body) => `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="620" viewBox="0 0 900 620">
<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M1 1 L11 6 L1 11" fill="none" stroke="${ink}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>
${body}
</svg>`;

const diagrams = {
  "slide04-system-v2.svg": SVG(`
    ${T(450, 55, "Cùng một mạng đường", 32, 700)}
    ${traffic(118, 84, 664, 300, "Các nút giao và dòng xe trong SUMO")}
    ${C(360, 250, 37, pale, sky, 5)}${C(566, 250, 37, pale, sky, 5)}
    ${T(360, 261, "A", 27, 700)}${T(566, 261, "B", 27, 700)}
    ${box(58, 467, 325, 115, "QUBO chọn nơi", "trong ngân sách")}
    ${box(517, 467, 325, 115, "RL vận hành", "đèn tại nút được chọn")}
    ${A("M220 457 V409 H348 V389")}
    ${A("M680 457 V409 H574 V389")}
    ${T(450, 431, "Bộ đo chi phí từ cùng lần chạy", 24, 600)}
  `),
  "slide05-system-v2.svg": SVG(`
    ${T(450, 55, "Một kịch bản, ba lớp dữ liệu", 32, 700)}
    ${box(31, 204, 205, 135, "OSM", "mạng đường")}
    ${P("M63 290 L90 260 L117 291 L145 245 L194 279", sky, 5)}
    ${traffic(278, 112, 398, 388, "SUMO: xe, đèn, thời gian chờ")}
    ${box(713, 204, 165, 135, "UE", "cảnh 3D")}
    ${P("M734 296 L789 259 L846 296 M789 259 V315", ink, 3)}
    ${A("M237 271 H267")}
    ${A("M680 271 H702")}
    ${T(469, 555, "Cùng map và cùng dấu thời gian", 26, 600)}
  `),
  "slide06-system-v2.svg": SVG(`
    ${T(450, 58, "Từ lịch hoạt động đến chuyến xe", 32, 700)}
    ${box(35, 124, 263, 123, "Lịch cá nhân", "giờ cần có mặt")}
    ${box(35, 312, 263, 123, "Phương tiện", "xe sẵn có, cùng hành trình")}
    ${A("M308 204 H356")}${A("M308 377 H356")}
    ${R(374, 137, 478, 280, white, sky, 20, 4)}
    ${T(613, 183, "Chuỗi hoạt động", 30, 700)}
    ${P("M414 277 H811", light, 18)}
    ${A("M414 277 H808")}
    ${[440,555,670,785].map(x=>C(x,277,24,pale,sky,4)).join("")}
    ${T(440, 333, "Nhà", 24)}${T(555, 333, "Trường", 24)}
    ${T(670, 333, "Làm", 24)}${T(785, 333, "Nhà", 24)}
    ${A("M613 430 V480", "giờ đi và tuyến", 735, 470)}
    ${box(321, 504, 584, 101, "Chuyến đi đưa vào SUMO", "gồm cả vào, ra và đi xuyên khu vực")}
  `),
  "slide07-system-v2.svg": SVG(`
    ${traffic(30, 118, 405, 375, "SUMO: nút giao + xe đang chờ")}
    ${box(535, 75, 330, 104, "Quan sát", "hàng chờ, pha hiện tại")}
    ${box(535, 228, 330, 104, "Chính sách RL", "đề xuất giữ / đổi pha")}
    ${box(535, 381, 330, 104, "Kiểm tra an toàn", "hành động hợp lệ")}
    ${A("M445 224 H525", "trạng thái", 483, 210)}
    ${A("M700 187 V218")}
    ${A("M700 340 V371")}
    ${A("M526 434 H446", "đổi tín hiệu", 487, 466)}
    ${P("M232 503 V550 H700 V497", ink, 3)}
    ${T(450, 589, "SUMO cập nhật xe; bộ đo ghi kết quả cho lần học tiếp", 25, 600)}
  `),
  "slide08-system-v2.svg": SVG(`
    ${T(450, 57, "Các thư viện nằm ở đâu trong vòng chạy?", 31, 700)}
    ${traffic(31, 136, 310, 297, "SUMO: giao thông")}
    ${box(395, 104, 447, 99, "sumo-rl", "đọc trạng thái, gửi hành động")}
    ${box(395, 253, 447, 99, "PettingZoo / SuperSuit", "ghép nhiều nút thành môi trường học")}
    ${box(395, 402, 447, 99, "SB3 / SB3-Contrib", "PPO / RecurrentPPO chọn hành động")}
    ${A("M347 205 H385", "trạng thái", 368, 187)}
    ${A("M620 213 V243")}
    ${A("M620 362 V392")}
    ${P("M390 454 H365 V478 H180 V442", ink, 3, "none", 'marker-end="url(#arrow)"')}
    ${T(448, 563, "hành động qua lớp an toàn → SUMO → quan sát mới", 25, 600)}
  `),
  "slide09-system-v2.svg": SVG(`
    ${traffic(29, 103, 419, 355, "Cùng map, các nút ứng viên")}
    ${C(185, 296, 32, pale, sky, 5)}${T(185, 306, "A", 25, 700)}
    ${C(325, 296, 32, pale, sky, 5)}${T(325, 306, "B", 25, 700)}
    ${box(520, 93, 352, 105, "Chạy đối chứng", "gốc, từng nút, từng cặp")}
    ${box(520, 252, 352, 105, "QUBO + ngân sách", "chọn danh mục ứng viên")}
    ${box(520, 411, 352, 105, "Chạy lại SUMO", "kiểm tra lợi ích thực đo")}
    ${A("M454 173 H508", "chi phí đo", 482, 153)}
    ${A("M696 206 V242")}${A("M696 365 V401")}
    ${P("M513 463 H462", ink, 4, "none", 'marker-end="url(#arrow)"')}
    ${T(450, 574, "Không kết luận chỉ từ danh mục QUBO chọn", 25, 600)}
  `),
  "slide10-system-v2.svg": SVG(`
    ${box(35, 89, 367, 164, "Hồ sơ kinh tế theo tuyến", "OD, chi phí, nguồn và khoảng giá trị")}
    ${box(497, 89, 367, 164, "map_qubo.py", "dựng hệ số riêng, cặp, ngân sách")}
    ${box(497, 348, 367, 164, "solve_map_qubo.py", "giải chính xác pilot nhỏ")}
    ${box(35, 348, 367, 164, "SUMO kiểm tra lại", "cùng map, kịch bản chưa dùng")}
    ${A("M412 171 H487", "dữ liệu", 450, 150)}
    ${A("M680 264 V338")}
    ${A("M487 430 H412", "danh mục", 450, 411)}
    ${P("M214 338 V265", ink, 4, "none", 'marker-end="url(#arrow)"')}
    ${T(450, 579, "Tác động trên map phải được đo trước khi khuyến nghị", 25, 600)}
  `),
};

await mkdir(out, { recursive: true });
for (const [name, content] of Object.entries(diagrams)) {
  await writeFile(join(out, name), content, "utf8");
}
console.log(`Wrote ${Object.keys(diagrams).length} system diagrams to ${out}`);
