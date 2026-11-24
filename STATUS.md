# Статус проекта — 24.11.2026, версия 1.2.1

**Готово:** весь сезон (12 выпусков, 5 испытаний × 3 уровня, 75 заданий), картинки ChatGPT (31), генеративная музыка и озвучка, ловушки скептика, 12 достижений, громкость музыки, режим «Играем вдвоём», сквозное дело с разгадкой, работа без сети, обновление без потери прогресса.
Игра: https://alekseyyatsenkoorion.github.io/game-Kate/ · код: GitHub alekseyyatsenkoorion/game-Kate (main) и эта папка.

## Проверка
`npm test` — все 14 групп (≈ 11 мин, Chrome). `npm test -- --zone B`, `npm test -- --only rules`. `npm run check-zone -- <зона>`.
WebKit (движок Safari) в среде разработки недоступен — финальная проверка на iPad.

## Отложено (решение Alex)
- Личный слой и финальный сюрприз (spec.md §10).
- Переезд на VPS с приватным репозиторием.

## Картинки
Новые картинки ChatGPT: ZIP в assets/gpt/ → `python3 tools/import-gpt.py <zip>` → `node tools/gpt-index.js` → `node tools/build-precache.js`.
