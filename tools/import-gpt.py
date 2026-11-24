# Импорт картинок ChatGPT: ZIP или папка с PNG/JPG/WebP → assets/gpt/<id>.webp нужного размера.
# Фоны (bg-*) и комнаты (room-*) — 2048×1536, остальное — 1024×1024; обрезка по центру, WebP q80.
# Запуск: python3 tools/import-gpt.py <архив.zip | папка>   (нужен Pillow)
import sys, os, zipfile, io
from PIL import Image
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'assets', 'gpt')

def items(src):
    if zipfile.is_zipfile(src):
        z = zipfile.ZipFile(src)
        for i in z.infolist():
            n = os.path.basename(i.filename)
            if n.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')): yield n, z.read(i)
    else:
        for n in sorted(os.listdir(src)):
            if n.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')): yield n, open(os.path.join(src, n), 'rb').read()

def main(src):
    os.makedirs(OUT, exist_ok=True); total = 0
    for name, data in items(src):
        id_ = os.path.splitext(name)[0].lower()
        im = Image.open(io.BytesIO(data)).convert('RGB')
        tw, th = (2048, 1536) if id_.startswith(('bg-', 'room-')) else (1024, 1024)
        r = max(tw / im.width, th / im.height)
        im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
        L, T = (im.width - tw) // 2, (im.height - th) // 2
        p = os.path.join(OUT, id_ + '.webp')
        im.crop((L, T, L + tw, T + th)).save(p, 'WEBP', quality=80, method=6)
        total += os.path.getsize(p); print(id_, os.path.getsize(p))
    print('итого МБ', round(total / 1048576, 2))

if __name__ == '__main__':
    main(sys.argv[1])
