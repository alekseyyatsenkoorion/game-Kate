# Проверочный рендер: картинка комнаты с кругами objects (зелёные — find, красные — обманки).
# python3 tests/trials/komnata/render_maps.py [--catalog DIR]
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
W, H = 1024, 768
try:
    FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
except Exception:
    FONT = ImageFont.load_default()

def draw(room, objs, out):
    im = Image.open(os.path.join(ROOT, 'assets', 'gpt', room + '.webp')).convert('RGB').resize((W, H))
    d = ImageDraw.Draw(im)
    for o in objs:
        x, y, r = o['x'] * W, o['y'] * H, o['r'] * W
        c = (40, 255, 80) if o['find'] else (255, 50, 50)
        d.ellipse([x - r, y - r, x + r, y + r], outline=c, width=3)
        d.line([x - 3, y, x + 3, y], fill=c); d.line([x, y - 3, x, y + 3], fill=c)
        t = o['name']
        tx, ty = min(W - 8 * len(t) - 4, max(2, x - 4 * len(t))), min(H - 16, y + r + 2)
        d.rectangle([tx - 1, ty, tx + d.textlength(t, font=FONT) + 1, ty + 15], fill=(0, 0, 0))
        d.text((tx, ty), t, fill=c, font=FONT)
    im.save(out)

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--catalog':
        from build_data import CATALOG
        for room, cat in CATALOG.items():
            draw(room, [{'x': v[1], 'y': v[2], 'r': v[3], 'find': True, 'name': k} for k, v in cat.items()],
                 os.path.join(sys.argv[2], 'cat-' + room + '.png'))
        sys.exit(0)
    data = json.load(open(os.path.join(ROOT, 'data', 'trials', 'komnata.json'), encoding='utf-8'))
    texts = json.load(open(os.path.join(ROOT, 'tests', 'trials', 'fixtures', 'texts-komnata.json'), encoding='utf-8'))
    snap = os.path.join(ROOT, 'tests', 'snapshots', 'B')
    os.makedirs(snap, exist_ok=True)
    for t in data['tasks']:
        p = t['payload']
        draw(p['room'], [dict(o, find=o['id'] in p['find'], name=texts[o['labelKey']]) for o in p['objects']],
             os.path.join(snap, 'komnata-map-' + t['id'] + '.png'))
    print('ok', len(data['tasks']))
