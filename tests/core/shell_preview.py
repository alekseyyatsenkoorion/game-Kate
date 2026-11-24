# Превью оболочки с заглушками чужих зон (реестр испытаний и items.json подменяются).
import os
import json, subprocess, time, sys
from playwright.sync_api import sync_playwright
srv = subprocess.Popen(['python3','-m','http.server','8770'], cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errs=[]
try:
  with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    pg = b.new_page(viewport={'width':1024,'height':768}, has_touch=True)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.route('**/src/trials/index.js', lambda r: r.fulfill(content_type='application/javascript', body='export const TRIALS = {};'))
    pg.route('**/data/items.json', lambda r: r.fulfill(content_type='application/json', body=json.dumps({'schema':1,'items':[]})))
    pg.goto('http://localhost:8770/index.html'); pg.wait_for_timeout(1200)
    pg.screenshot(path='/home/claude/sp_title.png')
    pg.mouse.click(512, 463); pg.wait_for_timeout(900); pg.screenshot(path='/home/claude/sp_season.png')
    pg.click('.card.open'); pg.wait_for_timeout(900) if pg.query_selector('.card.open[data-action]') else None
    print('season cards', pg.eval_on_selector_all('.card', 'els => els.map(e => e.className)')[:3])
    b.close()
finally:
    srv.terminate()
print('ERR', errs)
