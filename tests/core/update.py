# Группа 8 tests.md — обновление поверх установленной версии. Главное: прогресс игрока не теряется.
# Проект копируется во временные папки (v1…v4), в каждой своя версия sw.js и precache.json
# (node tools/build-precache.js <версия> внутри копии). Один и тот же адрес сервера, корень меняется на лету —
# для браузера это «выложили новую версию на GitHub Pages». Снимки — tests/snapshots/A/update-*.png
import json, os, shutil, subprocess, tempfile
from playwright.sync_api import sync_playwright
from _s6 import ROOT, Server, Checks, SNAP_A, launch, boot, wait_scene, fix_date, task_payload, play_episode1

C = Checks('Группа 8 — обновление')
os.makedirs(SNAP_A, exist_ok=True)
TMP = tempfile.mkdtemp(prefix='s6-update-')
VER = {'v1': '9.1.0', 'v2': '9.2.0', 'v3': '9.3.0', 'v4': '9.4.0'}


def make(name, broken=False):
    d = os.path.join(TMP, name)
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns('.git', 'tests', 'node_modules', '__pycache__', '*.pyc'))
    r = subprocess.run(['node', os.path.join(d, 'tools', 'build-precache.js'), VER[name]], cwd=d, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('build-precache в копии %s: %s %s' % (name, r.stdout, r.stderr))
    if broken:                                  # 8.4: в списке файл, которого нет на сервере → скачивание версии падает
        pj = os.path.join(d, 'precache.json'); j = json.load(open(pj)); j['files'].append('src/core/nope-missing.js')
        json.dump(j, open(pj, 'w'))
    return d


def shot(pg, name):
    pg.wait_for_timeout(300); pg.screenshot(path=os.path.join(SNAP_A, 'update-' + name + '.png'))


def state(pg):
    return pg.evaluate("JSON.parse(JSON.stringify(__s6.progress.get()))")


def version(pg, v, timeout=10000):
    try:
        pg.wait_for_function("(v) => window.__s6 && __s6.updater.version === v", arg=v, timeout=timeout); return True
    except Exception:
        return False


DIRS = {k: make(k, broken=(k == 'v4')) for k in VER}
srv = Server(root=DIRS['v1'])
try:
  with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={'width': 1024, 'height': 768}, has_touch=True)
    pg = ctx.new_page(); C.watch(pg)

    # ---- установлена версия 1, пройден выпуск 1 ----
    boot(pg, srv.url)
    pg.wait_for_function("navigator.serviceWorker.controller !== null", timeout=20000)
    fix_date(pg, 2026, 11, 24)
    play_episode1(pg)
    pg.click('[data-action=season]'); wait_scene(pg, 'season')
    pg.evaluate("__s6.progress.setSettings({ music: false })")
    before = state(pg); sets_before = pg.evaluate("__s6.progress.settings()")
    pg.reload(); wait_scene(pg, 'title')
    files = json.load(open(os.path.join(DIRS['v1'], 'precache.json')))['files']
    cached = pg.evaluate("async (v) => (await (await caches.open('s6-' + v)).keys()).length", VER['v1'])
    C.check('7.1', version(pg, VER['v1']) and cached == len(files),
            'версия 1 установлена: service worker активен, в кэше все %d файлов precache.json' % len(files), cached)

    # ---- 8.1 выкладываем версию 2 ----
    srv.root = DIRS['v2']
    pg.reload(); wait_scene(pg, 'title')
    try:
        pg.wait_for_selector('.banner', timeout=20000); banner = True
    except Exception:
        banner = False
    shot(pg, 'banner-title')
    txt = pg.evaluate("[document.querySelector('.banner') && document.querySelector('.banner').textContent, __s6.content.text('ui.updateReady')]")
    C.check('8.1a', banner and txt[1] in (txt[0] or ''), 'перезапуск с сетью → баннер «Обновить» на title', txt)
    C.check('8.1b', state(pg) == before, 'пока не обновились — прогресс тот же')
    if banner:
        with pg.expect_navigation(timeout=20000):
            pg.click('.banner button')
        wait_scene(pg, 'title')
    ok_v2 = version(pg, VER['v2'])
    after = state(pg); sets_after = pg.evaluate("__s6.progress.settings()")
    C.check('8.1c', ok_v2 and after == before and sets_after == sets_before,
            'после «Обновить» — версия 2, прогресс и настройки на месте',
            {'version': pg.evaluate("__s6.updater.version"), 'same': after == before, 'sets': [sets_before, sets_after]})
    pg.click('[data-action=season]'); wait_scene(pg, 'season'); shot(pg, 'after-v2-season')
    C.check('8.1d', 'done' in (pg.get_attribute('.card[data-n="1"]', 'class') or ''), 'на карте сезона выпуск 1 пройден после обновления')

    # ---- 8.3 старые кэши удалены ----
    keys = pg.evaluate("async () => (await caches.keys()).filter(k => k.indexOf('s6-') === 0)")
    C.check('8.3', keys == ['s6-' + VER['v2']], 'после активации старые кэши s6-* удалены', keys)

    # ---- 8.2 новая версия готова во время испытания ----
    srv.root = DIRS['v3']; srv.delay['precache.json'] = 6      # версия скачивается медленно — успеваем войти в испытание
    pg.reload(); wait_scene(pg, 'title')
    pg.click('[data-action=season]'); wait_scene(pg, 'season')
    pg.click('.card[data-n="1"]'); wait_scene(pg, 'intro')
    pg.click('[data-action=start]'); wait_scene(pg, 'trial')
    pg.wait_for_selector('[data-opt]')
    pg.evaluate("window.__mark = 'до обновления'")
    pg.wait_for_function("__s6.updater.ready === true", timeout=30000); pg.wait_for_timeout(800)
    shot(pg, 'ready-in-trial')
    r = pg.evaluate("({ scene: __s6.scenes.current().id, mark: window.__mark, opts: document.querySelectorAll('[data-opt]').length })")
    C.check('8.2a', r['scene'] == 'trial' and r['mark'] == 'до обновления' and r['opts'] > 0,
            'новая версия готова во время испытания → испытание не прерывается', r)
    C.check('8.2b', pg.query_selector('.banner') is None, 'во время испытания баннера нет (только на title или season)')
    pl = task_payload(pg, 'shirma', 1)
    pg.click('[data-opt="%s"]' % pl['answer']); wait_scene(pg, 'result', 15000)
    pg.click('[data-action=season]'); wait_scene(pg, 'season')
    try:
        pg.wait_for_selector('.banner', timeout=5000); banner = True
    except Exception:
        banner = False
    shot(pg, 'banner-season')
    C.check('8.2c', banner, 'после испытания на season баннер «Обновить» есть')
    mid = state(pg)
    if banner:
        with pg.expect_navigation(timeout=20000):
            pg.click('.banner button')
        wait_scene(pg, 'title')
    after = state(pg)
    C.check('8.2d', version(pg, VER['v3']) and after == mid and after['episodes']['1']['attempts'] == 2
            and after['power'] == before['power'],
            'обновление после переигровки: версия 3, переигровка засчитана, сила не прибавилась', after['episodes'].get('1'))

    # ---- 8.4 ошибка скачивания новой версии ----
    srv.root = DIRS['v4']; srv.delay = {}
    errs0 = len(C.errors)
    pg.reload(); wait_scene(pg, 'title'); pg.wait_for_timeout(6000)
    r = pg.evaluate("""async () => { const reg = await navigator.serviceWorker.getRegistration();
      return { banner: !!document.querySelector('.banner'), version: __s6.updater.version, waiting: !!(reg && reg.waiting) }; }""")
    pg.click('[data-action=season]'); wait_scene(pg, 'season')
    C.check('8.4', r == {'banner': False, 'version': VER['v3'], 'waiting': False} and len(C.errors) == errs0 and state(pg) == after,
            'ошибка скачивания новой версии → игра работает на старой без сообщений', [r, C.errors[errs0:]])

    # ---- без сети после обновления ----
    ctx.set_offline(True)
    pg.reload(); wait_scene(pg, 'title'); shot(pg, 'offline-after-update')
    C.check('8.5', state(pg) == after and pg.query_selector('h1') is not None,
            'после обновлений без сети игра стартует, прогресс на месте')
    ctx.set_offline(False)
    b.close()
finally:
    srv.stop()
    shutil.rmtree(TMP, ignore_errors=True)
C.done()
