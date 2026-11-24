#!/usr/bin/env python3
"""Запуск всех автотестов одной командой (tests.md, слой агента).

  npm test                      — все группы всех зон
  npm test -- --zone B          — тесты зоны B + smoke (можно --zone B,D)
  npm test -- --only rules      — одна или несколько групп по id (через запятую)
  npm test -- --list            — показать группы и выйти

Каждая группа — отдельный процесс со своим портом и сервером. Логи — во временной папке (путь печатается).
Строки «XFAIL» — известные баги в чужом коде: группу не валят, но перечисляются в итоге.
Код выхода ≠ 0, если хоть одна группа красная.
"""
import glob, json, os, shutil, socket, subprocess, sys, tempfile, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CFG = json.load(open(os.path.join(ROOT, 'tools', 'zones.json'), encoding='utf-8'))
TIMEOUT = int(os.environ.get('S6_TIMEOUT', '900'))


def arg(name):
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == name and i + 1 < len(a): return a[i + 1]
        if x.startswith(name + '='): return x.split('=', 1)[1]
    return None


def free_port(start):
    for p in range(start, start + 200):
        with socket.socket() as s:
            try: s.bind(('127.0.0.1', p)); return p
            except OSError: continue
    raise RuntimeError('нет свободного порта')


def groups():
    out = []
    for zone, items in CFG['tests'].items():
        for it in items:
            if 'glob' in it:
                for f in sorted(glob.glob(os.path.join(ROOT, it['glob']))):
                    rel = os.path.relpath(f, ROOT).replace(os.sep, '/')
                    if os.path.basename(f).startswith('_'): continue
                    gid = rel.replace('tests/', '').replace('/run.py', '').replace('.py', '').replace('/', '-')
                    out.append(dict(it, id=gid, file=rel, zone=zone, title=it['title'] + ' (' + rel + ')'))
            else:
                out.append(dict(it, zone=zone))
    return out


def webkit_ok():
    code = 'from playwright.sync_api import sync_playwright\nwith sync_playwright() as p: p.webkit.launch().close()'
    try:
        return subprocess.run([sys.executable, '-c', code], capture_output=True, timeout=60).returncode == 0
    except Exception:
        return False


def run_group(g, port, logdir, snap_a):
    env = dict(os.environ, S6_PORT=str(port), PYTHONDONTWRITEBYTECODE='1', S6_BROWSER=g.get('browser', 'chromium'))
    if snap_a: env['S6_SNAP_A'] = snap_a
    srv = None
    if 'cmd' in g:
        cmd = g['cmd']
    else:
        cmd = [sys.executable, os.path.join(ROOT, g['file'])]
        if g.get('server'):
            srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.8)
            cmd.append('http://localhost:%d' % port)
            env['S6_PORT'] = str(free_port(port + 1))
    log = os.path.join(logdir, g['id'] + '.log')
    t0 = time.time()
    try:
        with open(log, 'w', encoding='utf-8') as fh:
            p = subprocess.run(cmd, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, timeout=TIMEOUT)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = 'timeout'
    finally:
        if srv: srv.terminate(); srv.wait()
    lines = open(log, encoding='utf-8', errors='replace').read().splitlines()
    lines = [l for l in lines if not l.startswith('[agent-proxy]') and 'connect_rejected' not in l]
    fails = [l for l in lines if l.lstrip().startswith('FAIL')]
    xfail = [l.strip() for l in lines if l.lstrip().startswith(('XFAIL', 'XPASS'))]
    ok = rc == 0 and not fails
    return ok, rc, time.time() - t0, fails, xfail, lines, log


def main():
    all_g = groups()
    if '--list' in sys.argv:
        for g in all_g: print('%-4s %-22s %s' % (g['zone'], g['id'], g['title']))
        return 0
    zones = arg('--zone'); only = arg('--only')
    sel = all_g
    if zones:
        zs = [z.strip().upper() for z in zones.split(',')]
        bad = [z for z in zs if z not in CFG['tests']]
        if bad: print('Нет такой зоны:', ', '.join(bad), '(есть A, B, C, D)'); return 2
        sel = [g for g in all_g if g['zone'] in zs or g['id'] == CFG['always']]
    if only:
        ids = [x.strip() for x in only.split(',')]
        sel = [g for g in all_g if g['id'] in ids]
        if not sel: print('Нет групп', ids, '— см. --list'); return 2
    # webkit: smoke ещё раз в движке Safari, если браузер установлен
    note = ''
    if any(g.get('webkit') for g in sel):
        if webkit_ok():
            for g in list(sel):
                if g.get('webkit'):
                    sel.insert(sel.index(g) + 1, dict(g, id=g['id'] + '-webkit', browser='webkit', title=g['title'] + ' — WebKit'))
        else:
            note = 'WebKit недоступен (python3 -m playwright install webkit не скачался) — всё гоняется только в Chrome.'
    logdir = tempfile.mkdtemp(prefix='s6-tests-')
    # чужие зоны не пишут снимки зоны A в репозиторий: при --zone без A снимки smoke — во временную папку
    snap_a = None
    if zones and 'A' not in [z.strip().upper() for z in zones.split(',')]:
        snap_a = os.path.join(logdir, 'snapshots-A')
    print('Группы: %d. Логи: %s' % (len(sel), logdir))
    if note: print(note)
    res = []; port = 8800
    for g in sel:
        port = free_port(port + 5)
        print('… %-4s %-22s %s' % (g['zone'], g['id'], g['title']), flush=True)
        ok, rc, dt, fails, xfail, lines, log = run_group(g, port, logdir, snap_a)
        res.append((g, ok, xfail))
        print('  %s %s за %d с%s' % ('✓' if ok else '✗', 'зелёная' if ok else 'КРАСНАЯ (код %s)' % rc, dt,
                                    (', известных провалов: %d' % len([x for x in xfail if x.startswith('XFAIL')])) if xfail else ''), flush=True)
        if not ok:
            for l in (fails or lines[-25:])[:25]: print('    | ' + l)
            print('    лог: ' + log)
    green = sum(1 for _, ok, _ in res if ok)
    print('\nИтог: %d из %d групп зелёные.' % (green, len(res)))
    red = [g['id'] for g, ok, _ in res if not ok]
    if red: print('Красные: ' + ', '.join(red))
    xs = [(g['id'], x) for g, _, xf in res for x in xf]
    if xs:
        print('Известные провалы (баги в чужом коде, см. отчёт):')
        for gid, x in xs: print('  [%s] %s' % (gid, x[:220]))
    if note: print(note)
    return 1 if red else 0


if __name__ == '__main__':
    sys.exit(main())
