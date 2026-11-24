# Проверка зоны B (испытания shirma и bagazhnik) на стенде tests/trials/harness.html.
# Запуск: сервер `python3 -m http.server 8765` из корня проекта, затем
#   python3 tests/trials/run_trials.py [base_url]
# Снимки — в tests/snapshots/B/.
import json, os, random, sys
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765').rstrip('/')
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

    def js(self, code):
        return self.pg.evaluate(code)

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


with sync_playwright() as pw:
    br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    test_shirma(br)
    test_bagazhnik(br)
    br.close()

bad = [r for r in results if not r[1]]
print('\nИтого: %d проверок, провалено %d' % (len(results), len(bad)))
sys.exit(1 if bad else 0)
