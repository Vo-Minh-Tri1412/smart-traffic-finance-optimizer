import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

// Content diagrams for the 10-minute Canva deck. All geometry is deliberately
// deterministic: no invented traffic volumes, benefits, or map coordinates.
const outputDir = "Giay_to/presentation_assets/diagrams";
const C = {
  ink: "#29343B",
  muted: "#62727C",
  sky: "#73C7EB",
  sky2: "#BFEAF9",
  pale: "#EBF8FD",
  white: "#FFFFFF",
  warm: "#F5D6AF",
};
const esc = (s) => String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const txt = (x, y, s, size = 24, weight = 600, fill = C.ink, anchor = "middle") =>
  `<text x="${x}" y="${y}" text-anchor="${anchor}" font-family="Segoe UI,Arial,sans-serif" font-size="${size}" font-weight="${weight}" fill="${fill}">${esc(s)}</text>`;
const rect = (x, y, w, h, fill = C.white, stroke = C.ink, rx = 18, sw = 3) =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
const circle = (x, y, r, fill = C.white, stroke = C.ink, sw = 3) =>
  `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
const line = (x1, y1, x2, y2, stroke = C.ink, sw = 3, extra = "") =>
  `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${sw}" stroke-linecap="round" ${extra}/>`;
const path = (d, stroke = C.ink, sw = 3, fill = "none", extra = "") =>
  `<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" ${extra}/>`;
const arrow = (d, color = C.ink, sw = 3) => path(d, color, sw, "none", 'marker-end="url(#arrow)"');
const car = (x, y, color = C.sky) =>
  `<g transform="translate(${x} ${y})">${rect(-30, -14, 60, 28, color, C.ink, 10, 2.5)}${circle(-16, 16, 5, C.ink, C.ink, 1)}${circle(16, 16, 5, C.ink, C.ink, 1)}</g>`;
const signal = (x, y, active = 1) =>
  `<g transform="translate(${x} ${y})">${rect(-16, -46, 32, 91, C.white, C.ink, 15, 3)}${circle(0, -26, 7, active === 0 ? C.warm : C.white, C.ink, 1.5)}${circle(0, 0, 7, active === 1 ? C.sky : C.white, C.ink, 1.5)}${circle(0, 26, 7, C.white, C.ink, 1.5)}</g>`;
const house = (x, y, scale = 1) =>
  `<g transform="translate(${x} ${y}) scale(${scale})">${path("M-38 -10 L0 -43 L38 -10", C.ink, 3, C.sky2)}${rect(-31, -10, 62, 61, C.white, C.ink, 3, 3)}${rect(-8, 18, 16, 33, C.pale, C.ink, 2, 2)}${rect(-24, 5, 12, 12, C.pale, C.ink, 2, 2)}</g>`;
const building = (x, y, kind = "office") => {
  const top = kind === "school" ? -50 : -68;
  const body = rect(-38, top, 76, 118 + top * -1 - 50, C.white, C.ink, 5, 3);
  const roof = kind === "school" ? path("M-48 -50 H48", C.ink, 3) : "";
  const windows = [-21, 4].flatMap((xx) => [-28, 0, 28].map((yy) => rect(xx, yy, 17, 16, C.sky2, C.ink, 2, 1.7))).join("");
  return `<g transform="translate(${x} ${y})">${body}${roof}${windows}</g>`;
};
const svg = (body) => `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="620" viewBox="0 0 900 620" role="img">
<defs>
  <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M1 1 L9 5 L1 9" fill="none" stroke="${C.ink}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></marker>
</defs>
${body}
</svg>`;

const diagrams = {
  "slide04-dual-optimization.svg": svg(`
    ${txt(78, 85, "RL", 30, 700, C.ink, "start")}
    ${txt(78, 118, "điều khiển theo thời gian", 21, 500, C.muted, "start")}
    ${path("M75 265 H830", C.sky2, 74)}
    ${path("M305 162 V362 M595 162 V362", C.sky2, 70)}
    ${path("M75 265 H830 M305 162 V362 M595 162 V362", C.ink, 3)}
    ${car(165, 247)}${car(455, 247, C.white)}${car(738, 247)}
    ${signal(305, 140)}${signal(595, 140, 0)}
    ${arrow("M205 150 C245 100 340 95 380 147", C.ink)}
    ${txt(780, 105, "quan sát → quyết định", 20, 500, C.muted, "end")}
    ${line(90, 414, 810, 414, C.sky, 4)}
    ${txt(80, 485, "QUBO", 30, 700, C.ink, "start")}
    ${txt(80, 519, "chọn nơi nâng cấp", 21, 500, C.muted, "start")}
    ${circle(305, 475, 38, C.pale, C.sky, 5)}${circle(595, 475, 38, C.pale, C.sky, 5)}
    ${txt(305, 487, "✓", 34, 700, C.ink)}${txt(595, 487, "?", 32, 600, C.ink)}
    ${path("M305 515 V558 H595 V515", C.ink, 3)}
    ${txt(450, 594, "ngân sách và tác động qua lại", 19, 500, C.muted)}
  `),
  "slide05-osm-sumo-ue.svg": svg(`
    ${circle(155, 275, 112, C.pale, C.sky, 4)}
    ${path("M90 210 L120 250 L85 304 L145 342 L214 301 M112 327 L180 225 L232 253", C.ink, 4)}
    ${circle(120, 250, 8, C.sky, C.ink, 2)}${circle(180, 225, 8, C.sky, C.ink, 2)}
    ${circle(445, 275, 112, C.pale, C.sky, 4)}
    ${path("M355 270 H535 M445 185 V365", C.sky2, 35)}
    ${path("M355 270 H535 M445 185 V365", C.ink, 3)}
    ${car(395, 255)}${car(492, 255, C.white)}${signal(463, 220)}
    ${circle(735, 275, 112, C.pale, C.sky, 4)}
    ${path("M658 325 L735 280 L812 325 L735 370 Z", C.ink, 3, C.white)}
    ${path("M735 280 V188 M658 325 V233 L735 188 L812 233 V325", C.ink, 3)}
    ${path("M685 251 L735 221 L785 251", C.sky, 4)}
    ${arrow("M282 275 H315")}${arrow("M572 275 H605")}
    ${txt(155, 452, "OSM", 29, 700)}
    ${txt(445, 452, "SUMO", 29, 700)}
    ${txt(735, 452, "UE", 29, 700)}
    ${txt(155, 487, "mạng đường", 19, 500, C.muted)}
    ${txt(445, 487, "diễn biến xe và đèn", 19, 500, C.muted)}
    ${txt(735, 487, "cảnh 3D", 19, 500, C.muted)}
    ${path("M88 545 H815", C.sky2, 3)}
    ${txt(452, 582, "Cùng một kịch bản, ba vai trò khác nhau", 21, 500, C.ink)}
  `),
  "slide06-activity-demand.svg": svg(`
    ${txt(450, 73, "Hành trình theo lịch hoạt động", 27, 700)}
    ${path("M70 348 C210 310 360 388 500 348 S760 318 840 348", C.sky2, 20)}
    ${path("M70 348 C210 310 360 388 500 348 S760 318 840 348", C.ink, 3, "none", 'stroke-dasharray="8 12"')}
    ${house(95, 263)}${building(285, 262, "school")}${building(480, 260)}
    ${rect(632, 210, 90, 105, C.white, C.ink, 6, 3)}
    ${path("M626 210 H728 L713 190 H642 Z", C.ink, 3, C.sky2)}
    ${house(815, 263)}
    ${circle(95, 348, 10, C.sky, C.ink, 2)}${circle(285, 348, 10, C.sky, C.ink, 2)}
    ${circle(480, 348, 10, C.sky, C.ink, 2)}${circle(677, 348, 10, C.sky, C.ink, 2)}
    ${circle(815, 348, 10, C.sky, C.ink, 2)}
    ${txt(95, 417, "Nhà", 22)}${txt(285, 417, "Trường", 22)}
    ${txt(480, 417, "Công việc", 22)}${txt(677, 417, "Mua sắm", 22)}
    ${txt(815, 417, "Nhà", 22)}
    ${path("M115 490 H785", C.sky, 3)}
    ${arrow("M85 535 H310")}${arrow("M815 535 H590")}
    ${txt(450, 545, "cùng người, cùng phương tiện, các chặng nối tiếp", 20, 500, C.ink)}
  `),
  "slide07-rl-control-loop.svg": svg(`
    ${txt(450, 77, "Vòng điều khiển trong mô phỏng", 28, 700)}
    ${circle(450, 300, 126, C.pale, C.sky, 4)}
    ${path("M344 300 H556 M450 194 V406", C.sky2, 41)}
    ${path("M344 300 H556 M450 194 V406", C.ink, 3)}
    ${car(391, 284)}${car(500, 284, C.white)}${signal(474, 250)}
    ${circle(140, 172, 45, C.white, C.sky, 4)}
    ${circle(760, 172, 45, C.white, C.sky, 4)}
    ${circle(140, 478, 45, C.white, C.sky, 4)}
    ${circle(760, 478, 45, C.white, C.sky, 4)}
    ${txt(140, 181, "1", 28, 700)}${txt(760, 181, "2", 28, 700)}
    ${txt(760, 487, "3", 28, 700)}${txt(140, 487, "4", 28, 700)}
    ${txt(140, 103, "Quan sát", 22)}${txt(760, 103, "Đề xuất", 22)}
    ${txt(760, 559, "Kiểm tra an toàn", 22)}${txt(140, 559, "Đo kết quả", 22)}
    ${arrow("M190 172 H690")}${arrow("M760 225 V409")}
    ${arrow("M710 478 H210")}${arrow("M140 428 V226")}
  `),
  "slide08-rl-stack.svg": svg(`
    ${txt(450, 64, "Python nối mô phỏng với bộ học", 27, 700)}
    ${path("M120 300 H780", C.sky2, 17)}
    ${arrow("M120 300 H770")}
    ${circle(130, 300, 67, C.white, C.sky, 4)}
    ${circle(335, 300, 67, C.white, C.sky, 4)}
    ${circle(545, 300, 67, C.white, C.sky, 4)}
    ${circle(755, 300, 67, C.white, C.sky, 4)}
    ${txt(130, 309, "SUMO", 24, 700)}
    ${txt(335, 309, "sumo-rl", 21, 700)}
    ${txt(545, 291, "PettingZoo", 18, 700)}
    ${txt(545, 317, "SuperSuit", 18, 700)}
    ${txt(755, 309, "SB3", 26, 700)}
    ${txt(130, 407, "giao thông", 19, 500, C.muted)}
    ${txt(335, 407, "môi trường", 19, 500, C.muted)}
    ${txt(545, 407, "nhiều nút", 19, 500, C.muted)}
    ${txt(755, 407, "PPO / LSTM", 19, 500, C.muted)}
    ${path("M750 465 C730 548 210 548 145 465", C.ink, 3, "none", 'stroke-dasharray="7 9"')}
    ${txt(450, 545, "hành động hợp lệ + bộ đo → vòng học kế tiếp", 19, 500, C.ink)}
  `),
  "slide09-qubo-map.svg": svg(`
    ${txt(450, 72, "Chọn tổ hợp trên cùng mạng đường", 27, 700)}
    ${path("M105 180 L276 240 L455 172 L620 240 L790 182 M105 410 L276 340 L455 440 L620 340 L790 410 M276 240 V340 M455 172 V440 M620 240 V340", C.sky2, 25)}
    ${path("M105 180 L276 240 L455 172 L620 240 L790 182 M105 410 L276 340 L455 440 L620 340 L790 410 M276 240 V340 M455 172 V440 M620 240 V340", C.ink, 3)}
    ${[[105,180],[276,240],[455,172],[620,240],[790,182],[105,410],[276,340],[455,440],[620,340],[790,410]].map(([x,y])=>circle(x,y,12,C.white,C.ink,2)).join("")}
    ${circle(276,240,34,C.pale,C.sky,5)}${circle(620,340,34,C.pale,C.sky,5)}
    ${txt(276,249,"✓",29,700)}${txt(620,349,"✓",29,700)}
    ${txt(288,505,"Ứng viên",19,600,C.muted)}
    ${txt(618,505,"Danh mục thử",19,600,C.muted)}
    ${path("M118 554 H782", C.ink, 3)}
    ${rect(118, 541, 385, 26, C.sky2, C.sky, 12, 2)}
    ${txt(450, 603, "Chi phí chọn ≤ ngân sách", 21, 600)}
  `),
  "slide10-qubo-stack.svg": svg(`
    ${txt(450, 68, "Từ dữ liệu đến danh mục kiểm tra", 27, 700)}
    ${path("M90 312 H825", C.sky2, 18)}
    ${arrow("M90 312 H820")}
    ${rect(55, 220, 155, 185, C.white, C.ink, 11, 3)}
    ${line(78, 263, 187, 263, C.sky, 5)}${line(78, 293, 165, 293, C.ink, 2)}
    ${line(78, 323, 177, 323, C.ink, 2)}${line(78, 353, 146, 353, C.ink, 2)}
    ${txt(132, 457, "Hồ sơ tuyến", 19)}
    ${circle(357, 312, 85, C.white, C.sky, 4)}
    ${[[0,0],[0,1],[1,0],[1,1]].map(([i,j])=>rect(327+i*34,282+j*34,25,25,(i===j?C.sky2:C.white),C.ink,3,2)).join("")}
    ${txt(357, 457, "Python QUBO", 19)}
    ${circle(587, 312, 85, C.white, C.sky, 4)}
    ${path("M587 270 V305 M587 305 L555 340 M587 305 L619 340", C.ink, 3)}
    ${circle(555,340,10,C.sky,C.ink,2)}${circle(619,340,10,C.white,C.ink,2)}
    ${txt(587, 457, "Giải bài toán nhỏ", 19)}
    ${circle(797, 312, 70, C.white, C.sky, 4)}
    ${path("M750 311 H844 M797 264 V358", C.sky2, 25)}
    ${path("M750 311 H844 M797 264 V358", C.ink, 2)}
    ${car(784,300)}${txt(797, 457, "Chạy lại SUMO", 19)}
    ${path("M116 532 H792", C.sky, 3)}
    ${txt(454, 580, "Chưa có tác động đo đủ trên map để khuyến nghị", 19, 500, C.muted)}
  `),
};

await mkdir(outputDir, { recursive: true });
for (const [name, content] of Object.entries(diagrams)) {
  await writeFile(join(outputDir, name), content, "utf8");
}
console.log(`Wrote ${Object.keys(diagrams).length} diagrams to ${outputDir}`);
