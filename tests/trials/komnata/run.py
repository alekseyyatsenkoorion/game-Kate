# Проверка испытания «Тёмная комната» (komnata) и его данных.
# Запуск из корня проекта: python3 tests/trials/komnata/run.py
# Поднимает свой сервер на 8768, гоняет Chrome (Playwright), в конце сервер останавливает.
# Снимки — tests/snapshots/B/komnata-*.png
import json, math, os, random, re, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SNAP = os.path.join(ROOT, 'tests', 'snapshots', 'B')
PORT = 8768
BASE = 'http://localhost:%d' % PORT
os.makedirs(SNAP, exist_ok=True)
RW, RH = 800, 600            # комната в поле
OX, OY = 32, 132             # поле на сцене

results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(info)) if info != '' else ''))

DATA = json.load(open(os.path.join(ROOT, 'data', 'trials', 'komnata.json'), encoding='utf-8'))
TEXTS = json.load(open(os.path.join(ROOT, 'tests', 'trials', 'fixtures', 'texts-komnata.json'), encoding='utf-8'))
CASE = json.load(open(os.path.join(ROOT, 'data', 'case.json'), encoding='utf-8'))
TASKS = DATA['tasks']

# ---------------- данные ----------------
def data_checks():
    check('данные: schema 1, type komnata', DATA.get('schema') == 1 and DATA.get('type') == 'komnata')
    check('данные: 15 заданий', len(TASKS) == 15, len(TASKS))
    for lvl, nf, light in ((1, 3, 0.14), (2, 5, 0.11), (3, 7, 0.08)):
        ts = [t for t in TASKS if t['level'] == lvl]
        check('данные: уровень %d — 5 заданий' % lvl, len(ts) == 5, len(ts))
        check('данные: уровень %d — найти %d, луч %s' % (lvl, nf, light),
              all(len(t['payload']['find']) == nf and t['payload']['light'] == light for t in ts))
    clue_ep = {c['id']: c['episode'] for c in CASE['clues']}
    ep_of = {1: 5, 2: 9, 3: 12}
    bad = []
    keys = set()
    rooms = {}
    for t in TASKS:
        p = t['payload']; tid = t['id']
        if not re.match(r'^komnata-[123]-\d{3}$', tid) or int(tid.split('-')[1]) != t['level']: bad.append(tid + ' id')
        if not os.path.exists(os.path.join(ROOT, 'assets', 'gpt', p['room'] + '.webp')): bad.append(tid + ' room')
        rooms.setdefault(t['level'], []).append(p['room'])
        if p.get('timeLimitSec') is not None: bad.append(tid + ' timeLimitSec')
        ids = [o['id'] for o in p['objects']]
        if len(set(ids)) != len(ids): bad.append(tid + ' dup id')
        if not all(re.match(r'^[a-z0-9-]+$', i) for i in ids): bad.append(tid + ' id format')
        if not all(f in ids for f in p['find']): bad.append(tid + ' find not in objects')
        dec = len(ids) - len(p['find'])
        if not 2 <= dec <= 4: bad.append(tid + ' decoys %d' % dec)
        for o in p['objects']:
            keys.add(o['labelKey'])
            if not (0 <= o['x'] <= 1 and 0 <= o['y'] <= 1 and 0.01 <= o['r'] <= 0.07): bad.append(tid + ' xyr ' + o['id'])
            if o['clue'] is not None and clue_ep.get(o['clue']) != ep_of[t['level']]: bad.append(tid + ' clue ' + str(o['clue']))
        for i, a in enumerate(p['objects']):
            for b in p['objects'][i + 1:]:
                if math.hypot(a['x'] - b['x'], (a['y'] - b['y']) * 0.75) < a['r'] + b['r']: bad.append(tid + ' overlap %s/%s' % (a['id'], b['id']))
        labs = [TEXTS.get(o['labelKey']) for o in p['objects']]
        if len(set(labs)) != len(labs): bad.append(tid + ' same labels')
    check('данные: id, комнаты, обманки 2–4, координаты, без перекрытий, улики выпусков 5/9/12', not bad, bad)
    check('данные: на каждом уровне все 3 комнаты', all(len(set(r)) == 3 for r in rooms.values()), rooms)
    ui = ['km.findTitle', 'km.hintBtn', 'km.noPower', 'km.wrong', 'km.found', 'km.progress', 'km.solved']
    miss = [k for k in list(keys) + ui if not TEXTS.get(k)]
    check('данные: все ключи есть в texts-komnata.json', not miss, miss)
    check('данные: тексты без лишних ключей', set(TEXTS) == keys | set(ui), set(TEXTS) ^ (keys | set(ui)))

# ---------------- код ----------------
def code_checks():
    src = open(os.path.join(ROOT, 'src', 'trials', 'komnata', 'komnata.js'), encoding='utf-8').read()
    css = open(os.path.join(ROOT, 'src', 'trials', 'komnata', 'komnata.css'), encoding='utf-8').read()
    code = re.sub(r'//[^\n]*', '', src)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
    banned = ['Math.random', 'roundRect', '.filter =', 'OffscreenCanvas', 'requestIdleCallback', 'localStorage',
              'fetch(', 'Intl.Segmenter', 'setTimeout', 'setInterval', 'requestAnimationFrame', 'http://', 'https://', 'import ']
    found = [b for b in banned if b in code]
    check('код: нет запрещённых API, своих таймеров, сети и импортов', not found, found)
    check('код: нет приватных полей #', not re.search(r'\bthis\.#|^\s*#\w', code, re.M))
    check('код: кириллица только в комментариях', not re.search('[а-яА-ЯёЁ]', code))
    css_code = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    check('css: без filter/blur/box-shadow-анимаций и вложенности',
          not re.search(r'(?<![-\w])filter\s*:|blur\(|@container|&', css_code) and 'box-shadow' not in ''.join(re.findall(r'@keyframes[^}]*}[^}]*}', css_code)))

# ---------------- браузер ----------------
class Page:
    def __init__(self, browser, params=''):
        self.pg = browser.new_page(viewport={'width': 1024, 'height': 768})
        self.errors = []
        self.pg.on('pageerror', lambda e: self.errors.append('pageerror: ' + str(e)))
        self.pg.on('console', lambda m: self.errors.append('console: ' + m.text) if m.type == 'error' else None)
        self.pg.goto(BASE + '/tests/trials/komnata/harness.html?' + params)
        self.pg.wait_for_function('window.__ready || window.__error', timeout=10000)
        err = self.pg.evaluate('window.__error || null')
        if err: self.errors.append('harness: ' + err)
        self.pg.wait_for_timeout(150)
    def js(self, c, arg=None): return self.pg.evaluate(c, arg)
    def log(self): return self.js('window.__log')
    def ev(self, name, **kw): return [e for e in self.log() if e['ev'] == name and all(e.get(k) == v for k, v in kw.items())]
    def finishes(self): return [e['result'] for e in self.ev('finish')]
    def click_field(self, fx, fy, wait=40):
        self.pg.mouse.click(OX + fx, OY + fy)
        self.pg.wait_for_timeout(wait)
    def tap_obj(self, o, wait=40):     # два тыка: первый ставит луч, второй — по предмету в луче
        fx, fy = o['x'] * RW, o['y'] * RH
        self.click_field(fx, fy, wait); self.click_field(fx, fy, wait)
    def hint(self):
        self.pg.click('[data-km="hint"]'); self.pg.wait_for_timeout(40)
    def shot(self, name): self.pg.screenshot(path=os.path.join(SNAP, name))
    def close(self): self.pg.close()

def objs(t, find=True):
    p = t['payload']
    return [o for o in p['objects'] if (o['id'] in p['find']) == find]

def run_browser(browser):
    t0 = TASKS[0]
    # --- старт, снимок, найти все ---
    p = Page(browser, 'task=0')
    check('стенд: загрузка без ошибок', not p.errors, p.errors)
    L = p.js('window.__h.light()')
    check('старт: фонарь в центре, радиус 0.14×800', abs(L['x'] - 400) < 1 and abs(L['y'] - 300) < 1 and L['R'] == 112, L)
    check('старт: картинка комнаты загружена', p.js('!!document.querySelector(".km-img") && document.querySelector(".km-img").naturalWidth === 2048'))
    check('старт: в списке 3 названия', p.js('document.querySelectorAll(".km-item").length') == 3)
    p.shot('komnata-l1-start.png')
    finds = objs(t0)
    p.tap_obj(finds[0])
    check('найдено: sfx star, отметка в списке', len(p.ev('sfx', id='star')) == 1 and p.js('document.querySelectorAll(".km-item.is-found").length') == 1)
    p.pg.wait_for_timeout(120)
    p.shot('komnata-found.png')
    p.tap_obj(finds[0])
    check('повторный тык по найденному — без эффекта', len(p.ev('sfx', id='star')) == 1 and not p.ev('react'))
    for o in finds[1:]: p.tap_obj(o)
    check('все найдены: react correct', p.ev('react', kind='correct') != [])
    p.pg.wait_for_timeout(1700)
    p.shot('komnata-solved.png')
    p.pg.wait_for_timeout(900)
    fs = p.finishes()
    r = fs[0] if fs else {}
    check('finish ровно 1 раз', len(fs) == 1, len(fs))
    check('результат: solved, accuracy 1, mistakes 0, hints 0', r.get('solved') is True and r.get('accuracy') == 1 and r.get('mistakes') == 0 and r.get('hintsUsed') == 0, r)
    check('результат: улика clue-07, тип и id', r.get('caseClues') == ['clue-07'] and r.get('type') == 'komnata' and r.get('taskId') == t0['id'] and r.get('level') == 1, r)
    check('результат: timeMs > 0', isinstance(r.get('timeMs'), int) and r['timeMs'] > 0, r.get('timeMs'))
    check('ввод после конца игнорируется', (p.tap_obj(objs(t0, False)[0]) or True) and not p.ev('react', kind='mistake'))
    p.pg.wait_for_timeout(2400)
    check('повторного finish нет', len(p.finishes()) == 1)
    check('без ошибок страницы (полное прохождение)', not p.errors, p.errors)
    p.close()

    # --- обманка, пустой тык, тык в темноте ---
    p = Page(browser, 'task=0')
    dec = objs(t0, False)[0]
    dx, dy = dec['x'] * RW, dec['y'] * RH
    p.click_field(40, 560)         # увести луч в пустой угол
    p.click_field(dx, dy)          # в темноте — только перенос луча
    check('тык в темноте по обманке — не ошибка, луч переехал', not p.ev('react') and abs(p.js('window.__h.light().x') - dx) < 1)
    p.click_field(dx, dy)
    check('тык по обманке в луче — mistake, react(mistake)', len(p.ev('react', kind='mistake')) == 1 and p.js('window.__h.inst.mistakes') == 1)
    p.click_field(dx, dy)
    check('та же обманка второй раз — без нового штрафа', p.js('window.__h.inst.mistakes') == 1 and len(p.ev('react', kind='mistake')) == 1)
    # пустое место: ищем точку без предметов рядом
    pts = [(x, y) for x in range(60, 760, 20) for y in range(60, 560, 20)
           if all(math.hypot(x - o['x'] * RW, y - o['y'] * RH) > o['r'] * RW * 1.2 + 30 for o in t0['payload']['objects'])]
    ex, ey = pts[len(pts) // 2]
    p.click_field(ex, ey); p.click_field(ex, ey)
    check('тык в пустоту в луче — не ошибка', p.js('window.__h.inst.mistakes') == 1 and len(p.ev('react')) == 1)
    for o in objs(t0): p.tap_obj(o)
    p.js('window.__h.tick(3000)')
    r = (p.finishes() or [{}])[0]
    check('accuracy = 1 − 0.2 × mistakes = 0.8', abs(r.get('accuracy', 0) - 0.8) < 1e-9 and r.get('mistakes') == 1, r)
    check('без ошибок страницы (обманка)', not p.errors, p.errors)
    p.close()

    # --- подсказки ---
    p = Page(browser, 'task=5&power=2')
    p.hint()
    check('подсказка: сила списана, hint(glow), свечение видно',
          p.js('window.__h.getPower()') == 1 and p.ev('hint', kind='glow') and p.js('!!document.querySelector(".km-glow")'))
    check('подсказка: spend с причиной komnata и ценой 1', p.ev('spend', ok=True, reason='komnata', n=1) != [])
    p.hint()
    check('подсказка: пока светится — повторно не тратится', p.js('window.__h.getPower()') == 1 and len(p.ev('hint')) == 1)
    p.shot('komnata-hint.png')
    p.js('window.__h.tick(2100)')
    check('подсказка: через 2 с свечение гаснет', not p.js('!!document.querySelector(".km-glow")'))
    p.hint()
    check('подсказка 2: списано, сила 0', p.js('window.__h.getPower()') == 0 and len(p.ev('hint')) == 2)
    p.js('window.__h.tick(2100)')
    p.hint()
    check('нет силы: km.noPower, ничего не списано', len(p.ev('hint')) == 2 and p.js('document.querySelector(".km-msg").textContent') == TEXTS['km.noPower'] and p.ev('spend', ok=False))
    for o in objs(TASKS[5]): p.tap_obj(o)
    check('все найдены: кнопка подсказки неактивна', p.js('document.querySelector(".km-hintbtn").classList.contains("is-off")'))
    p.js('window.__h.tick(3000)')
    r = (p.finishes() or [{}])[0]
    check('результат: hintsUsed 2, powerSpent 2, улики clue-13 и clue-14', r.get('hintsUsed') == 2 and r.get('powerSpent') == 2 and sorted(r.get('caseClues', [])) == ['clue-13', 'clue-14'], r)
    check('без ошибок страницы (подсказки)', not p.errors, p.errors)
    p.close()

    # --- destroy ---
    p = Page(browser, 'task=10&power=3')
    p.tap_obj(objs(TASKS[10])[0]); p.hint()
    p.pg.mouse.move(OX + 100, OY + 100); p.pg.mouse.down(); p.pg.mouse.move(OX + 300, OY + 200, steps=8); p.pg.mouse.up()
    p.js('window.__h.destroy()')
    c = p.js('window.__h.counters()')
    check('destroy: поле пусто', p.js('window.__h.field.children.length') == 0)
    check('destroy: нет таймеров/rAF/слушателей', c == {'timeouts': 0, 'intervals': 0, 'rafs': 0, 'listeners': 0}, c)
    ok = True
    try: p.js('window.__h.inst.destroy(); window.__h.inst.update(500); window.__h.inst.render(); window.__h.inst.onInput({action:"tap",x:0,y:0,fx:100,fy:100,target:null,t:0})')
    except Exception as e: ok = str(e)
    check('destroy: повторный destroy и вызовы после — без исключений', ok is True, ok)
    check('destroy: finish не пришёл', not p.finishes())
    check('без ошибок страницы (destroy)', not p.errors, p.errors)
    p.close()

    # --- битое задание, заглушка без картинки ---
    p = Page(browser, 'task=0&bad=1')
    f = p.ev('fail')
    check('битое задание → fail TASK_INVALID', len(f) == 1 and f[0]['err']['code'] == 'TASK_INVALID', f)
    p.close()
    p = Page(browser, 'task=3&noimg=1')
    check('нет картинки: векторная заглушка', p.js('!!document.querySelector(".km-pic.is-stub svg")') and not p.js('!!document.querySelector(".km-img")'))
    p.shot('komnata-stub.png')
    for o in objs(TASKS[3]): p.tap_obj(o)
    p.js('window.__h.tick(3000)')
    check('нет картинки: задание проходится', len(p.finishes()) == 1 and p.finishes()[0]['solved'])
    check('без ошибок страницы (заглушка)', not p.errors, p.errors)
    p.close()

    # --- все 15 заданий проходятся по координатам данных ---
    bad = []
    p = Page(browser, 'task=0')
    for i, t in enumerate(TASKS):
        if i: p.pg.goto(BASE + '/tests/trials/komnata/harness.html?task=%d' % i); p.pg.wait_for_function('window.__ready || window.__error')
        for o in objs(t):
            x, y = o['x'] * RW, o['y'] * RH
            p.js('([x,y]) => { window.__h.send("tap", x, y); window.__h.send("tap", x, y); }', [x, y])
        p.js('window.__h.tick(3000)')
        fs = p.finishes()
        if len(fs) != 1 or fs[0]['accuracy'] != 1 or not fs[0]['solved'] or fs[0]['level'] != t['level']: bad.append(t['id'])
        if i in (10,):
            p.js('window.__h.send("hold", 700, 120)'); p.pg.wait_for_timeout(1600)
    check('все 15 заданий: найти всё → finish, accuracy 1', not bad, bad)
    check('без ошибок страницы (15 заданий)', not p.errors, p.errors)
    p.close()
    p = Page(browser, 'task=12')
    p.js('window.__h.send("drag", 600, 250)')
    p.shot('komnata-l3-start.png')
    p.close()

    # --- 300 случайных касаний и перетаскиваний ---
    rnd = random.Random(7)
    errs = []
    for ti in (0, 7, 13):
        p = Page(browser, 'task=%d&power=5' % ti)
        for k in range(100):
            x, y = rnd.uniform(0, 1024), rnd.uniform(0, 768)
            kind = rnd.random()
            if kind < 0.55: p.pg.mouse.click(x, y)
            elif kind < 0.9:
                p.pg.mouse.move(x, y); p.pg.mouse.down()
                p.pg.mouse.move(rnd.uniform(0, 1024), rnd.uniform(0, 768), steps=rnd.randint(2, 6)); p.pg.mouse.up()
            else:
                p.pg.mouse.move(x, y); p.pg.mouse.down(); p.pg.wait_for_timeout(560); p.pg.mouse.up()
        p.pg.wait_for_timeout(300)
        n = len(p.finishes())
        if n > 1: errs.append('finish %d' % n)
        errs += p.errors
        p.close()
    check('300 случайных касаний/перетаскиваний — 0 ошибок', not errs, errs)

    # --- кадры при перетаскивании, процессор ×4 медленнее ---
    p = Page(browser, 'task=10')
    cdp = p.pg.context.new_cdp_session(p.pg)
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    p.pg.mouse.move(OX + 100, OY + 100); p.pg.mouse.down(); p.pg.mouse.move(OX + 120, OY + 110, steps=2)
    p.js('window.__h.fpsStart()')
    t_end = time.time() + 4
    k = 0
    while time.time() < t_end:
        a = k * 0.09
        p.pg.mouse.move(OX + 400 + 330 * math.cos(a), OY + 300 + 230 * math.sin(a * 1.3))
        k += 1
    m = p.js('window.__h.fpsStop()')
    p.pg.mouse.up()
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
    print('КАДРЫ (CPU ×4, перетаскивание фонаря 4 с): %.1f кадр/с, кадров %d, худший кадр %.0f мс, событий drag %d' % (m['fps'], m['frames'], m['worst'], k))
    check('кадры при перетаскивании (CPU ×4) ≥ 30', m['fps'] >= 30, '%.1f' % m['fps'])
    p.close()


def main():
    data_checks()
    code_checks()
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: urllib.request.urlopen(BASE + '/index.html', timeout=1); break
            except Exception: time.sleep(0.1)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
            try: run_browser(browser)
            finally: browser.close()
    finally:
        srv.terminate()
        try: srv.wait(timeout=5)
        except Exception: srv.kill()
    bad = [n for n, ok in results if not ok]
    print('\nИТОГО: %d проверок, провалено %d' % (len(results), len(bad)))
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
