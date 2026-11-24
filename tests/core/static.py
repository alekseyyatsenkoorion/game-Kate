# Статические проверки кода (tests.md 1.8, 1.9, 2.14, 9.4) — без браузера.
# Комментарии вырезаются, строки разбираются простым лексером JS (строки '…', "…", `…`, комментарии // и /* */).
import os, re, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from _s6 import ROOT

fails = 0
# Известные нарушения в чужих зонах: (проверка, файл) → пояснение. Печатаются как XFAIL и группу не валят;
# любое другое нарушение — FAIL. Когда нарушение исправят, проверка напечатает XPASS — строку отсюда убрать.
KNOWN = {
}


def check(num, ok, msg, bad=()):
    global fails
    bad = list(bad)
    known = [b for b in bad if (num, b.split(':')[0]) in KNOWN]
    real = [b for b in bad if b not in known]
    for (kn, kf), why in KNOWN.items():
        if kn == num and not any(b.split(':')[0] == kf for b in bad) and os.path.exists(os.path.join(ROOT, kf)):
            print('XPASS %s %s [известное нарушение в %s больше не находится — уберите из KNOWN]' % (num, msg, kf))
    for b in known:
        print('XFAIL %s %s — %s [известный баг: %s]' % (num, msg, b, KNOWN[(num, b.split(':')[0])]))
    if known and not real: return
    print(('PASS ' if not real else 'FAIL ') + num + ' ' + msg)
    if real:
        fails += 1
        for b in real[:30]: print('    ✗ ' + b)


def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')


def lex(src):
    """→ (код без комментариев и с пустыми строками-литералами, [(строка, номер_строки)])"""
    out, strs, i, n, line = [], [], 0, len(src), 1
    prev = ''                                     # последний значимый символ — отличить регулярку от деления
    while i < n:
        c = src[i]
        if c == '\n': line += 1
        if src.startswith('//', i):
            j = src.find('\n', i); i = n if j < 0 else j; continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2); j = n if j < 0 else j + 2
            line += src.count('\n', i, j); i = j; out.append(' '); continue
        if c in '\'"`':
            j, buf, start = i + 1, [], line
            while j < n and src[j] != c:
                if src[j] == '\\': buf.append(src[j:j + 2]); j += 2; continue
                if src[j] == '\n': line += 1
                buf.append(src[j]); j += 1
            strs.append((''.join(buf), start)); out.append(c + c); i = j + 1; prev = c; continue
        if c == '/' and prev and prev in '(,=:[!&|?{};+-*%<>~^':
            j = i + 1; cls = False                # литерал регулярного выражения
            while j < n and src[j] != '\n':
                if src[j] == '\\': j += 2; continue
                if src[j] == '[': cls = True
                elif src[j] == ']': cls = False
                elif src[j] == '/' and not cls: break
                j += 1
            out.append('/re/'); i = j + 1; prev = '/'; continue
        out.append(c)
        if not c.isspace(): prev = c
        i += 1
    return ''.join(out), strs


def strip_css(src): return re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)


JS = sorted(glob.glob(os.path.join(ROOT, 'src', '**', '*.js'), recursive=True))
CSS = sorted(glob.glob(os.path.join(ROOT, 'src', '**', '*.css'), recursive=True) + glob.glob(os.path.join(ROOT, 'styles', '*.css')))
HTML = [os.path.join(ROOT, 'index.html')]
SW = os.path.join(ROOT, 'sw.js')
code = {}
for f in JS + [SW]:
    code[rel(f)] = lex(open(f, encoding='utf-8').read())


def uses(pattern, allowed):
    bad = []
    for f, (c, _) in code.items():
        if f in allowed: continue
        for m in re.finditer(pattern, c):
            bad.append('%s:%d' % (f, c.count('\n', 0, m.start()) + 1))
    return bad


# 1.8
bad = uses(r'\bMath\s*\.\s*random\b', {'src/core/rng.js'})
check('1.8', not bad, 'Math.random только в src/core/rng.js', bad)
# 1.9
bad = uses(r'\blocalStorage\b', {'src/core/progress.js'})
check('1.9a', not bad, 'localStorage только в src/core/progress.js', bad)
bad = uses(r'\bcaches\b', {'src/core/updater.js', 'sw.js'})
check('1.9b', not bad, 'caches (Cache Storage) только в updater.js и sw.js', bad)
bad = uses(r'(?<![\w.])fetch\s*\(', {'src/core/content-loader.js', 'src/core/asset-loader.js', 'src/core/updater.js', 'sw.js'})
check('1.9c', not bad, 'fetch только в content-loader.js, asset-loader.js, updater.js и sw.js', bad)
SVG_NS = ('http://www.w3.org/2000/svg', 'http://www.w3.org/1999/xlink', 'http://www.w3.org/1999/xhtml')
bad = []
for f in JS + CSS + HTML + [SW]:
    txt = open(f, encoding='utf-8').read()
    txt = strip_css(txt) if f.endswith('.css') else (lex(txt)[0] + ' '.join(s for s, _ in lex(txt)[1]) if f.endswith('.js') else txt)
    for m in re.finditer(r'https?://[^\s\'"`)<>]*', txt):
        if not m.group(0).startswith(SVG_NS): bad.append('%s: %s' % (rel(f), m.group(0)))
check('1.9d', not bad, 'нет внешних адресов http(s):// в src/, styles/, index.html, sw.js (кроме пространств имён SVG)', bad)

# 2.14 русские строки длиннее 2 слов
ALLOW = {('src/core/debug-scene.js', 'Что-то пошло не так')}   # запасной текст сцены error, когда data/ не загрузилась — из data его взять нельзя
bad = []
for f, (c, strs) in code.items():
    if not f.startswith('src/'): continue
    src_lines = open(os.path.join(ROOT, f), encoding='utf-8').read().split('\n')
    for s, ln in strs:
        if not re.search('[А-Яа-яЁё]', s): continue
        words = re.findall(r'[А-Яа-яЁёA-Za-z0-9-]+', s)
        if len(words) <= 2 or (f, s) in ALLOW: continue
        before = src_lines[ln - 1].split(s[:12])[0] if s[:12] in src_lines[ln - 1] else ''
        if re.search(r'(\blog\s*\.\s*(warn|error|info)|\bgameError|\bbad)\s*\(', before): continue   # сообщения разработчику в лог
        bad.append('%s:%d «%s»' % (f, ln, s[:60]))
check('2.14', not bad, 'в src/ нет русских строк длиннее 2 слов вне комментариев (сообщения в лог не считаются)', bad)

# 9.4 запрещённые API Safari 15.6 (spec.md §6)
FORBID_JS = [(r'\.\s*roundRect\s*\(', 'canvas.roundRect'), (r'\.\s*filter\s*=(?!=)', 'ctx.filter'),
             (r'\bOffscreenCanvas\b', 'OffscreenCanvas'), (r'\brequestIdleCallback\b', 'requestIdleCallback'),
             (r'\bIntl\s*\.\s*Segmenter\b', 'Intl.Segmenter'), (r'importmap', 'import maps')]
bad = []
for f, (c, strs) in code.items():
    for pat, name in FORBID_JS:
        for m in re.finditer(pat, c):
            bad.append('%s:%d %s' % (f, c.count('\n', 0, m.start()) + 1, name))
    for s, ln in strs:
        if 'importmap' in s: bad.append('%s:%d import maps' % (f, ln))
        if re.search(r'@container|container-type', s): bad.append('%s:%d container queries' % (f, ln))
for f in HTML:
    if 'importmap' in open(f, encoding='utf-8').read(): bad.append(rel(f) + ' import maps')


def css_nesting(txt):
    """Вложенность CSS: «{» внутри обычного правила (не @media/@supports/@keyframes…)."""
    stack, out, i, tok = [], [], 0, ''
    for ch in txt:
        if ch == '{':
            sel = tok.strip()
            if stack and stack[-1] == 'rule': out.append(sel[:50])
            kf = stack and stack[-1] == 'keyframes'
            stack.append('keyframes' if re.match(r'@(-webkit-)?keyframes', sel) else 'at' if sel.startswith('@') else 'frame' if kf else 'rule')
            tok = ''
        elif ch == '}':
            if stack: stack.pop()
            tok = ''
        elif ch == ';':
            tok = ''
        else:
            tok += ch
    return out


for f in CSS:
    txt = strip_css(open(f, encoding='utf-8').read())
    for m in re.finditer(r'@container|container-type|container-name', txt):
        bad.append('%s:%d container queries' % (rel(f), txt.count('\n', 0, m.start()) + 1))
    for sel in css_nesting(txt):
        bad.append('%s: вложенность CSS «%s»' % (rel(f), sel))
check('9.4', not bad, 'нет запрещённых API Safari 15.6: import maps, вложенность CSS, container queries, roundRect, ctx.filter, OffscreenCanvas, requestIdleCallback, Intl.Segmenter', bad)

print('Итог: провалено %d' % fails)
sys.exit(1 if fails else 0)
