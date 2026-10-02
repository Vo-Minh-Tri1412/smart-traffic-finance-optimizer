import { createRequire } from 'node:module';
import { resolve, dirname, basename } from 'node:path';

const require = createRequire(import.meta.url);
const sharp = require('C:/Users/Tri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const folder = resolve(import.meta.dirname, '../../Giay_to/presentation_assets/diagrams');
const files = process.argv.slice(2);
if (files.length === 0) throw new Error('Pass at least one SVG filename.');

for (const name of files) {
  const input = resolve(folder, name);
  if (dirname(input) !== folder || !name.endsWith('.svg')) throw new Error(`Unexpected SVG path: ${name}`);
  const output = resolve(folder, `${basename(name, '.svg')}.png`);
  await sharp(input, { density: 144 }).png().toFile(output);
  process.stdout.write(`${output}\n`);
}
