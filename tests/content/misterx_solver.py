#!/usr/bin/env python3
"""Зона C — решатель Мистера Икс (tests.md 2.6).

python3 tests/content/misterx_solver.py

Для каждого задания data/trials/misterx.json:
  1) полный перебор назначений (каждая категория — перестановка значений по людям,
     с отсечением по уликам) — решение должно быть ровно одно и совпадать с solution;
  2) «человеческая» проверка: задание решается цепочкой простых выводов
     (исключения в таблице + связки), без угадывания.
Код выхода 1 при ошибке.
"""
import json
import sys
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = {'is': 4, 'not': 4, 'link': 5, 'unlink': 5}


def rule_cats(r):
    return {r[2]} if r[0] in ('is', 'not') else {r[1], r[3]}


def holds(r, asg):
    """asg: {cat: {person: value}} — проверка улики на (частичном) назначении,
    в котором все категории улики уже назначены."""
    k = r[0]
    if k == 'is':
        return asg[r[2]][r[1]] == r[3]
    if k == 'not':
        return asg[r[2]][r[1]] != r[3]
    _, c1, v1, c2, v2 = r
    who = next(p for p, v in asg[c1].items() if v == v1)
    same = asg[c2][who] == v2
    return same if k == 'link' else not same


def solve(p, limit=2):
    """Все решения (не больше limit) перебором с отсечением."""
    people = [x['id'] for x in p['people']]
    cats = [c['key'] for c in p['categories']]
    vals = {c['key']: [v['id'] for v in c['values']] for c in p['categories']}
    rules = [c['rule'] for c in p['clues']]
    # перестановки каждой категории, отфильтрованные по одиночным уликам
    perms = {}
    for c in cats:
        unary = [r for r in rules if rule_cats(r) == {c}]
        perms[c] = []
        for perm in permutations(vals[c]):
            a = {c: dict(zip(people, perm))}
            if all(holds(r, a) for r in unary):
                perms[c].append(a[c])
    out = []

    def rec(i, asg):
        if len(out) >= limit:
            return
        if i == len(cats):
            out.append({p_: {c: asg[c][p_] for c in cats} for p_ in people})
            return
        c = cats[i]
        done = set(cats[:i + 1])
        check = [r for r in rules if c in rule_cats(r) and rule_cats(r) <= done and len(rule_cats(r)) > 1]
        for perm in perms[c]:
            asg[c] = perm
            if all(holds(r, asg) for r in check):
                rec(i + 1, asg)
            del asg[c]

    rec(0, {})
    return out


def propagate(p):
    """Простые выводы, как в таблице на бумаге. True, если всё решено без угадывания."""
    people = [x['id'] for x in p['people']]
    cats = [c['key'] for c in p['categories']]
    vals = {c['key']: [v['id'] for v in c['values']] for c in p['categories']}
    rules = [c['rule'] for c in p['clues']]
    poss = {q: {c: set(vals[c]) for c in cats} for q in people}
    changed = True
    while changed:
        changed = False

        def drop(q, c, v):
            nonlocal changed
            if v in poss[q][c]:
                poss[q][c].discard(v)
                changed = True

        def fix(q, c, v):
            for w in list(poss[q][c]):
                if w != v:
                    drop(q, c, w)

        for r in rules:
            if r[0] == 'is':
                fix(r[1], r[2], r[3])
            elif r[0] == 'not':
                drop(r[1], r[2], r[3])
            else:
                _, c1, v1, c2, v2 = r
                for q in people:
                    if r[0] == 'link':
                        # v1 и v2 у одного и того же человека
                        if v1 not in poss[q][c1]:
                            drop(q, c2, v2)
                        if v2 not in poss[q][c2]:
                            drop(q, c1, v1)
                        if poss[q][c1] == {v1}:
                            fix(q, c2, v2)
                        if poss[q][c2] == {v2}:
                            fix(q, c1, v1)
                    else:
                        if poss[q][c1] == {v1}:
                            drop(q, c2, v2)
                        if poss[q][c2] == {v2}:
                            drop(q, c1, v1)
        # таблица: значение у одного — вычёркиваем у других; единственное место — ставим
        for c in cats:
            for q in people:
                if len(poss[q][c]) == 1:
                    v = next(iter(poss[q][c]))
                    for o in people:
                        if o != q:
                            drop(o, c, v)
            for v in vals[c]:
                where = [q for q in people if v in poss[q][c]]
                if len(where) == 1:
                    fix(where[0], c, v)
    return all(len(poss[q][c]) == 1 for q in people for c in cats)


def main():
    path = ROOT / 'data' / 'trials' / 'misterx.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    errors = []
    for t in data['tasks']:
        tid, p = t['id'], t['payload']
        bad = [c['rule'] for c in p['clues'] if c['rule'][0] not in RULES or len(c['rule']) != RULES[c['rule'][0]]]
        if bad:
            errors.append(f'{tid}: неверная форма rule {bad}')
            continue
        sols = solve(p)
        if len(sols) != 1:
            errors.append(f'{tid}: решений {len(sols) if len(sols) < 2 else "≥2"}, нужно ровно 1')
            continue
        if sols[0] != p['solution']:
            errors.append(f'{tid}: решатель нашёл другое решение, чем solution')
            continue
        if not propagate(p):
            errors.append(f'{tid}: решение единственное, но без угадывания не выводится')
        # минимальность: без любой улики решение перестаёт быть единственным
        extra = []
        for i in range(len(p['clues'])):
            q = dict(p, clues=p['clues'][:i] + p['clues'][i + 1:])
            if len(solve(q)) == 1:
                extra.append(p['clues'][i]['textKey'])
        if extra:
            errors.append(f'{tid}: лишние улики (без них решение всё равно одно): {extra}')
    if errors:
        print('MISTERX-SOLVER: ОШИБКИ')
        for e in errors:
            print('  ✗', e)
        sys.exit(1)
    print(f'MISTERX-SOLVER: ок — {len(data["tasks"])} заданий, у каждого ровно одно решение = solution, '
          f'выводится без угадывания, лишних улик нет')


if __name__ == '__main__':
    main()
