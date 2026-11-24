# Интеграция (зона A): режим теста → выпуски 3 (Мистер Икс 1), 7 (Багажник 2), 8 (Мистер Икс 2), 11 (Багажник 3 + Ширма 3). Снимки tests/snapshots/A/lv-*.png
import os, sys, json
from playwright.sync_api import sync_playwright
from _s6 import Server, SNAP_A, launch
OUT=SNAP_A+'/'; os.makedirs(OUT, exist_ok=True)
srv=Server(port=os.environ.get('S6_PORT') or 8773)
errs=[]; res=[]
def ck(c,m): res.append(('PASS ' if c else 'FAIL ')+m)
def pool(pg,t,l,tid): return pg.evaluate("(async()=> (await __s6.content.pool('%s',%d)).find(x=>x.id==='%s').payload)()"%(t,l,tid))
try:
 with sync_playwright() as p:
  b=launch(p)
  pg=b.new_page(viewport={'width':1024,'height':768},has_touch=True)
  pg.on('pageerror',lambda e:errs.append(str(e)))
  pg.on('console',lambda m: errs.append(m.text) if m.type=='error' and '404' not in m.text else None)
  pg.goto(srv.url); pg.wait_for_timeout(1500)
  pg.evaluate("__s6.progress.setSettings({test:true})")
  def jump(n):
    pg.evaluate("__s6.scenes.replace('debug')"); pg.wait_for_timeout(600)
    pg.click('[data-go="%d"]'%n); pg.wait_for_timeout(700)
    pg.click('[data-action=start]'); pg.wait_for_timeout(1300)
  def solve_mx(level):
    tid=pg.evaluate('__s6.progress.run().taskIds[__s6.progress.run().idx]'); pl=pool(pg,'misterx',level,tid)
    for cat,val in pl['solution'][pl['ask']].items(): pg.click('[data-mx-chip="%s:%s"]'%(cat,val)); pg.wait_for_timeout(80)
    pg.click('[data-mx=submit]'); pg.wait_for_timeout(4800)
  def solve_bag(level):
    tid=pg.evaluate('__s6.progress.run().taskIds[__s6.progress.run().idx]'); pl=pool(pg,'bagazhnik',level,tid)
    pg.click('[data-car="%s"]'%pl['target']); pg.wait_for_timeout(300); pg.click('[data-bz=choose]'); pg.wait_for_timeout(4500)
  def solve_sh(level):
    tid=pg.evaluate('__s6.progress.run().taskIds[__s6.progress.run().idx]'); pl=pool(pg,'shirma',level,tid)
    pg.click('[data-opt="%s"]'%pl['answer']); pg.wait_for_timeout(4500)
  def solve_km(level):
    tid=pg.evaluate('__s6.progress.run().taskIds[__s6.progress.run().idx]'); pl=pool(pg,'komnata',level,tid)
    objs={o['id']:o for o in pl['objects']}
    for f in pl['find']:
      o=objs[f]; x=32+o['x']*800; y=132+o['y']*600
      pg.mouse.click(x,y); pg.wait_for_timeout(150); pg.mouse.click(x,y); pg.wait_for_timeout(250)
    pg.wait_for_timeout(5000)
  def solve_fo(level):
    tid=pg.evaluate('__s6.progress.run().taskIds[__s6.progress.run().idx]'); pl=pool(pg,'foto',level,tid)
    texts=[pg.evaluate('__s6.content.text(%s)'%json.dumps(st['textKey'])) for st in pl['statements'] if st['true']]
    for tx in texts:
      pg.evaluate('(tx)=>{ const n=[...document.querySelectorAll("[data-st]")].find(e=>e.querySelector(".fo-st-tx").textContent===tx); const r=n.getBoundingClientRect(); window.__pt=[r.x+r.width/2,r.y+r.height/2]; }', tx)
      x,y=pg.evaluate('window.__pt'); pg.mouse.click(x,y); pg.wait_for_timeout(120)
    pg.click('[data-fo=check]'); pg.wait_for_timeout(8000)
  jump(4); pg.screenshot(path=OUT+'lv-foto1.png'); solve_fo(1); ck(pg.query_selector('.big-stars') is not None,'выпуск 4 (Фото-дело 1) пройден')
  jump(10); solve_fo(2); ck(pg.query_selector('.big-stars') is not None,'выпуск 10 (Фото-дело 2) пройден')
  jump(12); solve_mx(3); pg.wait_for_timeout(1500); solve_fo(3); pg.wait_for_timeout(1500)
  pg.mouse.click(432,432); pg.wait_for_timeout(300); solve_km(3)
  ck(pg.query_selector('.big-stars') is not None,'выпуск 12 (финал: Мистер Икс 3 + Фото-дело 3 + Тёмная комната 3) пройден'); pg.screenshot(path=OUT+'lv-result12.png')
  pg.click('[data-action=solution]'); pg.wait_for_timeout(500); pg.screenshot(path=OUT+'lv-solution.png'); ck(pg.query_selector('.modal') is not None,'разгадка дела показана'); pg.click('.modal .btn')
  pg.evaluate("__s6.progress.update(d=>{d.case.clues=__s6.content.caseData.clues.map(c=>c.id)})")
  pg.click('[data-action=season]'); pg.wait_for_timeout(600); pg.click('[data-action=diary]'); pg.wait_for_timeout(600)
  ck(len(pg.query_selector_all('.clue'))==22,'в дневнике 22 улики'); pg.mouse.wheel(0,600); pg.wait_for_timeout(400); pg.screenshot(path=OUT+'lv-diary22.png')
  jump(5); pg.mouse.click(432,432); pg.wait_for_timeout(400); pg.screenshot(path=OUT+'lv-komnata1.png'); solve_km(1)
  ck(pg.query_selector('.big-stars') is not None,'выпуск 5 (Тёмная комната 1) пройден'); pg.screenshot(path=OUT+'lv-result5.png')
  jump(9); solve_km(2); ck(pg.query_selector('.big-stars') is not None,'выпуск 9 (Тёмная комната 2) пройден')
  jump(3); pg.wait_for_timeout(300); pg.screenshot(path=OUT+'lv-misterx1.png'); solve_mx(1)
  ck(pg.query_selector('.big-stars') is not None,'выпуск 3 (Мистер Икс 1) пройден'); pg.screenshot(path=OUT+'lv-result3.png')
  jump(7); pg.screenshot(path=OUT+'lv-bag2.png'); solve_bag(2); ck(pg.query_selector('.big-stars') is not None,'выпуск 7 (Багажник 2) пройден')
  jump(8); pg.screenshot(path=OUT+'lv-misterx2.png'); solve_mx(2); ck(pg.query_selector('.big-stars') is not None,'выпуск 8 (Мистер Икс 2) пройден')
  jump(11); pg.screenshot(path=OUT+'lv-bag3.png'); solve_bag(3); pg.wait_for_timeout(1200); pg.screenshot(path=OUT+'lv-shirma3.png'); solve_sh(3)
  ck(pg.query_selector('.big-stars') is not None,'выпуск 11 (Багажник 3 + Ширма 3) пройден'); pg.screenshot(path=OUT+'lv-result11.png')
  b.close()
finally: srv.stop()
print('\n'.join(res)); print('ERRORS',errs)
sys.exit(1 if errs or any(x.startswith('FAIL') for x in res) else 0)
