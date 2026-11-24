#!/usr/bin/env python3
"""Зона C — проверка графики: иконки предметов, data/items.json, иконка приложения.

python3 tests/content/art-check.py           — только проверки (код выхода 1 при ошибке)
python3 tests/content/art-check.py --render  — сначала пересобрать PNG-иконки и листы-превью
                                               (нужен Python Playwright и /usr/bin/google-chrome)
"""
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'assets' / 'art'
ICONS = ROOT / 'assets' / 'icons'
SNAP = ROOT / 'tests' / 'snapshots' / 'C'
ITEM_IDS = ['clock', 'kettle', 'lamp', 'book', 'key', 'umbrella', 'scissors',
            'guitar', 'bottle', 'cup', 'candle', 'glasses', 'bell', 'hat']
SVG_NS = '{http://www.w3.org/2000/svg}'
errors = []


def fail(msg):
    errors.append(msg)


def check_svg(path, need_viewbox=None):
    if not path.is_file():
        fail(f'нет файла {path.relative_to(ROOT)}')
        return
    raw = path.read_text(encoding='utf-8')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        fail(f'{path.name}: не XML ({e})')
        return
    if root.tag != SVG_NS + 'svg':
        fail(f'{path.name}: корень не <svg>')
    if need_viewbox and root.get('viewBox') != need_viewbox:
        fail(f'{path.name}: viewBox={root.get("viewBox")!r}, нужен {need_viewbox!r}')
    if root.get('width') or root.get('height'):
        fail(f'{path.name}: у <svg> не должно быть width/height')
    for el in root.iter():
        tag = el.tag.split('}')[-1]
        if tag in ('text', 'tspan', 'textPath', 'filter', 'image', 'script', 'foreignObject', 'style'):
            fail(f'{path.name}: запрещённый элемент <{tag}>')
        for k, v in el.attrib.items():
            if k.split('}')[-1] == 'href' and not v.startswith('#'):
                fail(f'{path.name}: внешняя ссылка {v!r}')
            if 'font' in k:
                fail(f'{path.name}: атрибут шрифта {k}')
            if re.search(r'url\((?!#)', v):
                fail(f'{path.name}: внешний url() в {k}')
    if re.search(r'https?://(?!www\.w3\.org/)', raw):
        fail(f'{path.name}: внешний адрес в тексте файла')


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def check():
    for i in ITEM_IDS:
        check_svg(ART / f'item-{i}.svg', '0 0 256 256')

    try:
        data = json.loads((ROOT / 'data' / 'items.json').read_text(encoding='utf-8'))
    except Exception as e:  # noqa: BLE001
        fail(f'data/items.json не читается: {e}')
        data = None
    if data is not None:
        if data.get('schema') != 1:
            fail('items.json: schema должна быть 1')
        items = data.get('items', [])
        if [x.get('id') for x in items] != ITEM_IDS:
            fail('items.json: id не совпадают со списком/порядком из задачи')
        for x in items:
            if set(x) != {'id', 'labelKey', 'art'}:
                fail(f'items.json: лишние/недостающие поля у {x}')
            if x.get('labelKey') != f'item.{x.get("id")}':
                fail(f'items.json: labelKey у {x.get("id")}')
            if not (ART / f'{x.get("art")}.svg').is_file():
                fail(f'items.json: нет файла для art={x.get("art")}')

    check_svg(ICONS / 'icon.svg')
    for n in (180, 512):
        p = ICONS / f'icon-{n}.png'
        if not p.is_file():
            fail(f'нет {p.relative_to(ROOT)}')
        elif png_size(p) != (n, n):
            fail(f'{p.name}: размер {png_size(p)}, нужен {n}×{n}')


def render():
    import tempfile
    from playwright.sync_api import sync_playwright
    tmp = Path(tempfile.mkdtemp()) / 'page.html'

    def show(pg, html):  # file:// страница, чтобы <img> мог грузить file:// svg
        tmp.write_text(html, encoding='utf-8')
        pg.goto(tmp.as_uri())
        pg.wait_for_load_state('load')
    SNAP.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        pg = br.new_page()
        for n in (180, 512):
            pg.set_viewport_size({'width': n, 'height': n})
            show(pg, f'<style>*{{margin:0}}img{{display:block}}</style>'
                     f'<img src="{(ICONS / "icon.svg").as_uri()}" width="{n}" height="{n}">')
            pg.screenshot(path=str(ICONS / f'icon-{n}.png'), omit_background=False)
        for name, css, bg in (('items-color', '', '#3a2456'),
                              ('items-silhouette', 'filter:brightness(0);', '#d9d9d9')):
            cells = ''.join(f'<div><img src="{(ART / f"item-{i}.svg").as_uri()}"></div>' for i in ITEM_IDS)
            pg.set_viewport_size({'width': 7 * 136 + 8, 'height': 2 * 136 + 8})
            show(pg,
                f'<style>*{{margin:0}}body{{background:{bg};padding:4px;display:grid;'
                f'grid-template-columns:repeat(7,136px)}}div{{width:136px;height:136px;'
                f'display:flex;align-items:center;justify-content:center}}'
                f'img{{width:128px;height:128px;{css}}}</style>{cells}')
            pg.screenshot(path=str(SNAP / f'{name}.png'))
        br.close()


if __name__ == '__main__':
    if '--render' in sys.argv:
        render()
    check()
    if errors:
        print('ART-CHECK: ОШИБКИ')
        for e in errors:
            print('  ✗', e)
        sys.exit(1)
    print(f'ART-CHECK: ок — {len(ITEM_IDS)} иконок, items.json, иконка приложения 180/512')
