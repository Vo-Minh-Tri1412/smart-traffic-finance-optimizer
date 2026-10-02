import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Keep every module at the same coordinates across slides. A stage only reveals
// additional data/control paths; it never redraws the map or changes a node's role.
const root = resolve(import.meta.dirname, '../..');
const folder = resolve(root, 'Giay_to/presentation_assets/diagrams');
const master = readFileSync(resolve(folder, 'system-overview-preview.svg'), 'utf8');

const stages = [
  {
    file: 'system-stage-01-environment.svg',
    title: 'Bản đồ → mô phỏng → hình ảnh',
    subtitle: 'OSM cung cấp đường; SUMO tính xe và đèn; Unreal Engine chỉ hiển thị',
    hide: ['stage-demand', 'stage-rl', 'stage-cv', 'stage-qubo'],
    viewport: '0 110 1000 690',
  },
  {
    file: 'system-stage-02-demand.svg',
    title: 'Thêm hành trình có thời điểm',
    subtitle: 'Nhu cầu đi lại cung cấp chuyến đi cho cùng môi trường SUMO',
    hide: ['stage-rl', 'stage-cv', 'stage-qubo'],
    viewport: '0 110 1000 690',
  },
  {
    file: 'system-stage-03-control.svg',
    title: 'Quan sát có che khuất đi vào RL',
    subtitle: 'Geometry và nhiễu tạo quan sát; oracle chỉ để đối chứng; reward tách riêng',
    hide: ['stage-cv', 'stage-qubo'],
  },
  {
    file: 'system-stage-04-camera.svg',
    title: 'CV từ ảnh là nguồn quan sát mở rộng',
    subtitle: 'Ảnh UE qua CV dùng chung giao diện RL với nhánh hình học; chưa có vòng kín',
    hide: ['stage-qubo'],
  },
  {
    file: 'system-stage-05-investment.svg',
    title: 'Thêm lựa chọn đầu tư QUBO',
    subtitle: 'Lợi ích đo từ đối chứng và chi phí tạo danh mục; danh mục quay lại SUMO',
    hide: [],
  },
];

for (const stage of stages) {
  const hideStyle = stage.hide.length
    ? `<style>${stage.hide.map((name) => `.${name}{display:none!important}`).join('')}</style>`
    : '';
  let svg = master.replace('</defs>', `${hideStyle}</defs>`);
  svg = svg.replace('Một hệ thống, bốn bài toán liên kết', stage.title);
  svg = svg.replace(
    'Đường dữ liệu, quyết định vận hành và quyết định đầu tư được tách rõ',
    stage.subtitle,
  );
  if (stage.viewport) {
    svg = svg.replace('width="1600" height="900" viewBox="0 0 1600 900"',
      `width="1450" height="1000" viewBox="${stage.viewport}"`);
  }
  writeFileSync(resolve(folder, stage.file), svg, 'utf8');
  process.stdout.write(`${stage.file}\n`);
}
