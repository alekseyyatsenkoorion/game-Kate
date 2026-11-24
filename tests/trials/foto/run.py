# Проверка испытания «Фото-дело» (foto): данные + сценарии на стенде tests/trials/foto/harness.html.
# Запуск из любой папки: python3 tests/trials/foto/run.py
# Поднимает свой сервер (порт 8767) из корня проекта и в конце останавливает его.
# Снимки — tests/snapshots/B/foto-*.png
import json, os, random, re, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PORT = 8767
BASE = 'http://localhost:%d' % PORT
SNAP = os.path.join(ROOT, 'tests', 'snapshots', 'B')
os.makedirs(SNAP, exist_ok=True)
results = []


def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(info)) if info and not cond else ''))


# ---------------- данные ----------------
def test_data():
    data = json.load(open(os.path.join(ROOT, 'data/trials/foto.json'), encoding='utf-8'))
    texts = json.load(open(os.path.join(ROOT, 'tests/trials/fixtures/texts-foto.json'), encoding='utf-8'))
    gpt = set(json.load(open(os.path.join(ROOT, 'assets/gpt/index.json')))['images'])
    check('данные: schema 1, type foto', data.get('schema') == 1 and data.get('type') == 'foto')
    tasks = data['tasks']
    check('данные: 15 заданий', len(tasks) == 15, len(tasks))
    need = {1: (5, 2), 2: (6, 3), 3: (8, 4)}
    probs, keys = [], []
    for lv in (1, 2, 3):
        lvl = [t for t in tasks if t['level'] == lv]
        if len(lvl) != 5:
            probs.append('уровень %d: %d заданий' % (lv, len(lvl)))
        for n, t in enumerate(lvl, 1):
            p = t['payload']
            if t['id'] != 'foto-%d-%03d' % (lv, n): probs.append('id ' + t['id'])
            if not re.match(r'^[a-z0-9-]+$', t['id']): probs.append('id-формат ' + t['id'])
            if p['photo'] != 'foto-%d-%02d' % (lv, n): probs.append('photo ' + t['id'])
            if not os.path.exists(os.path.join(ROOT, 'assets/gpt', p['photo'] + '.webp')) or p['photo'] not in gpt:
                probs.append('нет фото ' + p['photo'])
            st = p['statements']
            if len(st) != need[lv][0]: probs.append('%s: утверждений %d' % (t['id'], len(st)))
            if p['pick'] != need[lv][1] or sum(1 for s in st if s['true'] is True) != p['pick']:
                probs.append('%s: верных не равно pick' % t['id'])
            if any(not isinstance(s['true'], bool) for s in st): probs.append(t['id'] + ': true не bool')
            if any(s['true'] and not s.get('explainKey') for s in st): probs.append(t['id'] + ': нет explainKey у верного')
            if not 2 <= len(p['items']) <= 3: probs.append(t['id'] + ': вещей не 2–3')
            for it in p['items']:
                keys.append(it['labelKey'])
                if it.get('art') and not os.path.exists(os.path.join(ROOT, 'assets/art', it['art'] + '.svg')):
                    probs.append('нет иконки ' + it['art'])
            for s in st:
                keys.append(s['textKey'])
                if s.get('explainKey'): keys.append(s['explainKey'])
    check('данные: уровни 5/5/5, id, photo, 5/6/8 утверждений, верных = pick 2/3/4, вещи 2–3, иконки есть', not probs, probs[:6])
    ui = ['fo.pickK', 'fo.check', 'fo.hintBtn', 'fo.noPower', 'fo.noMoreHints', 'fo.partial', 'fo.solved',
          'fo.ask', 'fo.items', 'fo.holdHint', 'fo.zoomClose', 'fo.noPhoto', 'fo.tooMany']
    miss = [k for k in keys + ui if k not in texts or not str(texts[k]).strip()]
    check('данные: все ключи есть в texts-foto.json', not miss, miss[:6])
    check('данные: ключи уникальны', len(keys) == len(set(keys)))
    unused = sorted(set(texts) - set(keys) - set(ui))
    check('данные: в texts-foto.json нет лишних ключей', not unused, unused[:6])
    check('данные: {k} в fo.pickK, {k} и {n} в fo.partial', '{k}' in texts['fo.pickK'] and '{k}' in texts['fo.partial'] and '{n}' in texts['fo.partial'])
    # код: без кириллицы вне комментариев, без Math.random, своих таймеров и слушателей
    src = open(os.path.join(ROOT, 'src/trials/foto/foto.js'), encoding='utf-8').read()
    code = re.sub(r'//[^\n]*', '', re.sub(r'/\*.*?\*/', '', src, flags=re.S))
    check('код: кириллица только в комментариях', not re.search('[А-Яа-яЁё]', code))
    bad = [w for w in ['Math.random', 'setTimeout', 'setInterval', 'requestAnimationFrame', 'addEventListener',
                       'localStorage', 'fetch(', 'import(', '#'] if w in code and not (w == '#' and '#' not in re.sub(r"'[^']*'", '', code))]
    check('код: нет Math.random/таймеров/слушателей/хранилища/сети/приватных полей', not bad, bad)
    css = open(os.path.join(ROOT, 'src/trials/foto/foto.css'), encoding='utf-8').read()
    kf = re.findall(r'@keyframes[^{]+\{(.*?)\}\s*\}', css, flags=re.S)
    anim_props = set(re.findall(r'([a-z-]+)\s*:', ' '.join(kf)))
    trans = set(p.strip().split()[0] for m in re.findall(r'transition:\s*([^;]+);', css) for p in m.split(','))
    check('css: анимации только transform/opacity', anim_props <= {'transform', 'opacity'} and trans <= {'transform', 'opacity'}, (anim_props, trans))
    return tasks


# ---------------- стенд ----------------
class Page:
    def __init__(self, browser, params):
        self.pg = browser.new_page(viewport={'width': 1024, 'height': 768})
        self.errors = []
        self.pg.on('pageerror', lambda e: self.errors.append('pageerror: ' + str(e)))
        self.pg.on('console', self._console)
        self.pg.goto(BASE + '/tests/trials/foto/harness.html?' + params)
        self.pg.wait_for_function('window.__ready || window.__error', timeout=8000)
        err = self.pg.evaluate('window.__error || null')
        if err:
            self.errors.append('harness: ' + err)
        self.pg.wait_for_timeout(350)

    def _console(self, m):
        if m.type == 'error' and 'Failed to load resource' not in m.text:
            self.errors.append('console: ' + m.text)

    def js(self, code):
        return self.pg.evaluate(code)

    def click(self, sel, wait=80):
        self.pg.click(sel)
        self.pg.wait_for_timeout(wait)

    def hold(self, sel, ms=750):
        box = self.pg.locator(sel).first.bounding_box()
        self.pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        self.pg.mouse.down()
        self.pg.wait_for_timeout(ms)
        self.pg.mouse.up()
        self.pg.wait_for_timeout(120)

    def wait(self, ms):
        self.pg.wait_for_timeout(ms)

    def log(self):
        return self.js('window.__log')

    def ev(self, name, **kw):
        return [e for e in self.log() if e['ev'] == name and all(e.get(k) == v for k, v in kw.items())]

    def finishes(self):
        return [e['result'] for e in self.ev('finish')]

    def sts(self):
        return self.js('window.__h.statements()')

    def trues(self):
        return [s['i'] for s in self.sts() if s['true']]

    def falses(self):
        return [s['i'] for s in self.sts() if not s['true']]

    def has(self, sel, cls):
        return self.js("(() => { const n = document.querySelector('%s'); return !!n && n.classList.contains('%s'); })()" % (sel, cls))

    def shot(self, name):
        self.pg.screenshot(path=os.path.join(SNAP, name))

    def close(self):
        self.pg.close()


def mark(p, idxs):
    for i in idxs:
        p.click('[data-st="%d"]' % i)


def test_trial(b, tasks):
    # (а) верно сразу
    p = Page(b, 'task=0')
    p.shot('foto-l1-start.png')
    check('а: фото из assets/gpt показано', p.js("!!document.querySelector('.fo-polaroid .fo-img') && document.querySelector('.fo-polaroid .fo-img').naturalWidth === 1024"))
    check('а: 5 утверждений, 3 вещи с иконками', p.js("document.querySelectorAll('.fo-st').length") == 5 and p.js("document.querySelectorAll('.fo-item').length") == 3 and p.js("document.querySelectorAll('.fo-art-img').length") >= 1)
    check('а: «Проверить» неактивна до отметки pick', p.has('.fo-check', 'is-off'))
    t = p.trues()
    hb = p.pg.locator('[data-fo="hint"]').bounding_box()
    p.click('[data-st="%d"]' % t[0])
    p.click('[data-fo="check"]')
    check('а: при 1 из 2 проверка не идёт', not p.ev('react') and not p.finishes() and p.js('window.__h.inst.mistakes') == 0)
    p.click('[data-st="%d"]' % t[1])
    check('а: при 2 из 2 «Проверить» активна, счётчик 2 / 2', not p.has('.fo-check', 'is-off') and p.js("document.querySelector('.fo-count').textContent") == '2 / 2')
    f0 = p.falses()[0]
    p.click('[data-st="%d"]' % f0)
    check('а: третью отметку не даёт, пишет подсказку', not p.has('[data-st="%d"]' % f0, 'is-marked') and p.has('.fo-msg', 'is-on'))
    p.click('[data-fo="check"]', 1500)
    p.shot('foto-solved.png')
    check('а: пояснения у верных показаны, ложные скрыты',
          p.js("[...document.querySelectorAll('.fo-st')].filter(n => getComputedStyle(n).display !== 'none').length") == 2
          and p.js("[...document.querySelectorAll('.fo-st.is-right .fo-st-ex')].every(n => getComputedStyle(n).display === 'block' && n.textContent.length > 5)"))
    check('а: заголовок — «Судьба прочитана», кнопки скрыты', 'Судьба' in p.js("document.querySelector('.fo-title').textContent") and not p.pg.locator('.fo-btns').is_visible())
    p.click('[data-st="%d"]' % t[0])
    p.pg.mouse.click(hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2)
    p.wait(4600)
    f = p.finishes()
    check('а: finish ровно 1 раз', len(f) == 1, len(f))
    r = f[0] if f else {}
    check('а: solved, accuracy 1, mistakes 0, hints 0', r.get('solved') is True and r.get('accuracy') == 1 and r.get('mistakes') == 0 and r.get('hintsUsed') == 0 and r.get('powerSpent') == 0, r)
    check('а: формат TrialResult', set(r) >= {'type', 'taskId', 'level', 'solved', 'accuracy', 'hintsUsed', 'powerSpent', 'mistakes', 'timeMs', 'caseClues'}
          and r.get('type') == 'foto' and r.get('taskId') == 'foto-1-001' and r.get('level') == 1 and r.get('caseClues') == [] and isinstance(r.get('timeMs'), int) and r['timeMs'] < 4000, r)
    check('а: react(correct) 1 раз, mistake 0', len(p.ev('react', kind='correct')) == 1 and not p.ev('react', kind='mistake'))
    check('а: после решения подсказка не тратит силу', not p.ev('spend'))
    check('а: Math.random не вызывался', p.js('window.__h.randomCalls()') == 0)
    check('а: нет ошибок', not p.errors, p.errors)
    p.close()

    # (б) одна ошибка
    p = Page(b, 'task=1')
    t, fl = p.trues(), p.falses()
    mark(p, [t[0], fl[0]])
    p.click('[data-fo="check"]', 200)
    check('б: mistakes 1, react(mistake) 1, звук wrong', p.js('window.__h.inst.mistakes') == 1 and len(p.ev('react', kind='mistake')) == 1 and len(p.ev('sfx', id='wrong')) == 1)
    check('б: неверное зачёркнуто и снято, верное осталось отмеченным',
          p.has('[data-st="%d"]' % fl[0], 'is-false') and not p.has('[data-st="%d"]' % fl[0], 'is-marked') and p.has('[data-st="%d"]' % t[0], 'is-marked'))
    msg = p.js("document.querySelector('.fo-msg').textContent")
    check('б: сообщение «Верно 1 из 2»', 'Верно 1 из 2' in msg, msg)
    p.click('[data-st="%d"]' % fl[0])
    check('б: тык по зачёркнутому ничего не делает', not p.has('[data-st="%d"]' % fl[0], 'is-marked') and p.js('window.__h.inst.mistakes') == 1)
    p.click('[data-st="%d"]' % t[1])
    p.click('[data-fo="check"]', 5600)
    f = p.finishes()
    r = f[0] if f else {}
    check('б: finish 1 раз, mistakes 1, accuracy 1 − 1/2', len(f) == 1 and r.get('mistakes') == 1 and abs(r.get('accuracy', 0) - 0.5) < 1e-9 and r.get('solved') is True, r)
    check('б: нет ошибок', not p.errors, p.errors)
    p.close()

    # (б2) уровень 3: две ошибки за две проверки, accuracy = 1 − 2/4
    p = Page(b, 'task=10')
    t, fl = p.trues(), p.falses()
    mark(p, [t[0], t[1], fl[0], fl[1]])
    p.click('[data-fo="check"]')
    check('б2: «Верно 2 из 4»', 'Верно 2 из 4' in p.js("document.querySelector('.fo-msg').textContent"))
    mark(p, [t[2], fl[2]])
    p.click('[data-fo="check"]')
    mark(p, [t[3]])
    p.click('[data-fo="check"]', 5600)
    r = (p.finishes() or [{}])[0]
    check('б2: mistakes 2, accuracy 0.5', r.get('mistakes') == 2 and abs(r.get('accuracy', 0) - 0.5) < 1e-9, r)
    p.close()

    # (в) подсказки
    p = Page(b, 'task=0&power=2')
    for _ in range(3):
        p.click('[data-fo="hint"]')
    sp = p.ev('spend')
    check('в: 2 подсказки списали по 1, 3-я при нуле — отказ', [s['ok'] for s in sp] == [True, True, False] and p.js('window.__h.getPower()') == 0, sp)
    check('в: ctx.hint("strike") 2 раза, зачёркнуто 2 ложных', len(p.ev('hint', kind='strike')) == 2 and p.js("document.querySelectorAll('.fo-st.is-struck').length") == 2
          and all(not s['true'] for s in p.sts() if p.has('[data-st="%d"]' % s['i'], 'is-struck')))
    check('в: «нет силы» показано', p.has('.fo-msg', 'is-on') and 'силы' in p.js("document.querySelector('.fo-msg').textContent"))
    p.wait(2300)
    check('в: «нет силы» скрыто через 2 с', not p.has('.fo-msg', 'is-on'))
    for i in p.trues():
        p.click('[data-st="%d"]' % i)
    p.click('[data-fo="check"]', 5600)
    r = (p.finishes() or [{}])[0]
    check('в: hintsUsed 2, powerSpent 2, accuracy 1', r.get('hintsUsed') == 2 and r.get('powerSpent') == 2 and r.get('accuracy') == 1, r)
    p.close()

    p = Page(b, 'task=0&power=0')
    p.click('[data-fo="hint"]')
    check('в: при силе 0 ничего не списано и не зачёркнуто', [s['ok'] for s in p.ev('spend')] == [False] and not p.ev('hint') and p.js("document.querySelectorAll('.fo-st.is-struck').length") == 0)
    p.close()

    p = Page(b, 'task=0&power=10')
    fl = p.falses()
    p.click('[data-st="%d"]' % fl[0])        # отмеченное ложное тоже может быть зачёркнуто — отметка снимается
    for _ in range(5):
        p.click('[data-fo="hint"]')
    check('в: ложные кончились — кнопка неактивна, лишнего не списано',
          p.has('.fo-hint', 'is-off') and len(p.ev('spend')) == 3 and p.js('window.__h.getPower()') == 7
          and 'Ложных' in p.js("document.querySelector('.fo-hint').textContent"))
    check('в: все ложные зачёркнуты, отметки сняты', p.js("document.querySelectorAll('.fo-st.is-struck').length") == 3 and p.js("document.querySelectorAll('.fo-st.is-marked').length") == 0)
    p.close()

    # (г) крупный просмотр: удержание открывает, тык закрывает, под ним ничего не нажимается
    p = Page(b, 'task=10')
    p.shot('foto-l3-start.png')
    p.hold('.fo-polaroid')
    check('г: удержание открывает фото крупно', p.has('.fo-zoom', 'is-on'))
    p.wait(400)
    p.shot('foto-zoom.png')
    p.pg.mouse.click(700, 400)
    p.wait(100)
    check('г: тык закрывает', not p.has('.fo-zoom', 'is-on'))
    p.hold('.fo-polaroid')
    p.pg.mouse.click(900, 600)       # там, где под затемнением утверждения
    p.wait(100)
    check('г: тык при открытом фото только закрывает', not p.has('.fo-zoom', 'is-on') and p.js("document.querySelectorAll('.fo-st.is-marked').length") == 0)
    p.click('.fo-polaroid')
    check('г: обычный тык по фото тоже открывает', p.has('.fo-zoom', 'is-on'))
    check('г: нет ошибок', not p.errors, p.errors)
    p.close()

    # (д) destroy посреди ожиданий
    p = Page(b, 'task=0&power=0')
    p.click('[data-fo="hint"]')
    mark(p, p.trues())
    p.click('[data-fo="check"]', 100)
    p.js('window.__h.destroy()')
    c = p.js('window.__h.counters()')
    check('д: после destroy поле пусто', p.js('window.__h.field.children.length') == 0)
    check('д: нет таймеров/rAF/слушателей', c == {'timeouts': 0, 'intervals': 0, 'rafs': 0, 'listeners': 0}, c)
    try:
        p.js('window.__h.inst.destroy()'); ok = True
    except Exception:
        ok = False
    check('д: повторный destroy не бросает', ok)
    p.wait(5600)
    check('д: после destroy finish не вызывается', not p.finishes())
    check('д: нет ошибок', not p.errors, p.errors)
    p.close()

    # (е) 300 случайных тыков (уровень 3, без фото — заглушка)
    p = Page(b, 'task=12&power=2&nophoto=1')
    check('е: заглушка «снимок утерян» вместо фото', p.js("!!document.querySelector('.fo-polaroid .fo-fallback') && !document.querySelector('.fo-polaroid .fo-img')"))
    rnd = random.Random(7)
    for _ in range(300):
        p.pg.mouse.click(rnd.uniform(32, 992), rnd.uniform(132, 732))
    p.wait(5600)
    check('е: 300 тыков — 0 ошибок', not p.errors, p.errors[:3])
    check('е: 300 тыков — finish не больше 1', len(p.finishes()) <= 1)
    check('е: сила не ушла в минус', p.js('window.__h.getPower()') >= 0)
    p.close()

    # (ж) пауза не входит во время; битое задание; seed
    p = Page(b, 'task=0')
    p.js('window.__h.inst.pause()'); p.wait(1500); p.js('window.__h.inst.resume()')
    mark(p, p.trues()); p.click('[data-fo="check"]', 5600)
    r = (p.finishes() or [{}])[0]
    check('ж: timeMs без паузы', r.get('timeMs', 99999) < 1400, r.get('timeMs'))
    p.close()
    p = Page(b, 'task=0&bad=1')
    check('ж: битое задание → ctx.fail TASK_INVALID, поле пусто', [e['err']['code'] for e in p.ev('fail')] == ['TASK_INVALID'] and p.js('window.__h.field.children.length') == 0)
    p.close()
    orders = []
    for sd in (5, 5, 99):
        p = Page(b, 'task=10&seed=%d' % sd)
        orders.append([s['key'] for s in p.sts()])
        p.close()
    check('ж: одинаковый seed — одинаковый порядок, разный — разный', orders[0] == orders[1] and orders[0] != orders[2])

    # (з) все 15 заданий: текст влезает до и после решения
    over = []
    for i, t in enumerate(tasks):
        p = Page(b, 'task=%d' % i)
        bad_fit = p.js("""(() => {
          const out = [];
          const chk = (sel) => document.querySelectorAll(sel).forEach((n) => { if (n.scrollHeight > n.clientHeight + 1 || n.scrollWidth > n.clientWidth + 1) out.push(sel + ':' + n.textContent.slice(0, 30)); });
          chk('.fo-st'); chk('.fo-item-label'); chk('.fo-title'); chk('.fo-list');
          const l = document.querySelector('.fo-list').getBoundingClientRect();
          document.querySelectorAll('.fo-st').forEach((n) => { const r = n.getBoundingClientRect(); if (r.bottom > l.bottom + 1 || r.height < 44) out.push('st-size:' + Math.round(r.height)); });
          return out; })()""")
        mark(p, p.trues())
        p.click('[data-fo="check"]', 1300)
        bad_fit += p.js("""(() => { const out = []; const l = document.querySelector('.fo-list');
          if (l.scrollHeight > l.clientHeight + 1) out.push('solved-list:' + l.scrollHeight + '>' + l.clientHeight);
          return out; })()""")
        if bad_fit or p.errors:
            over.append((t['id'], bad_fit[:3], p.errors[:2]))
        p.close()
    check('з: во всех 15 заданиях тексты влезают (до и после решения), высота строки ≥ 44 px', not over, over[:4])


def main():
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(BASE + '/index.html', timeout=1); break
            except Exception:
                time.sleep(0.1)
        tasks = test_data()
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
            try:
                test_trial(b, tasks)
            finally:
                b.close()
    finally:
        srv.terminate()
        srv.wait()
    bad = [n for n, ok in results if not ok]
    print('\n%d/%d PASS' % (len(results) - len(bad), len(results)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
