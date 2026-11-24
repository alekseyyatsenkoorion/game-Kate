# Режим «Играем вдвоём» (Т-19) в игре: переключатель во вступлении, ходы по очереди, итоги, сохранение.
# Снимки — tests/snapshots/D/guest-*.png. Запуск: python3 tests/shell/guest.py (свой сервер на свободном порту 8790+).
import subprocess, time, os, json, socket, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = ROOT + '/tests/snapshots/D/'; os.makedirs(OUT, exist_ok=True)
FX = ROOT + '/tests/trials/fixtures/'
TEXTS = json.load(open(FX + 'texts-shell.json', encoding='utf-8'))
G = json.load(open(FX + 'texts-guest.json', encoding='utf-8'))
TEXTS.update(G)
BAL = json.load(open(ROOT + '/data/balance.json', encoding='utf-8'))
WIN_BONUS = (BAL.get('guest') or {}).get('winBonus', 20)


def free_port(start):
    for p in range(start, start + 60):
        with socket.socket() as s:
            try: s.bind(('127.0.0.1', p)); return p
            except OSError: continue
    raise RuntimeError('нет свободного порта')


PORT = free_port(8790)
srv = subprocess.Popen(['python3', '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1); errs = []; res = []
def check(c, msg): res.append(('PASS ' if c else 'FAIL ') + msg)
def shot(pg, name, wait=400): pg.wait_for_timeout(wait); pg.screenshot(path=OUT + name + '.png')

def boot(pg):
    pg.wait_for_function('window.__s6 && window.__s6.content && window.__s6.content.texts && window.__s6.scenes')
    pg.evaluate('(t) => Object.assign(window.__s6.content.texts, t)', TEXTS)
    pg.wait_for_timeout(300)

def jump(pg, n):
    pg.evaluate("__s6.scenes.replace('debug')"); pg.wait_for_timeout(600)
    pg.click('[data-go="%d"]' % n); pg.wait_for_timeout(800)

def payload(pg, t, l):
    tid = pg.evaluate('__s6.progress.run().taskIds[__s6.progress.run().idx]')
    return pg.evaluate("(async()=> (await __s6.content.pool('%s',%d)).find(x=>x.id==='%s').payload)()" % (t, l, tid))

def badge(pg):
    return pg.evaluate("(() => { const e = document.querySelector('.turn-badge'); return e ? [e.textContent, e.classList.contains('is-guest')] : null; })()")

def box(pg, sel):
    return pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [r.width, r.height, r.bottom]; }", sel)

# Сохранение «как у Кати» до режима «Гость»: выпуск 1 пройден, поля guest нет
OLD = {'schema': 2, 'episodes': {'1': {'firstDate': '2026-11-24', 'stars': 2, 'points': 95, 'bestPoints': 95, 'attempts': 1}},
       'power': 5, 'totalPoints': 95,
       'rivals': {k: {'points': v, 'eliminatedAfter': None} for k, v in [('agata', 80), ('elisey', 60), ('baron', 40), ('miroslava', 70), ('timur', 55)]},
       'case': {'clues': ['clue-01'], 'links': []}, 'skeptic': {'pendingTraps': 0}, 'achievements': ['first-win'],
       'openedOn': {'1': '2026-11-24'}}

try:
  with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 1024, 'height': 768}, has_touch=True, service_workers='block')
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and '404' not in m.text else None)
    pg.goto('http://localhost:%d/' % PORT); boot(pg)

    # 1) старый сейв без guest
    pg.evaluate("(o) => { localStorage.clear(); localStorage.setItem('s6:v2:progress', JSON.stringify(o)); }", OLD)
    pg.reload(); boot(pg)
    st = pg.evaluate('({ g: __s6.progress.get().guest, rec: __s6.progress.recovered, e: Object.keys(__s6.progress.get().episodes), t: __s6.progress.get().totalPoints })')
    check(st['g'] == {'enabled': False, 'points': 0} and not st['rec'] and st['e'] == ['1'] and st['t'] == 95,
          'старый сейв без guest открылся: режим выключен, выпуск 1 и очки на месте: %s' % st)
    pg.click('[data-action=season]'); pg.wait_for_timeout(700)
    pg.click('.card[data-action=ep]'); pg.wait_for_timeout(700)
    check(pg.evaluate("JSON.parse(localStorage.getItem('s6:v2:progress')).guest === undefined"), 'просмотр вступления не переписывает старый сейв')
    tg = pg.inner_text('.guest-tg')
    check(G['ui.guestToggle'] in tg and not pg.evaluate("document.querySelector('.guest-tg').classList.contains('is-on')"), 'во вступлении переключатель «%s» (выключен)' % tg)

    # 2) вступление выпуска 2 (режим теста) — включаем «Играем вдвоём»
    pg.evaluate('__s6.progress.setSettings({ test: true })')
    jump(pg, 2)
    w, h, _ = box(pg, '.guest-tg')
    check(w >= 44 and h >= 44, 'кнопка переключателя ≥ 44×44: %dx%d' % (w, h))
    check(G['ui.guestHint'] in pg.inner_text('.guest-row'), 'пояснение ui.guestHint под переключателем')
    pg.click('.guest-tg'); pg.wait_for_timeout(300)
    check(pg.evaluate('__s6.progress.get().guest.enabled') is True, 'переключатель записал progress.guest.enabled = true')
    _, _, bottom = box(pg, '[data-action=start]')
    check(bottom <= 768, 'кнопка «Начать испытание» на экране: низ %d' % bottom)
    shot(pg, 'guest-intro')
    pg.click('.guest-tg'); pg.wait_for_timeout(200)
    check(pg.evaluate('__s6.progress.get().guest.enabled') is False, 'повторный тык выключает режим')
    pg.click('.guest-tg'); pg.wait_for_timeout(200)

    # 3) Багажник 1 по очереди: Катя ошиблась, гость нашёл
    pg.click('[data-action=start]'); pg.wait_for_timeout(1300)
    check(badge(pg) == [G['ui.turnPlayer'], False], 'плашка хода: %s' % badge(pg))
    pl = payload(pg, 'bagazhnik', 1)
    wrong = [c['id'] for c in pl['cars'] if c['id'] != pl['target']][0]
    pg.click('[data-car="%s"]' % wrong); pg.wait_for_timeout(300); pg.click('[data-bz=choose]'); pg.wait_for_timeout(700)
    check(badge(pg) == [G['ui.turnGuest'], True], 'после ошибки Кати — ход гостя: %s' % badge(pg))
    pg.click('[data-car="%s"]' % pl['target']); pg.wait_for_timeout(300)
    shot(pg, 'guest-turn', 200)
    pg.click('[data-bz=choose]')
    pg.wait_for_selector('.big-stars', timeout=9000); pg.wait_for_timeout(600)
    rows = pg.evaluate("[...document.querySelectorAll('table.rivals tr')].map(r => [r.className, r.querySelector('.nm').textContent, +r.lastChild.textContent])")
    grow = [r for r in rows if r[0] == 'guest']
    want = 100 + WIN_BONUS
    check(len(rows) == 7 and len(grow) == 1 and grow[0][1] == G['ui.guest'] and grow[0][2] == want, 'в таблице строка «Гость» с %d очками: %s' % (want, grow))
    wb = pg.inner_text('.won-by')
    check(wb == G['ui.wonBy'].replace('{name}', G['ui.guestName']), 'на итогах «%s»' % wb)
    st = pg.evaluate('__s6.progress.get()')
    check(st['guest'] == {'enabled': True, 'points': want}, 'очки гостя записаны: %s' % st['guest'])
    check(st['episodes']['2']['points'] > 0 and st['episodes']['2']['stars'] >= 1, 'выпуск 2 засчитан Кате: %s' % st['episodes']['2'])
    check('guest' not in st['rivals'], 'гость не попал в соперники')
    shot(pg, 'guest-result', 2600)

    # 4) после перезагрузки
    pg.reload(); boot(pg)
    check(pg.evaluate('__s6.progress.get().guest') == {'enabled': True, 'points': want}, 'режим и очки гостя пережили перезагрузку')

    # 5) выпуск 3 (выбывание, Мистер Икс — без ходов): гость последний, но не выбывает
    pg.evaluate('__s6.progress.update((d) => { d.totalPoints = 2000; d.guest.points = 0; })')
    jump(pg, 3)
    check(pg.evaluate("document.querySelector('.guest-tg').classList.contains('is-on')"), 'во вступлении выпуска 3 режим включён')
    pg.click('[data-action=start]'); pg.wait_for_timeout(1300)
    check(badge(pg) is None, 'в Мистере Икс плашки хода нет')
    pl = payload(pg, 'misterx', 1)
    for cat, val in pl['solution'][pl['ask']].items(): pg.click('[data-mx-chip="%s:%s"]' % (cat, val)); pg.wait_for_timeout(80)
    pg.click('[data-mx=submit]')
    pg.wait_for_selector('.big-stars', timeout=12000); pg.wait_for_timeout(600)
    rows = pg.evaluate("[...document.querySelectorAll('table.rivals tr')].map(r => [r.className, !!r.querySelector('.out'), +r.lastChild.textContent])")
    st = pg.evaluate('__s6.progress.get()')
    out = [k for k, v in st['rivals'].items() if v['eliminatedAfter'] == 3]
    check(rows[-1][0] == 'guest' and not rows[-1][1] and len(out) == 1 and sum(1 for r in rows if r[1]) == 1,
          'гость последний, но выбыл соперник %s: %s' % (out, rows))
    check(st['guest']['points'] == 0 and pg.query_selector('.won-by') is None, 'за испытание без ходов гость получил 0, строки «забрал» нет')

    # 6) Scoring напрямую: гость не меняет ботов, выбывание и переигровку
    r = pg.evaluate("""() => { const S = __s6.scoring;
      return import('/src/core/rng.js').then((m) => {
        const base = __s6.progress.defaults(); base.totalPoints = 0;
        const pl = { points: 10, stars: 1, powerGain: 1, newClues: [] };
        const off = S.rivals(3, pl, base, m.createRng(m.hashSeed('rivals', 3, 1)), 0);
        const on = JSON.parse(JSON.stringify(base)); on.guest = { enabled: true, points: 0 };
        const w = S.rivals(3, pl, on, m.createRng(m.hashSeed('rivals', 3, 1)), 0);
        const big = JSON.parse(JSON.stringify(on)); big.guest.points = 5000; big.totalPoints = 1000;
        const b = S.rivals(3, pl, big, m.createRng(m.hashSeed('rivals', 3, 1)), 0);
        const noG = (t) => t.filter((x) => x.id !== 'guest').map((x) => [x.id, x.points]);
        const res = [{ guest: { solved: true, accuracy: 0.75, winner: 'guest' } }];
        return { offRep: off.playerMustReplay, onRep: w.playerMustReplay, sameBots: JSON.stringify(noG(off.table)) === JSON.stringify(noG(w.table)),
          offHasG: off.table.some((x) => x.id === 'guest'), gLast: w.table[w.table.length - 1].id, onElim: w.eliminated,
          bigFirst: b.table[0].id, bigElim: b.eliminated, gain2: S.guestGain(2, res), gain3: S.guestGain(3, [{}]) };
      }); }""")
    check(r['offRep'] and r['onRep'] and r['sameBots'] and not r['offHasG'] and r['gLast'] == 'guest' and r['onElim'] is None,
          'гость ниже Кати не спасает её от переигровки, очки ботов те же, без режима строки нет: %s' % r)
    check(r['bigFirst'] == 'guest' and r['bigElim'] not in (None, 'guest'), 'гость на 1-м месте — выбывает последний из соперников: %s' % r)
    check(r['gain2'] == 75 + WIN_BONUS and r['gain3'] == 0, 'очки гостя: Багажник 1 с accuracy 0.75 и победой = %d, без хода = 0' % r['gain2'])

    # 7) Ширма 2 (выпуск 6): Катя ошиблась, гость ошибся, Катя угадала
    jump(pg, 6)
    pg.click('[data-action=start]'); pg.wait_for_timeout(1300)
    pl = payload(pg, 'shirma', 2)
    wr = [o for o in pl['options'] if o != pl['answer']]
    pg.click('[data-opt="%s"]' % wr[0]); pg.wait_for_timeout(500)
    b1 = badge(pg)
    pg.click('[data-opt="%s"]' % wr[1]); pg.wait_for_timeout(500)
    b2 = badge(pg)
    check(b1 == [G['ui.turnGuest'], True] and b2 == [G['ui.turnPlayer'], False], 'Ширма: ход Катя → Гость → Катя')
    pg.click('[data-opt="%s"]' % pl['answer'])
    pg.wait_for_selector('.big-stars', timeout=9000); pg.wait_for_timeout(400)
    wb = pg.inner_text('.won-by')
    check(wb == G['ui.wonBy'].replace('{name}', G['ui.playerName']), 'Ширма: «%s»' % wb)
    rr = pg.evaluate('__s6.progress.get().episodes[6]')
    check(rr and rr['points'] > 0, 'выпуск 6 засчитан: %s' % rr)

    # 8) режим выключен — рамка испытания без плашки, результат без guest
    pg.evaluate('__s6.progress.update((d) => { d.guest.enabled = false; })')
    jump(pg, 2)
    pg.click('[data-action=start]'); pg.wait_for_timeout(1300)
    check(badge(pg) is None, 'режим выключен — плашки хода нет')
    pl = payload(pg, 'bagazhnik', 1)
    pg.click('[data-car="%s"]' % pl['target']); pg.wait_for_timeout(300); pg.click('[data-bz=choose]')
    pg.wait_for_selector('.big-stars', timeout=9000); pg.wait_for_timeout(400)
    rows = pg.evaluate("[...document.querySelectorAll('table.rivals tr')].map(r => r.className)")
    check('guest' not in rows and pg.query_selector('.won-by') is None, 'режим выключен — в таблице нет гостя, строки «забрал» нет')
    b.close()
finally:
    srv.terminate()
print('\n'.join(res)); print('ERRORS:', errs)
sys.exit(1 if errs or any(x.startswith('FAIL') for x in res) else 0)
