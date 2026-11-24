# Проверка зоны B (испытания shirma, bagazhnik, misterx) на стенде tests/trials/harness.html.
# Запуск: сервер `python3 -m http.server 8765` из корня проекта, затем
#   python3 tests/trials/run_trials.py [base_url] [тип ...]
# Без списка типов проверяются все. Тип traps — ловушки скептика (Ширма, Багажник).
# TRAPS_REBASELINE=1 — перезаписать эталон traps=0 (fixtures/traps0-baseline.json), только если вид машин меняли намеренно.
# Снимки — в tests/snapshots/B/.
import itertools, json, os, random, sys
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765').rstrip('/')
ONLY = set(sys.argv[2:])
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAP = os.path.join(ROOT, 'tests', 'snapshots', 'B')
os.makedirs(SNAP, exist_ok=True)

results = []

def check(name, cond, info=''):
    results.append((name, bool(cond), info))
    print(('PASS ' if cond else 'FAIL ') + name + ((' — ' + str(info)) if info and not cond else ''))


class Page:
    def __init__(self, browser, params):
        self.pg = browser.new_page(viewport={'width': 1024, 'height': 768})
        self.errors = []
        self.pg.on('pageerror', lambda e: self.errors.append('pageerror: ' + str(e)))
        self.pg.on('console', self._console)
        self.pg.goto(BASE + '/tests/trials/harness.html?' + params)
        self.pg.wait_for_function('window.__ready || window.__error', timeout=8000)
        err = self.pg.evaluate('window.__error || null')
        if err:
            self.errors.append('harness: ' + err)
        self.pg.wait_for_timeout(300)

    def _console(self, m):
        # 404 картинок допустим: испытание обязано показать заглушку
        if m.type == 'error' and 'Failed to load resource' not in m.text:
            self.errors.append('console: ' + m.text)

    def click(self, sel, wait=60):
        self.pg.click(sel)
        self.pg.wait_for_timeout(wait)

    def wait(self, ms):
        self.pg.wait_for_timeout(ms)

    def log(self):
        return self.pg.evaluate('window.__log')

    def ev(self, name, **kw):
        return [e for e in self.log() if e['ev'] == name and all(e.get(k) == v for k, v in kw.items())]

    def finishes(self):
        return [e['result'] for e in self.ev('finish')]

    def js(self, code, arg=None):
        return self.pg.evaluate(code) if arg is None else self.pg.evaluate(code, arg)

    def shot(self, name):
        self.pg.screenshot(path=os.path.join(SNAP, name))

    def close(self):
        self.pg.close()


def destroy_check(p, prefix):
    p.js('window.__h.destroy()')
    c = p.js('window.__h.counters()')
    kids = p.js('window.__h.field.children.length')
    check(prefix + ': после destroy поле пусто', kids == 0, kids)
    check(prefix + ': после destroy нет таймеров/rAF/слушателей',
          c['timeouts'] == 0 and c['intervals'] == 0 and c['rafs'] == 0 and c['listeners'] == 0, c)
    try:
        p.js('window.__h.inst.destroy()')
        ok = True
    except Exception as e:
        ok = False
    check(prefix + ': повторный destroy не бросает', ok)
    n_before = len(p.finishes())
    p.wait(2200)
    check(prefix + ': после destroy finish не вызывается', len(p.finishes()) == n_before, len(p.finishes()))


def random_taps(p, prefix, seed):
    rnd = random.Random(seed)
    for _ in range(300):
        x = rnd.uniform(32, 992)
        y = rnd.uniform(132, 732)
        p.pg.mouse.click(x, y)
    p.wait(2500)
    check(prefix + ': 300 случайных тыков — 0 ошибок в консоли', not p.errors, p.errors[:3])
    check(prefix + ': 300 случайных тыков — finish не больше 1 раза', len(p.finishes()) <= 1, len(p.finishes()))


def test_shirma(b):
    T = 'type=shirma'
    # (а) без ошибок
    p = Page(b, T + '&texts=1')
    p.shot('shirma-start.png')
    check('shirma(а): тень на ткани при первой подсказке silhouette', p.js("!!document.querySelector('.sh-shadow')"))
    check('shirma(а): первая подсказка открыта бесплатно', p.js("document.querySelectorAll('.sh-hint').length") == 1 and not p.ev('spend'))
    p.click('[data-opt="kettle"]', 1900)
    p.shot('shirma-solved.png')
    p.click('[data-opt="kettle"]', 200)
    f = p.finishes()
    check('shirma(а): finish ровно 1 раз', len(f) == 1, len(f))
    r = f[0] if f else {}
    check('shirma(а): solved, accuracy 1, mistakes 0, hintsUsed 0',
          r.get('solved') is True and r.get('accuracy') == 1 and r.get('mistakes') == 0 and r.get('hintsUsed') == 0 and r.get('powerSpent') == 0, r)
    check('shirma(а): формат TrialResult', set(r.keys()) >= {'type', 'taskId', 'level', 'solved', 'accuracy', 'hintsUsed', 'powerSpent', 'mistakes', 'timeMs', 'caseClues'} and r.get('type') == 'shirma' and r.get('taskId') == 'shirma-1-001', r)
    check('shirma(а): react(correct) 1 раз', len(p.ev('react', kind='correct')) == 1)
    check('shirma(а): нет ошибок', not p.errors, p.errors)
    p.close()

    # (б) одна ошибка
    p = Page(b, T)
    p.click('[data-opt="clock"]')
    p.click('[data-opt="clock"]')          # повторный тык по зачёркнутой — не ошибка
    p.click('[data-opt="kettle"]', 1900)
    f = p.finishes()
    r = f[0] if f else {}
    check('shirma(б): mistakes 1, accuracy 1−1/3', len(f) == 1 and r.get('mistakes') == 1 and abs(r.get('accuracy', 0) - (1 - 1 / 3)) < 1e-9, r)
    check('shirma(б): react(mistake) 1 раз', len(p.ev('react', kind='mistake')) == 1, p.ev('react'))
    check('shirma(б): звук wrong', len(p.ev('sfx', id='wrong')) == 1)
    p.close()

    # (в) подсказки тратят силу; при нуле ничего не списывается
    p = Page(b, T + '&power=3')
    for _ in range(4):
        p.click('[data-sh="hint"]')
    spends = p.ev('spend')
    check('shirma(в): 3 подсказки списали по 1, 4-я отказ', [s['ok'] for s in spends] == [True, True, True, False], spends)
    check('shirma(в): сила 0, ctx.hint 3 раза', p.js('window.__h.getPower()') == 0 and len(p.ev('hint')) == 3)
    check('shirma(в): открыто 4 подсказки (1 бесплатная + 3)', p.js("document.querySelectorAll('.sh-hint').length") == 4)
    check('shirma(в): показано «нет силы»', p.js("document.querySelector('.sh-msg').classList.contains('is-on')"))
    p.wait(2200)
    check('shirma(в): «нет силы» скрыто через 2 с', not p.js("document.querySelector('.sh-msg').classList.contains('is-on')"))
    p.click('[data-opt="kettle"]', 1900)
    r = (p.finishes() or [{}])[0]
    check('shirma(в): hintsUsed 3, powerSpent 3', r.get('hintsUsed') == 3 and r.get('powerSpent') == 3, r)
    p.close()

    p = Page(b, T + '&power=0')
    p.click('[data-sh="hint"]')
    check('shirma(в): при силе 0 ничего не списано', p.js('window.__h.getPower()') == 0 and [s['ok'] for s in p.ev('spend')] == [False] and not p.ev('hint'))
    p.close()

    p = Page(b, T + '&power=10')
    for _ in range(6):
        p.click('[data-sh="hint"]')
    check('shirma(в): подсказки кончились — кнопка неактивна, лишнего не списано',
          p.js("document.querySelector('.sh-hintbtn').classList.contains('is-off')") and len(p.ev('spend')) == 4 and p.js('window.__h.getPower()') == 6)
    check('shirma(в): поздняя silhouette — чёткая тень', p.js("!!document.querySelector('.sh-shadow.is-sharp')"))
    p.close()

    # (г) destroy посреди ожиданий (сообщение + раскрытие)
    p = Page(b, T + '&power=0')
    p.click('[data-sh="hint"]')
    p.click('[data-opt="kettle"]', 100)
    destroy_check(p, 'shirma(г)')
    p.close()

    # (д) 300 случайных тыков (задание 2 — картинок нет, заглушки)
    p = Page(b, T + '&task=1&power=2')
    check('shirma(д): заглушка-буква вместо картинки', p.js("document.querySelectorAll('.sh-letter').length") == 4)
    random_taps(p, 'shirma(д)', 1)
    p.close()

    # доп.: пауза не входит во время, битое задание → fail
    p = Page(b, T)
    p.js('window.__h.inst.pause()')
    p.wait(1500)
    p.js('window.__h.inst.resume()')
    p.click('[data-opt="kettle"]', 1900)
    r = (p.finishes() or [{}])[0]
    check('shirma(доп): timeMs без паузы', r.get('timeMs', 99999) < 1400, r.get('timeMs'))
    p.close()
    p = Page(b, T + '&bad=1')
    check('shirma(доп): битое задание → ctx.fail TASK_INVALID', [e['err']['code'] for e in p.ev('fail')] == ['TASK_INVALID'] and p.js('window.__h.field.children.length') == 0)
    p.close()


def test_bagazhnik(b):
    T = 'type=bagazhnik'
    # (а) без ошибок
    p = Page(b, T + '&texts=1')
    p.shot('bagazhnik-start.png')
    check('bagazhnik(а): 6 машин', p.js("document.querySelectorAll('.bz-spot').length") == 6)
    p.click('[data-car="c3"]')
    p.click('[data-bz="inspect"]', 400)
    p.shot('bagazhnik-inspect.png')
    p.click('[data-bz="choose"]', 1200)
    p.shot('bagazhnik-found.png')
    p.wait(700)
    f = p.finishes()
    r = f[0] if f else {}
    check('bagazhnik(а): finish ровно 1 раз', len(f) == 1, len(f))
    check('bagazhnik(а): solved, accuracy 1, mistakes 0', r.get('solved') is True and r.get('accuracy') == 1 and r.get('mistakes') == 0, r)
    check('bagazhnik(а): формат TrialResult', r.get('type') == 'bagazhnik' and r.get('taskId') == 'bagazhnik-1-001' and r.get('caseClues') == [] and isinstance(r.get('timeMs'), int), r)
    check('bagazhnik(а): осмотр = 1 подсказка', r.get('hintsUsed') == 1 and r.get('powerSpent') == 1, r)
    check('bagazhnik(а): react(correct), звук trunk', len(p.ev('react', kind='correct')) == 1 and len(p.ev('sfx', id='trunk')) == 1)
    check('bagazhnik(а): нет ошибок', not p.errors, p.errors)
    p.close()

    # без осмотра — чистое решение
    p = Page(b, T)
    p.click('[data-car="c3"]')
    p.click('[data-bz="choose"]', 1900)
    r = (p.finishes() or [{}])[0]
    check('bagazhnik(а2): без осмотра hintsUsed 0, powerSpent 0', r.get('hintsUsed') == 0 and r.get('powerSpent') == 0 and r.get('solved') is True, r)
    p.close()

    # (б) одна ошибка
    p = Page(b, T)
    p.click('[data-car="c1"]')
    p.click('[data-bz="choose"]', 300)
    p.click('[data-car="c1"]')                # проверенная машина не выбирается
    p.click('[data-bz="choose"]', 200)
    check('bagazhnik(б): проверенная машина больше не выбирается', len(p.ev('sfx', id='trunk')) == 1 and len(p.ev('react', kind='mistake')) == 1)
    p.click('[data-car="c3"]')
    p.click('[data-bz="choose"]', 1900)
    f = p.finishes()
    r = f[0] if f else {}
    check('bagazhnik(б): mistakes 1, accuracy 0.75', len(f) == 1 and r.get('mistakes') == 1 and r.get('accuracy') == 0.75, r)
    check('bagazhnik(б): звук wrong', len(p.ev('sfx', id='wrong')) == 1)
    p.close()

    # (в) осмотры тратят силу; при нуле ничего не списывается; повторный осмотр бесплатен
    p = Page(b, T + '&power=3')
    for c in ['c1', 'c2', 'c4']:
        p.click('[data-car="%s"]' % c)
        p.click('[data-bz="inspect"]')
    p.click('[data-car="c5"]')
    p.click('[data-bz="inspect"]')
    spends = p.ev('spend')
    check('bagazhnik(в): 3 осмотра по 1, 4-й отказ', [s['ok'] for s in spends] == [True, True, True, False], spends)
    check('bagazhnik(в): сила 0, показано «нет силы»', p.js('window.__h.getPower()') == 0 and p.js("document.querySelector('.bz-info').classList.contains('is-bad')"))
    p.click('[data-car="c1"]')
    p.click('[data-bz="inspect"]')
    check('bagazhnik(в): повторный осмотр бесплатен', len(p.ev('spend')) == 4 and 'bag.nothing' in p.js("document.querySelector('.bz-info').textContent"))
    p.click('[data-car="c3"]')
    p.click('[data-bz="choose"]', 1900)
    r = (p.finishes() or [{}])[0]
    check('bagazhnik(в): hintsUsed 3, powerSpent 3', r.get('hintsUsed') == 3 and r.get('powerSpent') == 3, r)
    p.close()

    # звук стука при осмотре цели с уликой sound
    p = Page(b, T + '&task=1')
    p.click('[data-car="c1"]')
    p.click('[data-bz="inspect"]')
    check('bagazhnik(в): осмотр цели с sound → knock', len(p.ev('sfx', id='knock')) == 1)
    p.close()

    # (г) destroy посреди ожиданий
    p = Page(b, T + '&power=0')
    p.click('[data-car="c1"]')
    p.click('[data-bz="inspect"]')
    p.click('[data-car="c3"]')
    p.click('[data-bz="choose"]', 100)
    destroy_check(p, 'bagazhnik(г)')
    p.close()

    # (д) 300 случайных тыков
    p = Page(b, T + '&task=1&power=2')
    random_taps(p, 'bagazhnik(д)', 2)
    p.close()

    # доп.: битое задание
    p = Page(b, T + '&bad=1')
    check('bagazhnik(доп): битое задание → ctx.fail TASK_INVALID', [e['err']['code'] for e in p.ev('fail')] == ['TASK_INVALID'] and p.js('window.__h.field.children.length') == 0)
    p.close()



# ---------- Мистер Икс ----------
MX_FIX = os.path.join(ROOT, 'tests', 'trials', 'fixtures', 'misterx.json')


def mx_solve(pl, limit=2):
    # Перебор с отсечением по правилам rule: решения таблицы целиком (тест-решатель как 2.6)
    people = [q['id'] for q in pl['people']]
    cats = [(c['key'], [v['id'] for v in c['values']]) for c in pl['categories']]
    rules = [k['rule'] for k in pl['clues']]
    sols, assign = [], {}

    def ok(r):
        if r[0] in ('is', 'not'):
            _, q, c, v = r
            return c not in assign or (assign[c][q] == v) == (r[0] == 'is')
        _, c1, v1, c2, v2 = r
        if c1 not in assign or c2 not in assign:
            return True
        q = [x for x in people if assign[c1][x] == v1][0]
        return (assign[c2][q] == v2) == (r[0] == 'link')

    def rec(i):
        if len(sols) >= limit:
            return
        if i == len(cats):
            sols.append({q: {k: assign[k][q] for k, _ in cats} for q in people})
            return
        k, vals = cats[i]
        for perm in itertools.permutations(vals):
            assign[k] = dict(zip(people, perm))
            if all(ok(r) for r in rules):
                rec(i + 1)
            del assign[k]
    rec(0)
    return sols


def mx_pick(p, answer):
    for k, v in answer.items():
        p.click('[data-mx-chip="%s:%s"]' % (k, v), 30)


def mx_cell(p, r, j, times=1):
    for _ in range(times):
        p.click('[data-mx-cell="%d:%d"]' % (r, j), 30)


def mx_cls(p, r, j):
    return p.js("document.querySelector('[data-mx-cell=\"%d:%d\"]').className" % (r, j))


def test_misterx(b):
    T = 'type=misterx'
    L1 = T + '&task=0&level=1'
    L3 = T + '&task=1&level=3'
    fx = json.load(open(MX_FIX, encoding='utf-8'))
    for t in fx['tasks']:
        sols = mx_solve(t['payload'])
        check('misterx(фикстуры): %s — решение единственное и совпадает с solution' % t['id'],
              len(sols) == 1 and sols[0] == t['payload']['solution'], len(sols))
    S1 = fx['tasks'][0]['payload']['solution']['x']
    S3 = fx['tasks'][1]['payload']['solution']['x']

    # (а) верный ответ сразу
    p = Page(b, L1 + '&texts=1')
    p.shot('misterx-l1-start.png')
    check('misterx(а): таблица 3×9, улик 6, чипов 9',
          p.js("document.querySelectorAll('.mx-cell').length") == 27 and p.js("document.querySelectorAll('.mx-clue').length") == 6
          and p.js("document.querySelectorAll('.mx-chip').length") == 9)
    check('misterx(а): «Ответить» неактивна, пока выбраны не все', p.js("document.querySelector('.mx-submit').classList.contains('is-off')"))
    p.click('[data-mx="submit"]')
    check('misterx(а): неполный ответ не считается', not p.ev('react') and not p.finishes())
    mx_pick(p, S1)
    check('misterx(а): все выбраны — «Ответить» активна', not p.js("document.querySelector('.mx-submit').classList.contains('is-off')"))
    p.click('[data-mx="submit"]', 1500)
    p.shot('misterx-solved.png')
    p.wait(500)
    p.pg.click('[data-mx="submit"]', force=True)    # под раскрытием: тык не должен дать второй finish
    p.wait(200)
    f = p.finishes()
    check('misterx(а): finish ровно 1 раз', len(f) == 1, len(f))
    r = f[0] if f else {}
    check('misterx(а): solved, accuracy 1, mistakes 0, hintsUsed 0',
          r.get('solved') is True and r.get('accuracy') == 1 and r.get('mistakes') == 0 and r.get('hintsUsed') == 0 and r.get('powerSpent') == 0, r)
    check('misterx(а): формат TrialResult', set(r.keys()) >= {'type', 'taskId', 'level', 'solved', 'accuracy', 'hintsUsed', 'powerSpent', 'mistakes', 'timeMs', 'caseClues'}
          and r.get('type') == 'misterx' and r.get('taskId') == 'misterx-1-001' and r.get('level') == 1 and r.get('caseClues') == [] and isinstance(r.get('timeMs'), int), r)
    check('misterx(а): react(correct) 1 раз, mistake 0', len(p.ev('react', kind='correct')) == 1 and not p.ev('react', kind='mistake'))
    check('misterx(а): раскрытие показано, текст mx.solved', 'Мистер Икс раскрыт' in (p.js("(document.querySelector('.mx-reveal-title')||{}).textContent") or ''))
    check('misterx(а): нет ошибок', not p.errors, p.errors)
    p.close()

    # (б) один неверный ответ, потом верный
    p = Page(b, L1 + '&texts=1')
    wrong = dict(S1)
    wrong['job'] = 'pilot'
    mx_pick(p, wrong)
    p.click('[data-mx="submit"]', 200)
    msg = p.js("document.querySelector('.mx-ans-msg').textContent")
    check('misterx(б): сообщение mx.partial «Верно 2 из 3»', 'Верно 2 из 3' in msg and p.js("document.querySelector('.mx-answer').classList.contains('has-msg')"), msg)
    p.click('[data-mx="submit"]', 100)              # тот же ответ повторно — не ошибка
    check('misterx(б): тот же неверный ответ повторно не считается', len(p.ev('react', kind='mistake')) == 1)
    p.click('[data-mx-chip="job:%s"]' % S1['job'])
    check('misterx(б): смена ответа убирает сообщение', not p.js("document.querySelector('.mx-answer').classList.contains('has-msg')"))
    p.click('[data-mx="submit"]', 2100)
    f = p.finishes()
    r = f[0] if f else {}
    check('misterx(б): finish 1 раз, solved, mistakes 1, accuracy 0.75',
          len(f) == 1 and r.get('solved') is True and r.get('mistakes') == 1 and r.get('accuracy') == 0.75, r)
    check('misterx(б): react(mistake) 1 раз, звук wrong 1 раз', len(p.ev('react', kind='mistake')) == 1 and len(p.ev('sfx', id='wrong')) == 1, p.ev('react'))
    check('misterx(б): нет ошибок', not p.errors, p.errors)
    p.close()

    # (в) подсказки тратят силу; при нуле ничего не списывается
    p = Page(b, L1 + '&power=2')
    for _ in range(3):
        p.click('[data-mx="hint"]')
    spends = p.ev('spend')
    check('misterx(в): 2 подсказки по 1, 3-я отказ', [s['ok'] for s in spends] == [True, True, False]
          and all(s['reason'] == 'misterx' for s in spends), spends)
    check('misterx(в): сила 0, ctx.hint(reveal) 2 раза', p.js('window.__h.getPower()') == 0 and [h['kind'] for h in p.ev('hint')] == ['reveal', 'reveal'])
    check('misterx(в): открыто 2 верные клетки в строке Икс', p.js("document.querySelectorAll('[data-mx-cell^=\"0:\"].is-h').length") == 2)
    check('misterx(в): показано mx.noPower', p.js("document.querySelector('.mx-msg').classList.contains('is-on')") and p.js("document.querySelector('.mx-msg').textContent") == 'mx.noPower')
    p.wait(2200)
    check('misterx(в): mx.noPower скрыто через 2 с', not p.js("document.querySelector('.mx-msg').classList.contains('is-on')"))
    p.close()

    p = Page(b, L1 + '&power=0')
    p.click('[data-mx="hint"]')
    check('misterx(в): при силе 0 ничего не списано', p.js('window.__h.getPower()') == 0 and [s['ok'] for s in p.ev('spend')] == [False] and not p.ev('hint')
          and p.js("document.querySelectorAll('.mx-cell.is-h').length") == 0)
    p.close()

    p = Page(b, L1 + '&power=10')
    for _ in range(4):
        p.click('[data-mx="hint"]')
    check('misterx(в): всё открыто — кнопка неактивна (mx.noMoreHints), лишнего не списано',
          p.js("document.querySelector('.mx-hintbtn').classList.contains('is-off')") and 'mx.noMoreHints' in p.js("document.querySelector('.mx-hintbtn').textContent")
          and len(p.ev('spend')) == 3 and p.js('window.__h.getPower()') == 7)
    cells = p.js("[...document.querySelectorAll('[data-mx-cell^=\"0:\"].is-h')].map(c => c.getAttribute('data-mx-cell'))")
    check('misterx(в): подсказки открыли именно верные клетки', sorted(cells) == ['0:%d' % j for j in [1, 5, 6]], cells)
    mx_cell(p, 0, 1)
    check('misterx(в): клетка от подсказки закреплена', 'is-h' in mx_cls(p, 0, 1))
    check('misterx(в): подсказки выбрали ответ — «Ответить» активна', not p.js("document.querySelector('.mx-submit').classList.contains('is-off')"))
    p.click('[data-mx="submit"]', 2100)
    r = (p.finishes() or [{}])[0]
    check('misterx(в): hintsUsed 3, powerSpent 3, solved', r.get('hintsUsed') == 3 and r.get('powerSpent') == 3 and r.get('solved') is True, r)
    p.close()

    # порядок подсказок зависит только от seed (тест 3.7)
    order = []
    for _ in range(2):
        p = Page(b, L3 + '&power=1')
        p.click('[data-mx="hint"]')
        order.append(p.js("document.querySelector('.mx-cell.is-h').getAttribute('data-mx-cell')"))
        p.close()
    check('misterx(в): одинаковый seed — та же подсказка', order[0] == order[1], order)

    # заметки: цикл пусто → ✗ → ✓ → пусто и авто-✗ (уровень 3)
    p = Page(b, L3 + '&texts=1&power=3')
    p.shot('misterx-l3-start.png')
    check('misterx(з): уровень 3 — 5×20 клеток', p.js("document.querySelectorAll('.mx-cell').length") == 100)
    small = p.js("[...document.querySelectorAll('.mx-cell')].filter(c => { const r = c.getBoundingClientRect(); return r.width < 30 || r.height < 30; }).length")
    check('misterx(з): все клетки не меньше 30×30', small == 0, small)
    out = p.js("""(() => { const f = document.getElementById('field').getBoundingClientRect(); return [...document.querySelectorAll('.mx-table > div, .mx-chip, .mx-submit, .mx-hintbtn')]
      .filter(c => { const r = c.getBoundingClientRect(); return r.left < f.left - 0.5 || r.right > f.right + 0.5 || r.top < f.top - 0.5 || r.bottom > f.bottom + 0.5; }).length; })()""")
    check('misterx(з): таблица и панель ответа целиком в поле', out == 0, out)
    tbl = p.js("(() => { const t = document.querySelector('.mx-table'); return [t.scrollWidth, t.clientWidth, t.scrollHeight, t.clientHeight]; })()")
    check('misterx(з): таблица без прокрутки', tbl[0] <= tbl[1] and tbl[2] <= tbl[3], tbl)
    mx_cell(p, 2, 6)
    check('misterx(з): 1 тык — ✗', 'is-x' in mx_cls(p, 2, 6))
    mx_cell(p, 2, 6)
    n_ax = p.js("document.querySelectorAll('.mx-cell.is-ax').length")
    check('misterx(з): 2 тыка — ✓ и 8 авто-✗ (строка в категории + столбец)', 'is-v' in mx_cls(p, 2, 6) and n_ax == 8
          and 'is-ax' in mx_cls(p, 2, 5) and 'is-ax' in mx_cls(p, 0, 6) and 'is-ax' not in mx_cls(p, 2, 10), n_ax)
    mx_cell(p, 2, 6)
    check('misterx(з): 3 тыка — пусто, авто-✗ сняты', mx_cls(p, 2, 6) == 'mx-cell' and p.js("document.querySelectorAll('.mx-cell.is-ax').length") == 0)
    check('misterx(з): заметки бесплатны', not p.ev('spend') and not p.ev('hint'))
    # сцена с заметками для снимка
    for (r, j) in [(1, 4), (3, 2), (4, 10), (1, 18)]:
        mx_cell(p, r, j, 2)
    for (r, j) in [(2, 3), (2, 15), (2, 16), (0, 13), (0, 0)]:
        mx_cell(p, r, j, 1)
    p.click('[data-mx="hint"]', 600)
    for i in [1, 4, 9]:
        p.click('[data-mx-clue="%d"]' % i, 30)
    check('misterx(з): улика зачёркивается тыком', p.js("document.querySelectorAll('.mx-clue.is-used').length") == 3)
    p.js("document.querySelector('.mx-clues').scrollTop = 0")
    p.wait(100)
    p.shot('misterx-l3-notes.png')
    check('misterx(з): нет ошибок', not p.errors, p.errors)
    p.close()

    # уровень 3: решение целиком
    p = Page(b, L3)
    mx_pick(p, S3)
    p.click('[data-mx="submit"]', 2100)
    r = (p.finishes() or [{}])[0]
    check('misterx(з): уровень 3 решается, level 3', r.get('solved') is True and r.get('level') == 3 and r.get('taskId') == 'misterx-3-001', r)
    p.close()

    # (г) destroy посреди ожиданий (сообщение + раскрытие)
    p = Page(b, L1 + '&power=0')
    p.click('[data-mx="hint"]')
    mx_pick(p, S1)
    p.click('[data-mx="submit"]', 100)
    destroy_check(p, 'misterx(г)')
    p.close()

    # (д) 300 случайных тыков
    p = Page(b, L3 + '&power=2&texts=1')
    random_taps(p, 'misterx(д)', 3)
    p.close()
    p = Page(b, L1 + '&power=2')
    random_taps(p, 'misterx(д, ур.1)', 4)
    p.close()

    # доп.: пауза не входит во время, битое задание → fail
    p = Page(b, L1)
    p.js('window.__h.inst.pause()')
    p.wait(1500)
    p.js('window.__h.inst.resume()')
    mx_pick(p, S1)
    p.click('[data-mx="submit"]', 2100)
    r = (p.finishes() or [{}])[0]
    check('misterx(доп): timeMs без паузы', r.get('timeMs', 99999) < 1400, r.get('timeMs'))
    p.close()
    p = Page(b, L1 + '&bad=1')
    check('misterx(доп): битое задание → ctx.fail TASK_INVALID', [e['err']['code'] for e in p.ev('fail')] == ['TASK_INVALID'] and p.js('window.__h.field.children.length') == 0)
    p.close()


# ---------- Ловушки скептика (ctx.traps, Т-08, тест 3.2) ----------
TR_BASE = os.path.join(ROOT, 'tests', 'trials', 'fixtures', 'traps0-baseline.json')
FIX = lambda n: json.load(open(os.path.join(ROOT, 'tests', 'trials', 'fixtures', n), encoding='utf-8'))
NOTHING = 'Ничего необычного'
TRAP_MARK = {'sag': 'rotate(-2 ', 'fog': '#d6dde8', 'track': '#b59a74'}


def shirma_hints(b, params):
    p = Page(b, 'type=shirma&texts=1&power=20&' + params)
    for _ in range(8):
        p.click('[data-sh="hint"]', 30)
    hints = p.js("[...document.querySelectorAll('.sh-hint')].map(li => li.textContent)")
    return p, hints


def bag_state(b, params):
    p = Page(b, 'type=bagazhnik&texts=1&power=99&' + params)
    order = p.js("[...document.querySelectorAll('.bz-spot')].map(s => s.getAttribute('data-car'))")
    svg = p.js("Object.fromEntries([...document.querySelectorAll('.bz-spot')].map(s => [s.getAttribute('data-car'), s.querySelector('.bz-carwrap').innerHTML]))")
    info = {}
    for c in order:
        p.click('[data-car="%s"]' % c, 20)
        p.click('[data-bz="inspect"]', 20)
        info[c] = p.js("document.querySelector('.bz-info').textContent")
    return p, {'order': order, 'svg': svg, 'info': info}


# Прогон испытания в той же странице с другим seed: [{trap, hints|cars}] для проверки свойств.
# Генератор — игровой createRng (mulberry32) из src/core/rng.js, seed как в trial-host: hashSeed(seed выпуска, id задания)
SEED_LOOP = """async ([type, n, mutate]) => {
  const h = window.__h, out = [];
  const { createRng, hashSeed } = await import('/src/core/rng.js');
  for (let s = 1; s <= n; s++) {
    const ctx = Object.assign({}, h.ctx, { rng: createRng(hashSeed(s, h.task.id)), traps: 1, finish() {}, fail(e) { out.push({ fail: e }); } });
    // подмена текстов признака: notrait — ключа нет ('[key]', как ContentLoader); trait — есть, вид smell; badkind — вид silhouette
    if (mutate === 'notrait' || mutate === 'trait' || mutate === 'badkind') ctx.text = (k, v) => {
      if (/\.trait$/.test(k)) return mutate === 'notrait' ? '[' + k + ']' : 'trait-text';
      if (/\.traitKind$/.test(k)) return mutate === 'trait' ? 'smell' : 'silhouette';
      return h.ctx.text(k, v);
    };
    const task = JSON.parse(JSON.stringify(h.task));
    if (mutate === 'fake') task.payload.hints[2].fake = true;
    const before = JSON.stringify(task);
    const inst = h.TRIALS[type].create(ctx), div = document.createElement('div');
    inst.start(div, task, 1);
    out.push({ trap: inst.trap, hints: inst.hints, cars: inst.cars, same: JSON.stringify(task) === before });
    inst.destroy();
  }
  return out;
}"""


def test_traps(b):
    base = json.load(open(TR_BASE, encoding='utf-8'))
    if os.environ.get('TRAPS_REBASELINE') == '1':
        print('TRAPS_REBASELINE=1: эталон traps=0 перезаписывается')
    rebase = {'shirma': {}, 'bagazhnik': {}}
    texts = json.load(open(os.path.join(ROOT, 'data', 'texts.json'), encoding='utf-8'))['texts']
    sample = FIX('texts-sample.json')['texts']
    trap_texts = FIX('texts-traps.json')['texts']
    check('traps: тексты ловушек — 8 ключей trap.shirma.1…8 с {item}',
          sorted(trap_texts) == sorted('trap.shirma.%d' % i for i in range(1, 9)) and all('{item}' in v for v in trap_texts.values()))

    # --- Ширма ---
    sh = FIX('shirma.json')['tasks']
    for i, t in enumerate(sh):
        pl = t['payload']
        p, h0 = shirma_hints(b, 'task=%d&traps=0' % i)
        rebase['shirma'][str(i)] = h0
        check('traps-shirma[%d]: traps=0 — подсказки как до изменений' % i, h0 == base['shirma'][str(i)], h0)
        p.close()
        p, h1 = shirma_hints(b, 'task=%d&traps=1' % i)
        tr = p.js('window.__h.inst.trap')
        check('traps-shirma[%d]: traps=1 — подсказок на 1 больше' % i, len(h1) == len(h0) + 1, (len(h0), len(h1)))
        check('traps-shirma[%d]: первая (бесплатная) подсказка прежняя' % i, h1[:1] == h0[:1], h1[:1])
        pos = (tr or {}).get('pos', -1)
        rest = h1[:pos] + h1[pos + 1:] if pos >= 0 else None
        check('traps-shirma[%d]: ровно одна новая подсказка, остальные по порядку прежние' % i, pos >= 1 and rest == h0, (pos, h1))
        decoy = (tr or {}).get('decoy')
        label = sample.get('item.' + str(decoy), '?')
        new = h1[pos] if 0 <= pos < len(h1) else ''
        trait = texts.get('item.%s.trait' % decoy)
        check('traps-shirma[%d]: ложная — о неверном варианте (%s), не об ответе %s' % (i, decoy, pl['answer']),
              decoy in pl['options'] and decoy != pl['answer'] and sample['item.' + pl['answer']].lower() not in new.lower(), new)
        if trait:      # основной путь: признак обманки без названия, вид из traitKind
            kind = texts.get('item.%s.traitKind' % decoy)
            check('traps-shirma[%d]: текст — признак item.%s.trait, без названия, вид %s' % (i, decoy, kind),
                  tr.get('source') == 'trait' and new == sample['shirma.kind.' + kind] + trait and label.lower() not in new.lower(), new)
        else:          # запасной путь: шаблон trap.shirma.N
            check('traps-shirma[%d]: признака нет — запасной шаблон с названием' % i,
                  tr.get('source') == 'template' and label in new and '[' not in new, new)
        check('traps-shirma[%d]: ловушка выглядит как подсказка (тот же класс, иконка)' % i,
              p.js("(() => { const li = document.querySelectorAll('.sh-hint')[%d]; return li.className === 'sh-hint' && !!li.querySelector('.sh-hint-ic svg'); })()" % pos))
        check('traps-shirma[%d]: задание из пула не изменено' % i, p.js('window.__h.task.payload.hints.length') == len(pl['hints']))
        if i == 0:
            # снимок: ловушка видна в списке (прокрутка к ней)
            p.js("(() => { const ul = document.querySelector('.sh-hints'), li = ul.querySelectorAll('.sh-hint')[%d]; ul.scrollTop = li.offsetTop - ul.offsetTop - 70; })()" % pos)
            p.wait(100)
            p.shot('trap-shirma.png')
        p.click('[data-opt="%s"]' % pl['answer'], 1900)
        r = (p.finishes() or [{}])[0]
        check('traps-shirma[%d]: решается, hintsUsed = число платных подсказок' % i,
              r.get('solved') is True and r.get('hintsUsed') == len(h1) - 1, r)
        check('traps-shirma[%d]: нет ошибок' % i, not p.errors, p.errors)
        p.close()
        p, h2 = shirma_hints(b, 'task=%d&traps=1' % i)
        check('traps-shirma[%d]: тот же seed — та же ловушка' % i, h2 == h1 and p.js('window.__h.inst.trap') == tr)
        p.close()

    # свойства на 60 seed: позиция ≥ 1, обманка ≠ ответ, вид не silhouette; ловушка поверх fake уровня
    p = Page(b, 'type=shirma&task=0')
    pl = sh[0]['payload']
    runs = p.js(SEED_LOOP, ['shirma', 60, ''])
    okk = all(r['trap'] and 1 <= r['trap']['pos'] <= len(pl['hints']) and r['trap']['decoy'] != pl['answer'] and r['trap']['decoy'] in pl['options']
              and len(r['hints']) == len(pl['hints']) + 1 and r['hints'][0] == pl['hints'][0] and r['hints'][r['trap']['pos']]['kind'] != 'silhouette'
              and r['same'] for r in runs)
    check('traps-shirma(60 seed): позиция после первой, обманка ≠ ответ, не silhouette, задание не тронуто', okk)
    check('traps-shirma(60 seed): ловушка ложится на разные места и обманки',
          len(set(r['trap']['pos'] for r in runs)) > 1 and len(set(r['trap']['decoy'] for r in runs)) == len(pl['options']) - 1)
    # оба пути текста при любом наличии ключей в data: признака нет → шаблон; есть → признак и его вид
    runs = p.js(SEED_LOOP, ['shirma', 60, 'notrait'])
    check('traps-shirma(нет признака): запасные шаблоны trap.shirma.N с {item}',
          all(r['trap']['source'] == 'template' and r['trap']['textKey'].startswith('trap.shirma.')
              and r['hints'][r['trap']['pos']]['vars']['item'] for r in runs)
          and len(set(r['trap']['textKey'] for r in runs)) == 8)
    runs = p.js(SEED_LOOP, ['shirma', 30, 'trait'])
    check('traps-shirma(есть признак): ключ item.<обманка>.trait, вид из traitKind, без подстановки',
          all(r['trap']['source'] == 'trait' and r['trap']['textKey'] == 'item.%s.trait' % r['trap']['decoy']
              and r['trap']['kind'] == 'smell' and 'vars' not in r['hints'][r['trap']['pos']] for r in runs))
    runs = p.js(SEED_LOOP, ['shirma', 30, 'badkind'])
    check('traps-shirma(вид silhouette/неизвестный): берётся вид шаблона, не silhouette',
          all(r['trap']['source'] == 'trait' and r['trap']['kind'] in ('sound', 'warmth', 'detail', 'smell') for r in runs))
    runs = p.js(SEED_LOOP, ['shirma', 20, 'fake'])
    check('traps-shirma(fake уровня): ловушка добавляется поверх — ложных 2',
          all(len(r['hints']) == len(pl['hints']) + 1 and sum(1 for x in r['hints'] if x.get('fake')) == 2 for r in runs))
    p.close()

    # --- Багажник ---
    bz = FIX('bagazhnik.json')['tasks']
    for i, t in enumerate(bz):
        pl = t['payload']
        tgt = pl['target']
        p, s0 = bag_state(b, 'task=%d&traps=0' % i)
        rebase['bagazhnik'][str(i)] = s0
        check('traps-bag[%d]: traps=0 — раскладка, машины и улики как до изменений' % i, s0 == base['bagazhnik'][str(i)])
        p.close()
        p, s1 = bag_state(b, 'task=%d&traps=1' % i)
        tr = p.js('window.__h.inst.trap') or {}
        diff = [c for c in s0['order'] if s0['svg'][c] != s1['svg'].get(c) or s0['info'][c] != s1['info'].get(c)]
        car, kind = tr.get('car'), tr.get('kind')
        check('traps-bag[%d]: раскладка мест прежняя' % i, s1['order'] == s0['order'], s1['order'])
        check('traps-bag[%d]: изменилась ровно одна машина — обманка %s' % (i, car), diff == [car] and car != tgt, diff)
        check('traps-bag[%d]: у обманки раньше улик не было' % i, s0['info'].get(car) == NOTHING, s0['info'].get(car))
        check('traps-bag[%d]: ровно одна ложная улика, текст bag.clue.%s' % (i, kind),
              kind in TRAP_MARK and s1['info'].get(car) == texts['bag.clue.' + str(kind)], s1['info'].get(car))
        check('traps-bag[%d]: улика видна на машине (как настоящая %s)' % (i, kind),
              TRAP_MARK.get(kind, '#') in s1['svg'].get(car, '') and TRAP_MARK.get(kind, '#') not in s0['svg'].get(car, ''))
        check('traps-bag[%d]: цель %s не изменилась' % (i, tgt), s1['svg'][tgt] == s0['svg'][tgt] and s1['info'][tgt] == s0['info'][tgt])
        check('traps-bag[%d]: задание из пула не изменено' % i,
              p.js('window.__h.task.payload.cars.map(c => (c.clues || []).length)') == [len(c.get('clues') or []) for c in pl['cars']])
        if i == 0:
            p.click('[data-car="%s"]' % car, 300)
            p.shot('trap-bagazhnik.png')
        p.click('[data-car="%s"]' % car)
        p.click('[data-bz="choose"]', 300)
        p.click('[data-car="%s"]' % tgt)
        p.click('[data-bz="choose"]', 1900)
        r = (p.finishes() or [{}])[0]
        check('traps-bag[%d]: обманка пустая (ошибка), цель находится' % i, r.get('solved') is True and r.get('mistakes') == 1, r)
        check('traps-bag[%d]: нет ошибок' % i, not p.errors, p.errors)
        p.close()
        p, s2 = bag_state(b, 'task=%d&traps=1' % i)
        check('traps-bag[%d]: тот же seed — та же ловушка' % i, s2 == s1 and p.js('window.__h.inst.trap') == tr)
        p.close()

    p = Page(b, 'type=bagazhnik&task=2&level=3')
    pl = bz[2]['payload']
    empty = [c['id'] for c in pl['cars'] if c['id'] != pl['target'] and not c.get('clues')]
    runs = p.js(SEED_LOOP, ['bagazhnik', 60, ''])
    def one_ok(r):
        t = r['trap']
        if not t or t['car'] not in empty or t['kind'] not in TRAP_MARK or not r['same']:
            return False
        for c in pl['cars']:
            got = r['cars'][c['id']]['clues']
            want = len(c.get('clues') or []) + (1 if c['id'] == t['car'] else 0)
            if len(got) != want:
                return False
        return r['cars'][t['car']]['clues'] == [{'kind': t['kind'], 'textKey': 'bag.clue.' + t['kind'], 'fake': True}]
    check('traps-bag(60 seed): одна улика у пустой обманки, остальное как в задании', all(one_ok(r) for r in runs))
    check('traps-bag(60 seed): разные обманки и все 3 вида улик',
          len(set(r['trap']['car'] for r in runs)) > 3 and len(set(r['trap']['kind'] for r in runs)) == 3)
    p.close()

    if os.environ.get('TRAPS_REBASELINE') == '1':
        json.dump(rebase, open(TR_BASE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


with sync_playwright() as pw:
    br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    for name, fn in [('shirma', test_shirma), ('bagazhnik', test_bagazhnik), ('misterx', test_misterx), ('traps', test_traps)]:
        if not ONLY or name in ONLY:
            fn(br)
    br.close()

bad = [r for r in results if not r[1]]
print('\nИтого: %d проверок, провалено %d' % (len(results), len(bad)))
sys.exit(1 if bad else 0)
