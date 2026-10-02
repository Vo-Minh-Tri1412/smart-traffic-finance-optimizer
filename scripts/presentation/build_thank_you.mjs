import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const require = createRequire(import.meta.url);
const sharp = require('C:/Users/Tri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const folder = resolve(import.meta.dirname, '../../Giay_to/presentation_assets/diagrams');
const background = resolve(folder, 'slide19-thank-you-background.png');
const output = resolve(folder, 'slide19-thank-you.png');

// The background is a generated storybook illustration. Keep copy as a separate,
// deterministic layer so the Vietnamese accents are legible on the final slide.
const copy = `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
  <text x="105" y="330" font-family="Trebuchet MS, Segoe UI, Arial, sans-serif" font-size="104" font-weight="700" fill="#176d93">Cảm ơn</text>
  <text x="109" y="397" font-family="Trebuchet MS, Segoe UI, Arial, sans-serif" font-size="34" fill="#294b5d">Ban Giám khảo đã lắng nghe</text>
  <path d="M109 437 H612" stroke="#79c7e4" stroke-width="4" stroke-linecap="round"/>
  <text x="109" y="494" font-family="Trebuchet MS, Segoe UI, Arial, sans-serif" font-size="28" fill="#3f6677">Nhóm PIG4 sẵn sàng trả lời câu hỏi.</text>
</svg>`;

await sharp(background)
  .resize(1600, 900, { fit: 'cover' })
  .composite([{ input: Buffer.from(copy), left: 0, top: 0 }])
  .png()
  .toFile(output);
process.stdout.write(`${output}\n`);
