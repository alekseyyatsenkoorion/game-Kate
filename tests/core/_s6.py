# Общие помощники тестов зоны A: свой HTTP-сервер, запуск браузера, проверки с «известным провалом».
# Не тест — импортируется из tests/core/*.py. Сервер поднимается в этом же процессе (поток),
# корень и задержки можно менять на лету — это нужно тесту обновления (группа 8).
import functools, os, socket, sys, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BROWSER = os.environ.get('S6_BROWSER', 'chromium')       # chromium | webkit
SNAP_A = os.environ.get('S6_SNAP_A') or os.path.join(ROOT, 'tests', 'snapshots', 'A')


def free_port(prefer):
    for p in [prefer] + list(range(prefer + 1, prefer + 50)):
        with socket.socket() as s:
            try: s.bind(('127.0.0.1', p)); return p
            except OSError: continue
    raise RuntimeError('нет свободного порта')


class Server:
    """Статический сервер как у GitHub Pages (Cache-Control: max-age=600). root, delay, missing меняются на лету."""
    def __init__(self, root=ROOT, port=None):
        self.root = root
        self.delay = {}            # путь → секунды задержки ответа
        self.missing = set()       # пути, на которые отвечаем 404
        self.port = free_port(int(port or os.environ.get('S6_PORT') or 8790))
        srv = self

        class H(SimpleHTTPRequestHandler):
            def translate_path(self, path):
                self.directory = srv.root
                return SimpleHTTPRequestHandler.translate_path(self, path)
            def do_GET(self):
                p = self.path.split('?')[0].lstrip('/')
                if p in srv.delay: time.sleep(srv.delay[p])
                if p in srv.missing: self.send_error(404); return
                # без ответов 304: копии версий собираются в одну секунду, и по Last-Modified их не различить
                del self.headers['If-Modified-Since']
                return SimpleHTTPRequestHandler.do_GET(self)
            def end_headers(self):
                self.send_header('Cache-Control', 'max-age=600')
                SimpleHTTPRequestHandler.end_headers(self)
            def log_message(self, *a): pass

        self.httpd = ThreadingHTTPServer(('127.0.0.1', self.port), functools.partial(H, directory=root))
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = 'http://localhost:%d/' % self.port

    def stop(self):
        self.httpd.shutdown(); self.httpd.server_close()


def launch(p):
    if BROWSER == 'webkit':
        return p.webkit.launch()
    return p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])


class Checks:
    """PASS/FAIL построчно. known='...' — известный баг в чужом коде: провал печатается как XFAIL и группу не валит."""
    def __init__(self, title):
        self.title = title; self.fail = 0; self.n = 0; self.errors = []
        print('== ' + title + ' (' + BROWSER + ')', flush=True)

    def check(self, num, cond, msg, info='', known=None):
        self.n += 1
        if cond:
            tag = 'XPASS' if known else 'PASS'
        elif known:
            tag = 'XFAIL'
        else:
            tag = 'FAIL'; self.fail += 1
        line = '%s %s %s' % (tag, num, msg)
        if info and not cond: line += ' — ' + str(info)
        if known and not cond: line += ' [известный баг: ' + known + ']'
        if known and cond: line += ' [был известный баг — похоже, исправлен, снимите пометку]'
        print(line, flush=True)
        return cond

    def watch(self, pg):
        pg.on('pageerror', lambda e: self.errors.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: self.errors.append('console: ' + m.text)
              if m.type == 'error' and 'Failed to load resource' not in m.text else None)

    def done(self):
        if self.errors:
            print('ОШИБКИ СТРАНИЦЫ:', self.errors[:10])
        print('Итог: %d проверок, провалено %d' % (self.n, self.fail), flush=True)
        sys.exit(1 if self.fail else 0)


# ---------- игра ----------
def wait_scene(pg, sid, timeout=10000):
    pg.wait_for_function("(id) => window.__s6 && __s6.scenes && __s6.scenes.current().id === id && !__s6.scenes.busy",
                         arg=sid, timeout=timeout)
    pg.wait_for_timeout(150)


def boot(pg, url, timeout=15000):
    pg.goto(url)
    wait_scene(pg, 'title', timeout)


def fix_date(pg, y, m, d):
    """Подменить дату DayLock (месяц 1..12). Действует до перезагрузки."""
    pg.evaluate("([y,m,d]) => { __s6.dayLock.now = () => new Date(y, m - 1, d, 12, 0, 0); }", [y, m, d])


def task_payload(pg, type_, level, idx=None):
    return pg.evaluate("""async ([t, l, i]) => {
        const run = __s6.progress.run(); const id = run.taskIds[i == null ? run.idx : i];
        return (await __s6.content.pool(t, l)).find(x => x.id === id).payload; }""", [type_, level, idx])


def play_episode1(pg):
    """title → season → intro → Ширма 1 (одна ошибка, затем верный ответ) → result."""
    pg.click('[data-action=season]'); wait_scene(pg, 'season')
    pg.click('.card.open[data-action=ep]'); wait_scene(pg, 'intro')
    pg.click('[data-action=start]'); wait_scene(pg, 'trial')
    pg.wait_for_selector('[data-opt]')
    pl = task_payload(pg, 'shirma', 1)
    pg.click('[data-opt="%s"]' % pl['answer'])
    wait_scene(pg, 'result', 15000)
