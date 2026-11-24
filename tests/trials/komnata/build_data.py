# Сборка data/trials/komnata.json и tests/trials/fixtures/texts-komnata.json из каталога предметов.
# Каталог — предметы, реально видимые на картинках assets/gpt/room-1..3.webp (координаты — доли картинки).
# Запуск: python3 tests/trials/komnata/build_data.py
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# id: (название, x, y, r)
CATALOG = {
 'room-1': {   # кладовка
  'kettle': ('медный чайник', 0.115, 0.427, 0.035),
  'coffeepot': ('серебряный кофейник', 0.575, 0.433, 0.022),
  'pitcher': ('белый кувшин с розами', 0.632, 0.433, 0.028),
  'hourglass': ('песочные часы', 0.455, 0.193, 0.02),
  'sphere': ('латунная сфера с кольцами', 0.52, 0.187, 0.028),
  'globe': ('глобус', 0.598, 0.177, 0.032),
  'ship': ('модель парусника', 0.375, 0.187, 0.04),
  'cage': ('золотая птичья клетка', 0.818, 0.10, 0.035),
  'hat': ('фетровая шляпа на вешалке', 0.84, 0.20, 0.03),
  'lamp': ('керосиновая лампа', 0.978, 0.093, 0.02),
  'horse': ('лошадка-качалка', 0.955, 0.393, 0.032),
  'goblet': ('латунный кубок', 0.09, 0.097, 0.02),
  'jug': ('бело-синий кувшин', 0.21, 0.14, 0.022),
  'lavender': ('пучок лаванды', 0.29, 0.225, 0.028),
  'bell': ('латунный колокольчик', 0.057, 0.41, 0.016),
  'brushes': ('кружка с кистями', 0.228, 0.41, 0.022),
  'oranges': ('банка с дольками апельсина', 0.098, 0.247, 0.025),
  'nuts': ('банка с орехами на левой полке', 0.22, 0.28, 0.022),
  'beans': ('банка с белой фасолью', 0.357, 0.32, 0.022),
  'pasta': ('банка с макаронами-бантиками', 0.452, 0.32, 0.022),
  'cinnamon': ('банка с палочками корицы', 0.587, 0.32, 0.018),
  'decanter': ('хрустальный графин', 0.635, 0.313, 0.022),
  'flowerbox': ('коробка в цветочек', 0.442, 0.407, 0.025),
  'hatbox': ('круглая коробка на верхней полке', 0.45, 0.06, 0.03),
  'scrolls': ('свёрнутые свитки', 0.693, 0.057, 0.025),
  'bowl': ('фарфоровая супница', 0.69, 0.437, 0.022),
  'perfume': ('стеклянный флакон', 0.05, 0.543, 0.016),
  'casket': ('серебряная шкатулка', 0.145, 0.527, 0.022),
  'sugar': ('фарфоровая сахарница', 0.22, 0.653, 0.018),
  'binoculars': ('старый бинокль', 0.197, 0.75, 0.022),
  'broom': ('метла', 0.302, 0.79, 0.025),
  'bucket': ('жестяное ведро', 0.345, 0.745, 0.028),
  'chest': ('кованый сундук', 0.51, 0.735, 0.06),
  'towel': ('полотенце в полоску', 0.535, 0.57, 0.022),
  'sack': ('холщовый мешок', 0.68, 0.567, 0.032),
  'firewood': ('корзина с дровами', 0.683, 0.74, 0.035),
  'umbrella': ('чёрный зонт', 0.76, 0.653, 0.025),
  'stand': ('латунная подставка для зонтов', 0.763, 0.80, 0.025),
  'lantern': ('фонарь на нижней полке', 0.908, 0.677, 0.022),
  'vase': ('кувшин с сиреневыми цветами', 0.94, 0.547, 0.025),
 },
 'room-2': {   # кабинет
  'cat': ('фарфоровая кошка у окна', 0.083, 0.347, 0.022),
  'cage': ('клетка с жёлтой птичкой', 0.133, 0.313, 0.028),
  'bust': ('гипсовый бюст', 0.268, 0.10, 0.028),
  'telescope': ('подзорная труба на треноге', 0.263, 0.207, 0.028),
  'coral': ('белый коралл', 0.388, 0.22, 0.022),
  'butterfly': ('синяя бабочка под колпаком', 0.45, 0.233, 0.022),
  'shell': ('окаменелая раковина', 0.298, 0.327, 0.024),
  'urn': ('стеклянная ваза с крышкой', 0.393, 0.127, 0.016),
  'bottles': ('зелёные склянки', 0.313, 0.227, 0.016),
  'lamp': ('лампа с белым абажуром', 0.252, 0.47, 0.038),
  'decanter': ('хрустальный графин на столе', 0.318, 0.52, 0.02),
  'ship': ('модель парусника', 0.537, 0.035, 0.028),
  'roses': ('картина с букетом роз', 0.698, 0.26, 0.035),
  'oval': ('овальная картина с деревом', 0.80, 0.257, 0.028),
  'sphere': ('латунная сфера на комоде', 0.89, 0.28, 0.028),
  'clock': ('часы с маятником', 0.98, 0.11, 0.02),
  'globe': ('большой глобус', 0.603, 0.347, 0.045),
  'crystal': ('хрустальный шар', 0.71, 0.38, 0.014),
  'candles': ('пара подсвечников', 0.745, 0.35, 0.022),
  'owl': ('бронзовая сова', 0.845, 0.33, 0.018),
  'teapot': ('серебряный чайничек', 0.058, 0.605, 0.02),
  'watch': ('карманные часы на цепочке', 0.253, 0.613, 0.016),
  'bell': ('латунный колокольчик', 0.328, 0.593, 0.018),
  'binoculars': ('бинокль на столе', 0.383, 0.563, 0.024),
  'box': ('деревянная шкатулка', 0.208, 0.553, 0.016),
  'chest': ('кованый сундучок у окна', 0.059, 0.53, 0.028),
  'greenbox': ('зелёная шкатулка с золотом', 0.593, 0.55, 0.024),
  'inkwell': ('чернильница с пером', 0.633, 0.59, 0.022),
  'stamp': ('печать для сургуча', 0.675, 0.613, 0.014),
  'bluebox': ('голубая шкатулка', 0.725, 0.65, 0.022),
  'compass': ('компас с открытой крышкой', 0.80, 0.61, 0.024),
  'turtle': ('бронзовая черепаха', 0.65, 0.687, 0.02),
  'keys': ('связка старинных ключей', 0.755, 0.70, 0.02),
  'knife': ('нож для писем', 0.578, 0.66, 0.018),
  'sleepcat': ('спящая полосатая кошка', 0.905, 0.537, 0.028),
 },
 'room-3': {   # чердак
  'cage': ('клетка с птичкой', 0.043, 0.127, 0.033),
  'lavender': ('пучок лаванды на балке', 0.145, 0.167, 0.024),
  'globe': ('маленький глобус', 0.303, 0.10, 0.017),
  'angel': ('фигурка ангелочка', 0.32, 0.207, 0.02),
  'sphere': ('латунная сфера с кольцами', 0.28, 0.31, 0.024),
  'hourglass': ('песочные часы', 0.333, 0.32, 0.017),
  'hydrangea': ('ваза с белыми цветами', 0.437, 0.26, 0.026),
  'candle': ('свеча в подсвечнике', 0.125, 0.40, 0.018),
  'frame': ('тёмная картинка в рамке на полке', 0.178, 0.347, 0.024),
  'cup': ('чашка с блюдцем', 0.18, 0.43, 0.02),
  'casket': ('маленькая шкатулка', 0.09, 0.463, 0.018),
  'loupe': ('лупа', 0.151, 0.473, 0.016),
  'spyglass': ('подзорная труба на сундуке', 0.25, 0.39, 0.024),
  'ship': ('модель парусника', 0.533, 0.26, 0.03),
  'lamp': ('керосиновая лампа', 0.60, 0.273, 0.02),
  'mannequin': ('манекен с кружевной шалью', 0.688, 0.28, 0.038),
  'hat': ('соломенная шляпа с бантом', 0.75, 0.163, 0.028),
  'umbrella': ('зонт-трость', 0.808, 0.33, 0.018),
  'painting': ('картина с пейзажем', 0.868, 0.293, 0.032),
  'mirror': ('зеркало в золотой раме', 0.94, 0.20, 0.035),
  'perfume': ('сиреневый флакон духов', 0.858, 0.383, 0.014),
  'jewelbox': ('шкатулка на комоде', 0.923, 0.38, 0.018),
  'ballerina': ('фигурка балерины', 0.968, 0.36, 0.018),
  'basket': ('плетёная корзина', 0.755, 0.44, 0.032),
  'hatbox': ('полосатая шляпная коробка', 0.623, 0.467, 0.028),
  'horse': ('лошадка-качалка', 0.508, 0.43, 0.055),
  'top': ('юла', 0.423, 0.597, 0.018),
  'pillow': ('подушка с цветами', 0.055, 0.613, 0.032),
  'bear': ('плюшевый медвежонок', 0.173, 0.79, 0.038),
  'letters': ('письма с сургучной печатью', 0.275, 0.693, 0.024),
  'musicbox': ('музыкальная шкатулка', 0.38, 0.687, 0.024),
  'roses': ('засушенные розы', 0.325, 0.747, 0.02),
  'key': ('старинный ключ на полу', 0.435, 0.907, 0.02),
  'books': ('стопка книг с бечёвкой', 0.088, 0.873, 0.035),
  'floralbox': ('круглая коробка в цветочек', 0.775, 0.56, 0.024),
  'fan': ('кружевной веер', 0.76, 0.643, 0.022),
  'gloves': ('белые перчатки', 0.725, 0.747, 0.024),
  'bottle': ('зелёная бутылочка', 0.778, 0.693, 0.016),
  'photos': ('старые фотографии', 0.84, 0.687, 0.024),
  'feather': ('белое перо', 0.915, 0.677, 0.024),
  'pearls': ('нитка жемчуга', 0.885, 0.767, 0.016),
  'bell': ('колокольчик на полу', 0.623, 0.81, 0.018),
  'binoculars': ('бинокль на книге', 0.683, 0.847, 0.026),
  'compass': ('компас на полу', 0.818, 0.897, 0.02),
  'tin': ('жестяная коробка с розами', 0.955, 0.833, 0.028),
 },
}

LIGHT = {1: 0.14, 2: 0.11, 3: 0.08}
# (уровень, комната, искать, обманки, {id: улика})
TASKS = [
 (1, 'room-1', ['kettle', 'ship', 'flowerbox'], ['coffeepot', 'hatbox'], {'flowerbox': 'clue-07'}),
 (1, 'room-2', ['globe', 'owl', 'inkwell'], ['sphere', 'turtle'], {'inkwell': 'clue-06'}),
 (1, 'room-3', ['bear', 'horse', 'hat'], ['top', 'basket'], {}),
 (1, 'room-1', ['cage', 'chest', 'umbrella'], ['lamp', 'stand'], {'chest': 'clue-06'}),
 (1, 'room-2', ['cat', 'lamp', 'box'], ['sleepcat', 'greenbox', 'telescope'], {'box': 'clue-07'}),
 (2, 'room-2', ['oval', 'clock', 'ship', 'butterfly', 'keys'], ['roses', 'compass', 'coral'], {'oval': 'clue-13', 'clock': 'clue-14'}),
 (2, 'room-3', ['mannequin', 'mirror', 'spyglass', 'books', 'cage'], ['letters', 'binoculars', 'painting'], {'books': 'clue-15'}),
 (2, 'room-1', ['hourglass', 'lavender', 'decanter', 'sack', 'horse'], ['sphere', 'cinnamon', 'lantern'], {'hourglass': 'clue-14'}),
 (2, 'room-2', ['telescope', 'shell', 'chest', 'teapot', 'compass'], ['binoculars', 'coral', 'bluebox'], {}),
 (2, 'room-3', ['ballerina', 'umbrella', 'top', 'musicbox', 'frame'], ['angel', 'jewelbox', 'painting'], {'frame': 'clue-13'}),
 (3, 'room-3', ['key', 'compass', 'feather', 'gloves', 'angel', 'loupe', 'photos'], ['bell', 'pearls', 'casket', 'bottle'], {'photos': 'clue-21'}),
 (3, 'room-1', ['bell', 'perfume', 'binoculars', 'cinnamon', 'scrolls', 'brushes', 'casket'], ['goblet', 'decanter', 'sugar', 'pasta'], {'casket': 'clue-22'}),
 (3, 'room-2', ['stamp', 'watch', 'urn', 'bottles', 'candles', 'knife', 'sleepcat'], ['crystal', 'bell', 'keys', 'owl'], {'watch': 'clue-20'}),
 (3, 'room-3', ['globe', 'hourglass', 'candle', 'roses', 'bottle', 'bell', 'tin'], ['sphere', 'cup', 'casket'], {}),
 (3, 'room-1', ['goblet', 'jug', 'oranges', 'nuts', 'sugar', 'towel', 'vase'], ['pitcher', 'beans', 'bowl'], {}),
]
NFIND = {1: 3, 2: 5, 3: 7}

UI = {
 'km.findTitle': 'Найдите:',
 'km.hintBtn': 'Подсказка',
 'km.noPower': 'Не хватает силы',
 'km.wrong': 'Это не то, что ищем',
 'km.found': 'Найдено: {item}',
 'km.progress': 'Найдено {k} из {n}',
 'km.solved': 'Всё найдено! Свет вернулся в комнату.',
}

def rkey(room):
    return 'r' + room.split('-')[1]

def overlap(a, b):
    # расстояние в долях ширины (картинка 4:3)
    dx = a[1] - b[1]; dy = (a[2] - b[2]) * 0.75
    return math.hypot(dx, dy) < a[3] + b[3]

def build():
    errs = []
    tasks, texts, cnt = [], dict(UI), {1: 0, 2: 0, 3: 0}
    for lvl, room, find, decoys, clues in TASKS:
        cnt[lvl] += 1
        tid = 'komnata-%d-%03d' % (lvl, cnt[lvl])
        cat = CATALOG[room]
        ids = find + decoys
        if len(find) != NFIND[lvl]: errs.append(tid + ': find')
        if not 2 <= len(decoys) <= 4: errs.append(tid + ': decoys')
        if len(set(ids)) != len(ids): errs.append(tid + ': dup')
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if overlap(cat[a], cat[b]): errs.append('%s: overlap %s/%s' % (tid, a, b))
        objs = []
        for oid in ids:
            lab, x, y, r = cat[oid]
            key = 'km.%s.%s' % (rkey(room), oid)
            texts[key] = lab
            objs.append({'id': oid, 'labelKey': key, 'x': x, 'y': y, 'r': r, 'clue': clues.get(oid)})
        tasks.append({'id': tid, 'level': lvl, 'payload': {
            'room': room, 'light': LIGHT[lvl], 'objects': objs, 'find': find, 'timeLimitSec': None}})
    # одинаковые названия в одной комнате запрещены
    for room, cat in CATALOG.items():
        labs = [v[0] for v in cat.values()]
        if len(set(labs)) != len(labs): errs.append(room + ': повтор названий')
    return tasks, texts, errs

def dump_tasks(tasks):
    # компактно: один предмет — одна строка
    out = ['{ "schema": 1, "type": "komnata", "tasks": [']
    for i, t in enumerate(tasks):
        p = t['payload']
        objs = ',\n'.join('    ' + json.dumps(o, ensure_ascii=False) for o in p['objects'])
        out.append('  { "id": %s, "level": %d, "payload": { "room": %s, "light": %s, "objects": [\n%s\n   ],\n   "find": %s, "timeLimitSec": null } }%s' % (
            json.dumps(t['id']), t['level'], json.dumps(p['room']), json.dumps(p['light']), objs,
            json.dumps(p['find'], ensure_ascii=False), ',' if i < len(tasks) - 1 else ''))
    out.append('] }')
    return '\n'.join(out) + '\n'

if __name__ == '__main__':
    tasks, texts, errs = build()
    if errs:
        print('\n'.join(errs)); sys.exit(1)
    with open(os.path.join(ROOT, 'data', 'trials', 'komnata.json'), 'w', encoding='utf-8') as f:
        f.write(dump_tasks(tasks))
    with open(os.path.join(ROOT, 'tests', 'trials', 'fixtures', 'texts-komnata.json'), 'w', encoding='utf-8') as f:
        json.dump(texts, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    print('ok: %d заданий, %d текстов' % (len(tasks), len(texts)))
