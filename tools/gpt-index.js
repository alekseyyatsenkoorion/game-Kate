// Пересобирает assets/gpt/index.json: список id картинок, для которых есть <id>.webp.
// Конвертация <id>.png → <id>.webp делается отдельно (через Playwright) — этап 4.
const fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..', 'assets', 'gpt');
fs.mkdirSync(dir, { recursive: true });
const images = fs.readdirSync(dir).filter((f) => f.endsWith('.webp')).map((f) => f.slice(0, -5)).sort();
fs.writeFileSync(path.join(dir, 'index.json'), JSON.stringify({ images }, null, 1));
console.log('gpt images:', images.length);
