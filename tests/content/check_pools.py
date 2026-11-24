#!/usr/bin/env python3
"""Зона C — проверка пулов заданий: shirma, bagazhnik, misterx (contracts.md §12.2, spec.md §3.1).

python3 tests/content/check_pools.py      — код выхода 1 при ошибке

Решатель Мистера Икс (единственность решения) — отдельно: tests/content/misterx_solver.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data'
TYPES = ('shirma', 'bagazhnik', 'misterx')
MIN_PER_LEVEL = 5
MIN_ITEMS = 40
NEW_ITEMS = ['coffee', 'perfume', 'orange', 'soap', 'bread', 'rose', 'cinnamon', 'lemon',
             'violin', 'typewriter', 'telephone', 'camera', 'globe', 'compass', 'teapot', 'mirror',
             'vase', 'fan', 'hourglass', 'gramophone', 'person-ballerina', 'person-violinist',
             'person-chef', 'person-doctor', 'person-magician', 'person-detective']
SMELLS = {'coffee', 'perfume', 'orange', 'soap', 'bread', 'rose', 'cinnamon', 'lemon'}

# Ширма, уровень 3: на какой другой вариант указывает ложная подсказка.
# В данных этого поля нет (контракт его не предусматривает) — держим здесь, чтобы проверять.
SHIRMA_FAKE_POINTS = {
    'shirma-3-001': 'person-ballerina',
    'shirma-3-002': 'person-doctor',
    'shirma-3-003': 'clock',
    'shirma-3-004': 'person-detective',
    'shirma-3-005': 'telephone',
}
SHIRMA_OPTIONS = {1: 4, 2: 5, 3: 6}
SHIRMA_KINDS = {'silhouette', 'sound', 'warmth', 'detail', 'smell'}
HINT_MAX = 60

BAG_CARS = {1: 6, 2: 10, 3: 15}
BAG_FAKES = {1: 0, 2: 1, 3: 2}
BAG_KINDS = {'sag', 'fog', 'track', 'sound', 'smell'}
BAG_BODIES = {'sedan', 'hatch', 'suv', 'van'}

MX_SIZE = {1: (3, 3), 2: (4, 4), 3: (4, 5)}   # категорий × значений
MX_CLUES_L3 = (8, 12)
MX_RULE_LEN = {'is': 4, 'not': 4, 'link': 5, 'unlink': 5}

errors = []


def fail(msg):
    errors.append(msg)


def load(rel):
    try:
        return json.loads((DATA / rel).read_text(encoding='utf-8'))
    except Exception as e:  # noqa: BLE001
        fail(f'{rel}: не читается/битый JSON ({e})')
        return None


def stems(label):
    """Корни слов названия (для проверки «подсказка не называет ответ»)."""
    return [w.lower()[:5] for w in re.findall(r'[А-Яа-яЁё]+', label) if len(w) >= 4]


def check_items(texts):
    d = load('items.json')
    if d is None:
        return {}
    if d.get('schema') != 1:
        fail('items.json: schema ≠ 1')
    items = d.get('items', [])
    ids = [i.get('id') for i in items]
    for i, n in Counter(ids).items():
        if n > 1:
            fail(f'items.json: повтор id {i}')
    if len(set(ids)) < MIN_ITEMS:
        fail(f'items.json: предметов {len(set(ids))}, нужно ≥ {MIN_ITEMS}')
    for i in NEW_ITEMS:
        if i not in ids:
            fail(f'items.json: нет предмета {i}')
    for x in items:
        if set(x) != {'id', 'labelKey', 'art'}:
            fail(f'items.json: поля у {x.get("id")}: {sorted(x)}')
        if x.get('labelKey') != f'item.{x.get("id")}' or x.get('art') != f'item-{x.get("id")}':
            fail(f'items.json: labelKey/art у {x.get("id")}')
        if x.get('labelKey') not in texts:
            fail(f'texts.json: нет {x.get("labelKey")}')
    return {x['id']: texts.get(x['labelKey'], '') for x in items}


def need_text(texts, key, where):
    if not isinstance(key, str) or key not in texts:
        fail(f'{where}: нет текста {key!r} в texts.json')
        return ''
    return texts[key]


def check_envelope(t, d):
    if d.get('schema') != 1 or d.get('type') != t:
        fail(f'{t}.json: schema/type')
    tasks = d.get('tasks', [])
    ids = [x.get('id') for x in tasks]
    for i, n in Counter(ids).items():
        if n > 1:
            fail(f'{t}: повтор id {i}')
    per = Counter()
    for x in tasks:
        m = re.fullmatch(rf'{t}-([1-3])-(\d{{3}})', str(x.get('id')))
        if not m:
            fail(f'{t}: id {x.get("id")!r} не по шаблону {t}-<ур>-<nnn>')
        elif int(m.group(1)) != x.get('level'):
            fail(f'{x["id"]}: уровень в id ≠ level {x.get("level")}')
        if not isinstance(x.get('payload'), dict):
            fail(f'{x.get("id")}: нет payload')
        per[x.get('level')] += 1
    for lvl in (1, 2, 3):
        if per[lvl] < MIN_PER_LEVEL:
            fail(f'{t}: уровень {lvl} — заданий {per[lvl]}, нужно ≥ {MIN_PER_LEVEL}')
    return [x for x in tasks if isinstance(x.get('payload'), dict) and x.get('level') in (1, 2, 3)]


def check_shirma(tasks, texts, items):
    for x in tasks:
        tid, lvl, p = x['id'], x['level'], x['payload']
        opts, ans, hints = p.get('options', []), p.get('answer'), p.get('hints', [])
        if len(opts) != SHIRMA_OPTIONS[lvl] or len(set(opts)) != len(opts):
            fail(f'{tid}: вариантов {len(opts)} (нужно {SHIRMA_OPTIONS[lvl]}, без повторов)')
        for o in opts:
            if o not in items:
                fail(f'{tid}: вариант {o} не найден в items.json')
        if ans not in opts:
            fail(f'{tid}: answer не среди options')
        lo, hi = (4, 5) if lvl == 3 else (3, 5)
        if not lo <= len(hints) <= hi:
            fail(f'{tid}: подсказок {len(hints)}, нужно {lo}–{hi}')
        if not hints or hints[0].get('kind') != 'silhouette' or hints[0].get('fake'):
            fail(f'{tid}: первая подсказка должна быть настоящей silhouette')
        for h in hints:
            if h.get('kind') not in SHIRMA_KINDS or not isinstance(h.get('fake'), bool):
                fail(f'{tid}: подсказка {h}')
            txt = need_text(texts, h.get('textKey'), tid)
            if len(txt) > HINT_MAX:
                fail(f'{tid}: {h.get("textKey")} длиннее {HINT_MAX} символов ({len(txt)})')
            low = txt.lower()
            for s in stems(items.get(ans, '')):
                if s in low:
                    fail(f'{tid}: {h.get("textKey")} называет ответ («{s}»)')
        fakes = [h for h in hints if h.get('fake')]
        if lvl < 3 and fakes:
            fail(f'{tid}: ложные подсказки только на уровне 3')
        if lvl == 2 and not any(h.get('kind') == 'smell' and not h.get('fake') for h in hints):
            fail(f'{tid}: на уровне 2 нужна настоящая подсказка-запах')
        if lvl == 2 and not (ans in SMELLS or any(o in SMELLS for o in opts)):
            fail(f'{tid}: на уровне 2 нужны предметы с запахом')
        if lvl == 3:
            if len(fakes) != 1:
                fail(f'{tid}: ложных подсказок {len(fakes)}, нужно ровно 1')
            pt = SHIRMA_FAKE_POINTS.get(tid)
            if pt is None or pt not in opts or pt == ans:
                fail(f'{tid}: ложная подсказка должна указывать на другой вариант (SHIRMA_FAKE_POINTS)')


def check_bagazhnik(tasks, texts):
    for x in tasks:
        tid, lvl, p = x['id'], x['level'], x['payload']
        cars = p.get('cars', [])
        if len(cars) != BAG_CARS[lvl]:
            fail(f'{tid}: машин {len(cars)}, нужно {BAG_CARS[lvl]}')
        ids = [c.get('id') for c in cars]
        if len(set(ids)) != len(ids):
            fail(f'{tid}: повтор id машины')
        looks = [(c.get('body'), c.get('color')) for c in cars]
        if len(set(looks)) != len(looks):
            fail(f'{tid}: две одинаковые машины (кузов+цвет)')
        target = next((c for c in cars if c.get('id') == p.get('target')), None)
        if target is None:
            fail(f'{tid}: target не найден')
            continue
        fakes = 0
        for c in cars:
            if c.get('body') not in BAG_BODIES:
                fail(f'{tid}/{c.get("id")}: body {c.get("body")!r}')
            if not re.fullmatch(r'#[0-9a-f]{6}', str(c.get('color'))):
                fail(f'{tid}/{c.get("id")}: color {c.get("color")!r}')
            for k in c.get('clues', []):
                if k.get('kind') not in BAG_KINDS or not isinstance(k.get('fake'), bool):
                    fail(f'{tid}/{c.get("id")}: улика {k}')
                need_text(texts, k.get('textKey'), tid)
                if k.get('fake'):
                    fakes += 1
                    if c is target:
                        fail(f'{tid}: ложная улика у цели')
        real = [k for k in target.get('clues', []) if not k.get('fake')]
        if len(real) < 2:
            fail(f'{tid}: у цели настоящих улик {len(real)}, нужно ≥ 2')
        if fakes != BAG_FAKES[lvl]:
            fail(f'{tid}: ложных улик {fakes}, нужно {BAG_FAKES[lvl]}')
        if any(len(c.get('clues', [])) >= len(target.get('clues', [])) for c in cars if c is not target):
            fail(f'{tid}: у машины-обманки улик не меньше, чем у цели — не отличить')
        keys = [k.get('textKey') for c in cars for k in c.get('clues', [])]
        if len(set(keys)) != len(keys):
            fail(f'{tid}: один и тот же текст улики дважды')
    for lvl in (2, 3):
        pos = {[c['id'] for c in x['payload']['cars']].index(x['payload']['target'])
               for x in tasks if x['level'] == lvl and x['payload'].get('target')}
        if len(pos) < 3:
            fail(f'bagazhnik уровень {lvl}: цель почти всегда на одном месте')


def check_misterx(tasks, texts):
    for x in tasks:
        tid, lvl, p = x['id'], x['level'], x['payload']
        ncat, nval = MX_SIZE[lvl]
        cats = p.get('categories', [])
        people = p.get('people', [])
        if len(cats) != ncat:
            fail(f'{tid}: категорий {len(cats)}, нужно {ncat}')
        if len(people) != nval:
            fail(f'{tid}: людей {len(people)}, нужно {nval}')
        pids = [q.get('id') for q in people]
        if len(set(pids)) != len(pids) or 'x' not in pids:
            fail(f'{tid}: люди — повторы или нет "x"')
        if p.get('ask') != 'x':
            fail(f'{tid}: ask должен быть "x"')
        for q in people:
            need_text(texts, q.get('labelKey'), tid)
        vals = {}
        for c in cats:
            need_text(texts, c.get('labelKey'), tid)
            vs = [v.get('id') for v in c.get('values', [])]
            if len(vs) != nval or len(set(vs)) != nval:
                fail(f'{tid}: категория {c.get("key")} — значений {len(vs)}, нужно {nval} разных')
            for v in c.get('values', []):
                need_text(texts, v.get('labelKey'), tid)
            vals[c.get('key')] = set(vs)
        if len(vals) != len(cats):
            fail(f'{tid}: повтор ключа категории')
        sol = p.get('solution', {})
        if set(sol) != set(pids):
            fail(f'{tid}: solution не для всех людей')
        for c, vs in vals.items():
            got = [sol.get(q, {}).get(c) for q in pids]
            if sorted(map(str, got)) != sorted(vs):
                fail(f'{tid}: в solution категория {c} — каждое значение должно быть ровно у одного')
        clues = p.get('clues', [])
        kinds = Counter()
        for k in clues:
            r = k.get('rule')
            txt = need_text(texts, k.get('textKey'), tid)
            if not isinstance(r, list) or r[0] not in MX_RULE_LEN or len(r) != MX_RULE_LEN[r[0]]:
                fail(f'{tid}: rule {r!r}')
                continue
            kinds[r[0]] += 1
            if r[0] in ('is', 'not'):
                ok = r[1] in pids and r[2] in vals and r[3] in vals[r[2]]
                lab = texts.get(next((q['labelKey'] for q in people if q['id'] == r[1]), ''), '#')
                if ok and not txt.startswith(lab + ' '):
                    fail(f'{tid}: {k["textKey"]} — текст не про того человека, что в rule')
            else:
                ok = r[1] in vals and r[3] in vals and r[1] != r[3] and r[2] in vals[r[1]] and r[4] in vals[r[3]]
            if not ok:
                fail(f'{tid}: rule ссылается на несуществующее: {r}')
            if (r[0] in ('not', 'unlink')) != (' не ' in f' {txt}'):
                fail(f'{tid}: {k["textKey"]} — отрицание в тексте не совпадает с rule')
        if lvl == 3:
            lo, hi = MX_CLUES_L3
            if not lo <= len(clues) <= hi:
                fail(f'{tid}: улик {len(clues)}, нужно {lo}–{hi}')
            if kinds['link'] + kinds['unlink'] < len(clues) // 2:
                fail(f'{tid}: на уровне 3 нужны в основном улики-связки, а не прямые is')
            if any(c['rule'][0] == 'is' and c['rule'][1] == 'x' for c in clues):
                fail(f'{tid}: на уровне 3 Мистер Икс не называется напрямую')


def main():
    t = load('texts.json')
    texts = (t or {}).get('texts', {})
    items = check_items(texts)
    for typ in TYPES:
        d = load(f'trials/{typ}.json')
        if d is None:
            continue
        tasks = check_envelope(typ, d)
        if typ == 'shirma':
            check_shirma(tasks, texts, items)
        elif typ == 'bagazhnik':
            check_bagazhnik(tasks, texts)
        else:
            check_misterx(tasks, texts)
    if errors:
        print('CHECK-POOLS: ОШИБКИ')
        for e in errors:
            print('  ✗', e)
        sys.exit(1)
    print(f'CHECK-POOLS: ок — {len(items)} предметов; shirma, bagazhnik, misterx — по ≥{MIN_PER_LEVEL} '
          f'заданий на уровни 1–3, ограничения spec.md §3.1 и contracts.md §12.2 выполнены')


if __name__ == '__main__':
    main()
