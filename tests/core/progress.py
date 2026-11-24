# Группа 6 tests.md — прогресс: перезагрузка, продолжение выпуска, испорченное сохранение,
# недоступный localStorage, миграция прототипа, экспорт/импорт. Снимки — tests/snapshots/A/progress-*.png
import json, os
from playwright.sync_api import sync_playwright
from _s6 import Server, Checks, SNAP_A, launch, boot, wait_scene, fix_date, task_payload, play_episode1

C = Checks('Группа 6 — прогресс')
os.makedirs(SNAP_A, exist_ok=True)
srv = Server()
V = {'viewport': {'width': 1024, 'height': 768}, 'has_touch': True}


def shot(pg, name):
    pg.wait_for_timeout(300); pg.screenshot(path=os.path.join(SNAP_A, 'progress-' + name + '.png'))


def state(pg):
    return pg.evaluate("JSON.parse(JSON.stringify(__s6.progress.get()))")


def start_ep11(pg):
    """Режим теста → debug → выпуск 11 (Багажник 3 + Ширма 3) → первое испытание."""
    pg.evaluate("__s6.progress.setSettings({ test: true })")
    pg.evaluate("__s6.scenes.replace('debug')"); wait_scene(pg, 'debug')
    pg.click('[data-go="11"]'); wait_scene(pg, 'intro')
    pg.click('[data-action=start]'); wait_scene(pg, 'trial')
    pg.wait_for_selector('[data-car]')
    pl = task_payload(pg, 'bagazhnik', 3)
    pg.click('[data-car="%s"]' % pl['target']); pg.wait_for_timeout(300)
    pg.click('[data-bz=choose]')


def resume_ep11(pg):
    boot(pg, srv.url)
    pg.click('[data-action=season]'); wait_scene(pg, 'season')
    pg.click('.card[data-n="11"]'); wait_scene(pg, 'intro')
    pg.click('[data-action=start]'); wait_scene(pg, 'trial')
    pg.wait_for_timeout(500)
    return pg.evaluate("({ idx: __s6.scenes.current().params.idx, run: __s6.progress.run() })")


try:
  with sync_playwright() as p:
    b = launch(p)

    # ---- 6.1 перезагрузка ----
    ctx = b.new_context(**V); pg = ctx.new_page(); C.watch(pg)
    boot(pg, srv.url); fix_date(pg, 2026, 11, 24)
    play_episode1(pg)
    pg.click('[data-action=season]'); wait_scene(pg, 'season')
    before = state(pg)
    pg.reload(); wait_scene(pg, 'title')
    after = state(pg)
    pg.click('[data-action=season]'); wait_scene(pg, 'season'); shot(pg, 'reloaded-season')
    C.check('6.1', before == after and after['episodes'].get('1') and after['power'] > 3 and any(r['points'] for r in after['rivals'].values())
            and 'done' in pg.get_attribute('.card[data-n="1"]', 'class'),
            'пройти выпуск → перезагрузить → звёзды, сила, таблица соперников на месте', [before, after])

    # ---- 6.6 экспорт / импорт ----
    r = pg.evaluate("""() => { const P = __s6.progress; const before = JSON.stringify(P.get()); const draws = JSON.stringify(P.draws());
      const code = P.exportCode(); P.reset(); const wiped = Object.keys(P.get().episodes).length;
      const ok = P.importCode(code); const same = JSON.stringify(P.get()) === before && JSON.stringify(P.draws()) === draws;
      const bad1 = P.importCode('это не код'); const bad2 = P.importCode(btoa('{"p":{"schema":1}}')); const bad3 = P.importCode(code.slice(0, 20));
      return { wiped, ok, same, bad: [bad1, bad2, bad3], untouched: JSON.stringify(P.get()) === before }; }""")
    C.check('6.6', r == {'wiped': 0, 'ok': True, 'same': True, 'bad': [False, False, False], 'untouched': True},
            'exportCode → reset → importCode возвращает прогресс полностью; битый код не трогает текущий', r)
    ctx.close()

    # ---- 6.2 середина выпуска из 2 испытаний ----
    ctx = b.new_context(**V); pg = ctx.new_page(); C.watch(pg)
    boot(pg, srv.url)
    start_ep11(pg)
    pg.wait_for_function("__s6.scenes.current().id === 'trial' && __s6.scenes.current().params.idx === 1 && !__s6.scenes.busy", timeout=20000)
    pg.wait_for_selector('[data-opt]'); pg.wait_for_timeout(300)
    run0 = pg.evaluate("__s6.progress.run()")
    r = resume_ep11(pg); shot(pg, 'resume-second')
    C.check('6.2a', r['idx'] == 1 and r['run']['taskIds'] == run0['taskIds'] and len(r['run']['results']) >= 1 and r['run']['seed'] == run0['seed'],
            'закрыть на втором испытании выпуска 11 → открыть → продолжается со второго, задание то же',
            {'idx': r['idx'], 'tasks': [run0['taskIds'], r['run']['taskIds']]})
    ctx.close()

    ctx = b.new_context(**V); pg = ctx.new_page(); C.watch(pg)
    boot(pg, srv.url)
    start_ep11(pg)
    pg.wait_for_function("__s6.progress.run() && __s6.progress.run().results.length === 1", timeout=15000)
    run0 = pg.evaluate("__s6.progress.run()")
    r = resume_ep11(pg)
    C.check('6.2b', r['idx'] == 1 and len(r['run']['results']) >= 1,
            'закрыть сразу после завершения первого испытания (пока идёт пауза 2,6 с) → продолжается со второго',
            {'idx': r['idx'], 'run_before': {'idx': run0['idx'], 'results': len(run0['results'])}})
    ctx.close()

    # ---- 6.3 испорченный JSON ----
    ctx = b.new_context(**V); pg = ctx.new_page(); C.watch(pg)
    boot(pg, srv.url)
    pg.evaluate("localStorage.setItem('s6:v2:progress', '{\"schema\":2, сломано')")
    pg.reload(); wait_scene(pg, 'title'); shot(pg, 'corrupt-title')
    r = pg.evaluate("""() => ({ corrupt: localStorage.getItem('s6:v2:progress.corrupt'), rec: __s6.progress.recovered,
      warn: [...document.querySelectorAll('.warn')].map(e => e.textContent), msg: __s6.content.text('ui.recovered'),
      schema: __s6.progress.get().schema, h1: !!document.querySelector('h1') })""")
    C.check('6.3', r['corrupt'] == '{"schema":2, сломано' and r['rec'] and r['msg'] in r['warn'] and r['schema'] == 2 and r['h1'],
            'испорченный JSON → игра стартует, копия в s6:v2:progress.corrupt, сообщение показано', r)
    ctx.close()

    # ---- 6.4 localStorage бросает при записи ----
    ctx = b.new_context(**V)
    ctx.add_init_script("Storage.prototype.setItem = function () { throw new DOMException('quota', 'QuotaExceededError'); };")
    pg = ctx.new_page(); C.watch(pg)
    boot(pg, srv.url); shot(pg, 'nostorage-title')
    r = pg.evaluate("""() => ({ pers: __s6.progress.persistent, warn: [...document.querySelectorAll('.warn')].map(e => e.textContent),
      msg: __s6.content.text('ui.noStorage') })""")
    pg.click('[data-action=season]'); wait_scene(pg, 'season')
    C.check('6.4', r['pers'] is False and r['msg'] in r['warn'] and pg.query_selector('.card.open') is not None,
            'localStorage бросает → игра работает, предупреждение «прогресс не сохранится»', r)
    ctx.close()

    # ---- 6.5 миграция прототипа ----
    ctx = b.new_context(**V); pg = ctx.new_page(); C.watch(pg)
    boot(pg, srv.url)
    legacy = {'v': 1, 'done': {'1': {'date': '2026-11-23', 'stars': 2}, '2': {'date': '2026-11-24', 'stars': 3}}, 'power': 7, 'sound': True, 'test': False}
    pg.evaluate("""(s) => { Object.keys(localStorage).filter(k => k.startsWith('s6:')).forEach(k => localStorage.removeItem(k));
      localStorage.setItem('sixth-sense-save-v1', s); }""", json.dumps(legacy))
    pg.reload(); wait_scene(pg, 'title')
    r = pg.evaluate("""() => ({ p: __s6.progress.get(), saved: JSON.parse(localStorage.getItem('s6:v2:progress') || 'null'),
      legacyKept: localStorage.getItem('sixth-sense-save-v1') !== null })""")
    ep = r['p']['episodes']
    C.check('6.5', ep.get('1', {}).get('stars') == 2 and ep.get('2', {}).get('stars') == 3 and r['p']['power'] == 7
            and r['saved'] and r['saved']['schema'] == 2 and r['legacyKept'],
            'сохранение прототипа мигрирует: пройденные выпуски и сила перенесены, старый ключ не удалён', r)
    ctx.close()
    b.close()
finally:
    srv.stop()
C.done()
