# Статус проекта — 24.11.2026

**Готово:** демо (интерфейс, выпуск 1 «Ширма», выпуск 2 «Багажник», озвучка, работа без сети). Код — в этой папке и на GitHub: alekseyyatsenkoorion/game-Kate (ветка main).

## Ждёт Alex
1. Включить GitHub Pages: репозиторий → Settings → Pages → Branch: main, / (root) → Save. Адрес игры: https://alekseyyatsenkoorion.github.io/game-Kate/
2. Проверить демо на iPad (4 пункта в последнем отчёте: установка иконкой, выпуск 1 со смехом и похвалой, режим теста — 7 касаний по глазу → выпуск 2, авиарежим).
3. Картинки: вставить «Блок для ChatGPT» из prompt GPT.md, ChatGPT сохраняет 31 WebP в assets/gpt/. Затем сказать «картинки готовы».

## Следующие шаги оркестратора
- После «картинки готовы»: `node tools/gpt-index.js`, подключить фоны bg-* к сценам, портреты char-*/rival-* к вступлению и итогам, пересобрать precache, выложить.
- После реакции Кати: решение, продолжать ли этапы 1–3 (spec.md §8).
- Позже: переезд на VPS Alex с приватным репозиторием (домен с HTTPS + автообновление).

## Как проверить локально
`python3 -m http.server 8080` в этой папке → http://localhost:8080. Автотесты: `python3 tests/core/smoke.py`, `python3 tests/trials/run_trials.py` (нужен сервер на 8765), `python3 tests/content/art-check.py`.
