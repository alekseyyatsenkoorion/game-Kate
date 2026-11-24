# Группа 4 tests.md — правила: Scoring, соперники, скептик, DayLock, мешок заданий, pickText, звания.
# Запуск: python3 tests/core/rules.py  (свой сервер, порт из S6_PORT или 8790)
import json, os
from playwright.sync_api import sync_playwright
from _s6 import ROOT, Server, Checks, launch, boot, fix_date

C = Checks('Группа 4 — правила')
CASES = json.load(open(os.path.join(ROOT, 'tests', 'core', 'scoring.cases.json'), encoding='utf-8'))
srv = Server()
try:
  with sync_playwright() as p:
    b = launch(p)
    pg = b.new_page(viewport={'width': 1024, 'height': 768}, has_touch=True)
    C.watch(pg)
    boot(pg, srv.url)
    pg.evaluate("__s6.progress.reset(); __s6.progress.setSettings({test:false})")

    # ---- 4.1 SCORE_INPUT ----
    bad = pg.evaluate("""() => {
      const b = __s6.content.trialBalance('shirma', 1), ok = { solved: true, accuracy: 1, hintsUsed: 0, mistakes: 0, timeMs: 1, level: 1 };
      const code = (fn) => { try { fn(); return 'no-throw'; } catch (e) { return e.code || String(e); } };
      return {
        acc_hi: code(() => __s6.scoring.trial(Object.assign({}, ok, { accuracy: 1.01 }), b)),
        acc_lo: code(() => __s6.scoring.trial(Object.assign({}, ok, { accuracy: -0.1 }), b)),
        acc_nan: code(() => __s6.scoring.trial(Object.assign({}, ok, { accuracy: NaN }), b)),
        lvl0: code(() => __s6.scoring.trial(Object.assign({}, ok, { level: 0 }), b)),
        lvl4: code(() => __s6.scoring.trial(Object.assign({}, ok, { level: 4 }), b)),
        n0: code(() => __s6.scoring.episode(0, [{ points: 1, stars: 1 }])),
        n13: code(() => __s6.scoring.episode(13, [{ points: 1, stars: 1 }])),
        good: code(() => __s6.scoring.trial(ok, b)) };
    }""")
    C.check('4.1', all(bad[k] == 'SCORE_INPUT' for k in bad if k != 'good') and bad['good'] == 'no-throw',
            'SCORE_INPUT при accuracy вне 0..1, уровне вне 1..3, n вне 1..12', bad)

    # ---- 4.2–4.3 таблица ----
    got = pg.evaluate("""(t) => t.cases.map(c => __s6.scoring.trial(Object.assign({ type: 'shirma', taskId: 'x', powerSpent: 0, caseClues: [] }, c.r), t.balances[c.b]))""", CASES)
    wrong = ['%s: ждали %s/%s★, получили %s/%s★' % (c['name'], c['points'], c['stars'], g['points'], g['stars'])
             for c, g in zip(CASES['cases'], got) if c['points'] != g['points'] or c['stars'] != g['stars']]
    C.check('4.2', not [w for w in wrong], 'формула очков: %d табличных примеров' % len(CASES['cases']), wrong)
    sel = [(c, g) for c, g in zip(CASES['cases'], got)]
    three_ok = all((g['stars'] == 3) == (c['r']['solved'] and c['r']['hintsUsed'] == 0 and g['points'] >= CASES['balances'][c['b']]['stars3']) for c, g in sel)
    zero_ok = all((g['stars'] == 0) == (not c['r']['solved']) for c, g in sel)
    C.check('4.3', three_ok and zero_ok, 'звёзды: 3 только без подсказок и при points ≥ stars3; не решено → 0')

    # ---- 4.4 выпуск и переигровка ----
    r = pg.evaluate("""() => {
      const P = __s6.progress; P.reset();
      const ep = __s6.scoring.episode(11, [{ points: 110, stars: 3 }, { points: 55, stars: 2 }]);
      const p0 = P.get().power;
      P.recordEpisode(1, { points: 60, stars: 1, powerGain: 2, newClues: [] }, null, [], '2026-11-24');
      const p1 = P.get().power;
      P.recordEpisode(1, { points: 90, stars: 3, powerGain: 3, newClues: [] }, null, [], '2026-11-25');
      const e = P.get().episodes[1];
      return { ep, p0, p1, p2: P.get().power, stars: e.stars, best: e.bestPoints, attempts: e.attempts, first: e.firstDate };
    }""")
    C.check('4.4a', r['ep'] == {'points': 165, 'stars': 2, 'powerGain': 5, 'newClues': []},
            'выпуск: очки складываются, звёзды — среднее вниз, powerGain = сумма звёзд', r['ep'])
    C.check('4.4b', r['p1'] == r['p0'] + 2 and r['p2'] == r['p1'] and r['stars'] == 3 and r['best'] == 90 and r['attempts'] == 2 and r['first'] == '2026-11-24',
            'первое прохождение даёт силу, переигровка — нет, но улучшает звёзды', r)

    # ---- 4.5–4.7 соперники и скептик ----
    r = pg.evaluate("""async () => {
      const { createRng, hashSeed } = await import('/src/core/rng.js');
      const S = __s6.scoring, P = __s6.progress; P.reset();
      const base = P.get();
      const pl = { points: 50, stars: 2, powerGain: 2, newClues: [] };
      const t1 = S.rivals(1, pl, base, createRng(hashSeed('rivals', 1, 1)), 0);
      const t2 = S.rivals(1, pl, base, createRng(hashSeed('rivals', 1, 1)), 0);
      const t3 = S.rivals(1, pl, base, createRng(hashSeed('rivals', 1, 2)), 0);
      // сезон целиком сильным игроком
      let st = JSON.parse(JSON.stringify(base)); const elim = {}; let left = [];
      for (let n = 1; n <= 12; n++) {
        const k = __s6.content.episode(n).trials.length;
        const me = { points: 130 * k, stars: 3, powerGain: 3 * k, newClues: [] };
        const o = S.rivals(n, me, st, createRng(hashSeed('rivals', n, 1)), 0);
        o.table.forEach((row) => { if (st.rivals[row.id]) st.rivals[row.id].points = row.points; });
        if (o.eliminated) { st.rivals[o.eliminated].eliminatedAfter = n; elim[n] = o.eliminated; }
        if (o.playerMustReplay) elim[n] = 'player';
        st.totalPoints += me.points;
      }
      left = Object.keys(st.rivals).filter((id) => !st.rivals[id].eliminatedAfter);
      // игрок последний: выпуск выбывания и обычный
      const weak = { points: 0, stars: 0, powerGain: 0, newClues: [] };
      const m3 = S.rivals(3, weak, base, createRng(1), 0), m2 = S.rivals(2, weak, base, createRng(1), 0);
      const traps = [0, 1, 2, 5].map((h) => S.rivals(2, pl, base, createRng(1), h).skepticTraps);
      return { same: JSON.stringify(t1) === JSON.stringify(t2), diff: JSON.stringify(t1.table) !== JSON.stringify(t3.table),
               elim, left, m3: { must: m3.playerMustReplay, el: m3.eliminated }, m2: { must: m2.playerMustReplay, el: m2.eliminated }, traps,
               after: __s6.content.balance().eliminateAfter };
    }""")
    C.check('4.5a', r['same'] and r['diff'], 'один seed → одна таблица, другой seed → другая', r)
    C.check('4.5b', sorted(int(n) for n in r['elim']) == r['after'] == [3, 6, 9, 11] and 'player' not in r['elim'].values() and len(r['left']) == 1,
            'выбывание только после 3/6/9/11, к финалу остаётся 1 соперник', r['elim'])
    C.check('4.6', r['m3'] == {'must': True, 'el': None} and r['m2'] == {'must': False, 'el': None},
            'игрок последний в выпуск выбывания → playerMustReplay, никто не выбывает', r)
    C.check('4.7', r['traps'] == [0, 0, 1, 1], 'скептик: hintsUsed ≥ 2 → traps = 1, иначе 0', r['traps'])

    # ---- 4.8–4.9 DayLock ----
    def dl(js):
        return pg.evaluate("() => { const D = __s6.dayLock, P = __s6.progress; " + js + " }")
    pg.evaluate("__s6.progress.reset(); __s6.progress.setSettings({test:false})")
    done = "(n, day) => P.update(d => { d.episodes[n] = { firstDate: day, stars: 2, points: 60, bestPoints: 60, attempts: 1 }; })"
    fix_date(pg, 2026, 11, 24)    # вторник
    r = dl("""const done = %s;
      const a = [D.today(), D.availability(1), D.quotaLeft(), D.availability(2)];
      D.markStarted(1); const b = [D.quotaLeft(), D.availability(1)];
      done(1, '2026-11-24'); const c = [D.availability(1), D.availability(2), D.availability(3)];
      return { a, b, c };""" % done)
    C.check('4.8a', r['a'] == ['2026-11-24', 'open', 1, 'locked'] and r['b'] == [0, 'open'] and r['c'] == ['done', 'wait', 'locked'],
            'будний день: открыт 1 выпуск, второй ждёт завтра, третий закрыт', r)
    fix_date(pg, 2026, 11, 25)
    r = dl("const a = D.availability(2); D.markStarted(2); return [a, D.quotaLeft(), D.today()];")
    C.check('4.8b', r == ['open', 0, '2026-11-25'], 'на следующий день открывается следующий выпуск', r)
    fix_date(pg, 2026, 11, 23)    # часы назад
    r = dl("return [D.availability(2), D.availability(1)];")
    C.check('4.8c', r == ['open', 'done'], 'перевод часов назад не закрывает открытое', r)
    fix_date(pg, 2026, 11, 28)    # суббота
    r = dl("""const done = %s; done(2, '2026-11-25');
      const a = [D.quotaLeft(), D.availability(3)]; D.markStarted(3); done(3, '2026-11-28');
      const b = [D.quotaLeft(), D.availability(4)]; D.markStarted(4); done(4, '2026-11-28');
      const c = [D.quotaLeft(), D.availability(5)];
      return { a, b, c };""" % done)
    C.check('4.8d', r == {'a': [2, 'open'], 'b': [1, 'open'], 'c': [0, 'wait']}, 'суббота: 2 выпуска, третий ждёт', r)
    fix_date(pg, 2026, 11, 29)
    r = dl("""return [D.availability(5), D.availability(6), D.availability(12), D.availability(1), D.availability(4)];""")
    C.check('4.9a', r == ['open', 'locked', 'locked', 'done', 'done'], 'строго по порядку; пройденные доступны для переигровки', r)
    r = dl("""D.markStarted(5); const done = %s; done(5, '2026-11-29');
      const a = D.availability(6); P.setSettings({ test: true }); const b = [D.availability(6), D.availability(7)];
      P.setSettings({ test: false }); return [a, b];""" % done)
    C.check('4.9b', r == ['wait', ['open', 'locked']], 'в режиме теста дневного лимита нет, порядок сохраняется', r)
    r = pg.evaluate("""() => { const D = __s6.dayLock; D.now = () => new Date(NaN);
      try { return ['ok', D.availability(6)]; } catch (e) { return ['throw', String(e)]; } }""")
    C.check('4.9c', r[0] == 'ok', 'дата не читается → игра не блокируется, исключения нет', r)

    # ---- 4.10 мешок ----
    r = pg.evaluate("""async () => {
      const { createRng } = await import('/src/core/rng.js');
      const C = __s6.content, P = __s6.progress, K = __s6.content.balance().noRepeatLast;
      const res = { dupInBag: 0, notFull: 0, headRecent: 0, size: 0, seeds: 0 };
      for (const [t, l] of [['shirma', 1], ['bagazhnik', 2], ['misterx', 3], ['foto', 1], ['komnata', 2]]) {
        const ids = (await C.pool(t, l)).map((x) => x.id); res.size = ids.length;
        for (let seed = 1; seed <= 40; seed++) {
          P.saveDraws({}); const rng = createRng(seed); const seq = [];
          for (let i = 0; i < ids.length * 2; i++) seq.push((await C.draw(t, l, rng)).id);
          const first = seq.slice(0, ids.length), second = seq.slice(ids.length);
          if (new Set(first).size !== ids.length) res.dupInBag++;
          if (new Set(second).size !== ids.length) res.dupInBag++;
          if (first.some((id) => !ids.includes(id))) res.notFull++;
          const recent = first.slice(-K), headN = Math.min(K, ids.length - K);
          if (second.slice(0, headN).some((id) => recent.includes(id))) res.headRecent++;
          const strict = second.slice(0, K).some((id) => recent.includes(id));
          if (strict) res.strict = (res.strict || 0) + 1;
          res.seeds++;
        }
      }
      return res;
    }""")
    C.check('4.10a', r['dupInBag'] == 0 and r['notFull'] == 0, 'мешок: каждое задание пула выпадает по разу, пока мешок не пуст (%d прогонов)' % r['seeds'], r)
    C.check('4.10b', r['headRecent'] == 0, 'после перемешивания последние %d не попадают в начало нового мешка (сколько позволяет размер пула)' % 3, r)
    pg.evaluate("__s6.progress.saveDraws({})")
    first = pg.evaluate("""async () => { const { createRng } = await import('/src/core/rng.js');
      const r = createRng(7), out = []; for (let i = 0; i < 3; i++) out.push((await __s6.content.draw('shirma', 2, r)).id); return out; }""")
    pg.reload(); pg.wait_for_function("window.__s6 && __s6.scenes.current().id === 'title'")
    rest = pg.evaluate("""async () => { const { createRng } = await import('/src/core/rng.js');
      const r = createRng(8), out = []; for (let i = 0; i < 2; i++) out.push((await __s6.content.draw('shirma', 2, r)).id); return out; }""")
    pool = pg.evaluate("(async () => (await __s6.content.pool('shirma', 2)).map(x => x.id))()")
    C.check('4.10d', sorted(first + rest) == sorted(pool), 'состояние мешка переживает перезагрузку', [first, rest])

    # ---- 4.11 pickText ----
    r = pg.evaluate("""async () => { const { createRng } = await import('/src/core/rng.js');
      const out = {}; for (const pre of ['host.praise', 'skeptic.jab']) {
        const rng = createRng(42); let prev = null, rep = 0; const seen = new Set();
        for (let i = 0; i < 1000; i++) { const s = __s6.content.pickText(pre, rng); if (s === prev) rep++; prev = s; seen.add(s); }
        out[pre] = { rep, uniq: seen.size }; } return out; }""")
    C.check('4.11', all(v['rep'] == 0 and v['uniq'] == 12 for v in r.values()), 'pickText: 1000 вызовов без повтора подряд, все 12 реплик встречаются', r)

    # ---- 4.12 звания ----
    r = pg.evaluate("""() => { const ts = __s6.content.balance().titles;
      return ts.map((t, i) => [__s6.scoring.title(t.from).id === t.id, i === 0 || __s6.scoring.title(t.from - 1).id === ts[i - 1].id]); }""")
    C.check('4.12', all(a and b2 for a, b2 in r), 'звание меняется ровно на порогах titles из balance.json', r)

    pg.evaluate("__s6.progress.reset()")
    b.close()
finally:
    srv.stop()
C.done()
