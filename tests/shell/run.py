# Проверки зоны D: достижения (тост, запись, список в настройках) и громкость музыки. Снимки — tests/snapshots/D/.
# Запуск: python3 tests/shell/run.py  (свой сервер на свободном порту, Chrome + Playwright)
import subprocess, time, os, json, re, socket, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = ROOT + '/tests/snapshots/D/'; os.makedirs(OUT, exist_ok=True)
TEXTS = json.load(open(ROOT + '/tests/trials/fixtures/texts-shell.json', encoding='utf-8'))
s = socket.socket(); s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]; s.close()
srv = subprocess.Popen(['python3', '-m', 'http.server', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1); errs = []; res = []
def check(c, msg): res.append(('PASS ' if c else 'FAIL ') + msg)
def shot(pg, name, wait=400): pg.wait_for_timeout(wait); pg.screenshot(path=OUT + name + '.png')

# 1) статическая проверка: в .js оболочки нет русских строк вне комментариев
for f in sorted(os.listdir(ROOT + '/src/shell')):
    if not f.endswith('.js'): continue
    code = re.sub(r'//[^\n]*', '', open(ROOT + '/src/shell/' + f, encoding='utf-8').read())
    check(not re.search('[А-Яа-яЁё]', code), 'нет русских строк в src/shell/' + f)
d = json.load(open(ROOT + '/data/achievements.json', encoding='utf-8'))
ids = [a['id'] for a in d['achievements']]
check(d['schema'] == 1 and 10 <= len(ids) <= 12 and len(set(ids)) == len(ids), 'achievements.json: %d достижений, id уникальны' % len(ids))
check(all(a['titleKey'] in TEXTS and a['descKey'] in TEXTS for a in d['achievements']), 'у всех достижений есть тексты в texts-shell.json')

def boot(pg):
    pg.wait_for_function('window.__s6 && window.__s6.content && window.__s6.content.texts')
    pg.evaluate('(t) => Object.assign(window.__s6.content.texts, t)', TEXTS)
    pg.wait_for_timeout(300)

try:
  with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(viewport={'width': 1024, 'height': 768}, has_touch=True, service_workers='block')
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and '404' not in m.text else None)
    # 2) старое сохранение без achievements и musicVolume
    pg.goto('http://localhost:%d/' % PORT); boot(pg)
    pg.evaluate("""() => { const d = __s6.progress.defaults(); delete d.achievements;
      localStorage.setItem('s6:v2:progress', JSON.stringify(d));
      localStorage.setItem('s6:v2:settings', JSON.stringify({ music: true, sfx: true, voice: true, test: false })); }""")
    pg.reload(); boot(pg)
    st = pg.evaluate('({ a: __s6.progress.get().achievements, v: __s6.progress.settings().musicVolume, rec: __s6.progress.recovered })')
    check(st['a'] == [] and st['v'] is None and not st['rec'], 'старый сейв открылся: achievements=[] по умолчанию, musicVolume нет, не «испорчен»')
    # 3) выпуск 1 без подсказок и ошибок
    pg.click('[data-action=season]'); pg.wait_for_timeout(700)
    pg.click('.card.open[data-action=ep]'); pg.wait_for_timeout(700)
    pg.click('[data-action=start]'); pg.wait_for_timeout(1200)
    tid = pg.evaluate('__s6.progress.run().taskIds[0]')
    ans = pg.evaluate("(async (id) => (await __s6.content.pool('shirma',1)).find(t => t.id===id).payload.answer)('%s')" % tid)
    pg.click('[data-opt="%s"]' % ans)
    pg.wait_for_selector('.big-stars', timeout=8000)
    pg.wait_for_selector('.ach-toast', timeout=4000)
    shot(pg, 'ach-toast', 2600)
    got = pg.evaluate('__s6.progress.get().achievements')
    check(all(x in got for x in ['first-win', 'no-hints', 'no-mistakes']), 'достижения записаны в progress: %s' % got)
    n = len(pg.query_selector_all('.ach-toast')); txt = pg.inner_text('.ach-toasts')
    check(n == len(got) and TEXTS['ach.first-win.title'] in txt, 'тосты на итогах: %d шт.' % n)
    pg.wait_for_timeout(5500)
    check(len(pg.query_selector_all('.ach-toast')) == 0, 'тосты исчезли сами')
    # 4) список в настройках
    pg.click('[data-action=season]'); pg.wait_for_timeout(700)
    pg.click('[data-action=title]'); pg.wait_for_timeout(700)
    pg.click('[data-action=settings]'); pg.wait_for_timeout(700)
    check(pg.get_attribute('.vstep.gold', 'data-v') == '1', 'громкость по умолчанию 100%')
    pg.click('[data-action=ach]'); pg.wait_for_timeout(400)
    items = len(pg.query_selector_all('.ach-item')); bright = len(pg.query_selector_all('.ach-item.got'))
    check(items == len(ids) and bright == len(got), 'список достижений: %d всего, ярких %d' % (items, bright))
    shot(pg, 'ach-list')
    pg.click('.ach-box'); pg.wait_for_timeout(200)
    check(pg.query_selector('.ach-panel') is not None, 'тык внутри окна не закрывает его')
    pg.click('.ach-box [data-action=ach-close]'); pg.wait_for_timeout(300)
    check(pg.query_selector('.ach-panel') is None, 'окно достижений закрывается')
    # 5) громкость музыки
    on = pg.evaluate('__s6.audio.unlocked && !!__s6.audio.musicNode')
    check(on, 'музыка играет после касания')
    pg.click('[data-action=vol][data-v="0"]'); pg.wait_for_timeout(300)
    st = pg.evaluate('({ v: __s6.progress.settings().musicVolume, m: !!__s6.audio.musicNode })')
    check(st['v'] == 0 and not st['m'], '0%% — музыка выключена: %s' % st)
    pg.click('[data-action=vol][data-v="0.5"]'); pg.wait_for_timeout(300)
    st = pg.evaluate('({ v: __s6.progress.settings().musicVolume, m: !!__s6.audio.musicNode, g: __s6.audio.musicNode && __s6.audio.musicNode.out.gain.value })')
    check(st['v'] == 0.5 and st['m'], '50%% — музыка снова играет: %s' % st)
    pg.wait_for_timeout(1500)
    g = pg.evaluate('__s6.audio.musicNode.out.gain.value')
    pg.click('[data-action=vol][data-v="1"]'); pg.wait_for_timeout(1500)
    g2 = pg.evaluate('__s6.audio.musicNode.out.gain.value')
    check(g2 > g * 1.5, 'громкость меняется сразу: %.2f → %.2f' % (g, g2))
    pg.click('[data-action=vol][data-v="0.5"]'); pg.wait_for_timeout(300)
    shot(pg, 'settings-volume')
    # музыка выключена кнопкой → выбор громкости включает её
    pg.click('[data-action=tg][data-k=music]'); pg.wait_for_timeout(200)
    pg.click('[data-action=vol][data-v="0.75"]'); pg.wait_for_timeout(300)
    st = pg.evaluate('({ on: __s6.progress.settings().music, m: !!__s6.audio.musicNode })')
    check(st['on'] and st['m'], 'выбор громкости при выключенной музыке включает её')
    pg.click('[data-action=tg][data-k=music]'); pg.wait_for_timeout(200)
    pg.click('[data-action=tg][data-k=music]'); pg.wait_for_timeout(300)
    check(pg.evaluate('!!__s6.audio.musicNode'), 'музыка выкл → вкл снова играет')
    pg.click('[data-action=vol][data-v="0.5"]'); pg.wait_for_timeout(300)
    # 6) после перезагрузки
    pg.reload(); boot(pg)
    pg.click('[data-action=settings]'); pg.wait_for_timeout(700)
    check(pg.get_attribute('.vstep.gold', 'data-v') == '0.5', 'громкость 50% сохранилась после перезагрузки')
    check(pg.evaluate('__s6.progress.get().achievements.length') == len(got), 'достижения сохранились после перезагрузки')
    pg.click('[data-action=vol][data-v="0.25"]'); pg.wait_for_timeout(300)  # первое касание → разблокировка звука
    check(pg.evaluate('!!__s6.audio.musicNode'), 'музыка стартует с сохранённой громкостью')
    # 7) правила по данным (через модуль оболочки)
    r = pg.evaluate("""async () => { const m = await import('/src/shell/achievements.js'); const app = __s6;
      const a = (await m.awardAchievements(app, { results: [{ type: 'bagazhnik', level: 1, solved: true, hintsUsed: 0, mistakes: 1 }] })).map(x => x.id);
      const b = (await m.awardAchievements(app, { results: [{ type: 'misterx', level: 2, solved: true, hintsUsed: 0, mistakes: 0 }] })).map(x => x.id);
      const c = (await m.awardAchievements(app, { results: [{ type: 'misterx', level: 3, solved: true, hintsUsed: 0, mistakes: 0 }] })).map(x => x.id);
      const d = (await m.awardAchievements(app, { caseSolved: false })).map(x => x.id);
      const e = (await m.awardAchievements(app, { caseSolved: true })).map(x => x.id);
      app.progress.update((s) => { s.totalPoints = 900; const k = Object.keys(s.rivals)[0]; s.rivals[k].eliminatedAfter = 3; });
      const f = (await m.awardAchievements(app, {})).map(x => x.id);
      const g = (await m.awardAchievements(app, { caseSolved: true })).map(x => x.id);
      return { a, b, c, d, e, f, g }; }""")
    check(r['a'] == ['bag-blind'], 'Багажник без осмотра → bag-blind (с ошибкой «без промаха» не даётся): %s' % r['a'])
    check(r['b'] == [] and 'misterx-master' in r['c'], 'Мистер Икс: ур. 2 не считается, ур. 3 без подсказок → misterx-master')
    check(r['d'] == [] and r['e'] == ['case-solved'], 'разгадка дела: все связи верны → case-solved')
    check(sorted(r['f']) == ['seer', 'survivor'] and r['g'] == [], 'звание «Ясновидящая» и выбывание соперника; повторно не выдаются: %s' % r['f'])
    b.close()
finally:
    srv.terminate()
print('\n'.join(res)); print('ERRORS:', errs)
sys.exit(1 if errs or any(x.startswith('FAIL') for x in res) else 0)
