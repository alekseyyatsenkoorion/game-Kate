# Контракты модулей — «Шестое чувство»

Версия **2.6** от 24.11.2026. Меняет только оркестратор. Агент, которому нужен другой интерфейс, пишет запрос оркестратору.
Нотация — сигнатуры в стиле TypeScript, без реализации. Код — ES-модули (`export`), классы.
Для каждого модуля указаны: имя, входы, выходы, что происходит при ошибке.

---

## 0. Общие правила

| Правило | Значение |
|---|---|
| Координаты | Логическая сцена 1024×768, начало — левый верхний угол. Input переводит касания в эти координаты (сцена вписывается в экран с полями). В данных координаты задаются долями поля испытания: x, y, r в диапазоне 0..1 |
| Время | Длительности — миллисекунды по `performance.now()`. Шаг кадра `dtMs` ограничен 100 мс. Календарь — `DateKey` = `'YYYY-MM-DD'` по локальной дате устройства, читает только DayLock |
| Идентификаторы | Латиница, нижний регистр, цифры и дефис: `[a-z0-9-]+`. Задание — `<type>-<уровень>-<nnn>` (`shirma-1-001`). Ключ текста — точки: `host.ep1.intro`. Ассет — имя файла без расширения: `bg-title` |
| Хранилище | localStorage читает и пишет **только Progress**. Cache Storage — **только Updater и sw.js**. Проверяется тестом 1.9 |
| Сеть | fetch разрешён **только ContentLoader, AssetLoader, Updater и sw.js**, только к своему адресу (same-origin). Внешних адресов нет |
| Ни один модуль не роняет игру | Ошибку модуль обрабатывает сам и возвращает безопасное значение, либо передаёт `GameError` вызывающему по правилу своего раздела. Что не поймали — ловит SceneManager и ведёт на сцену `error`. Белый экран — ошибка уровня «задача не принята» |
| Лог | `log.warn / log.error` из `src/core/log.js`. Каждое предупреждение пишется один раз на ключ, без спама. В режиме теста лог виден в debug |
| Изменение контрактов | Новая версия + запись в журнале (§14) + уведомление всех зон |

```ts
type Level = 1 | 2 | 3;
type DateKey = string;
interface GameError { code: ErrorCode; module: string; message: string; details?: object }   // ErrorCode — §13.6
```

---

## 1. Scene — экран игры

### 1.1 Интерфейс
```ts
abstract class Scene {
  static readonly id: SceneId;
  constructor(app: AppContext);                         // создание: без DOM и без загрузок
  enter(root: HTMLElement, params: SceneParams): Promise<void>;   // вход: строит DOM и подписки
  update(dtMs: number): void;                           // обновление: каждый кадр, пока сцена активна
  render(): void;                                       // отрисовка: каждый кадр после update (DOM-сцены могут ничего не делать)
  onInput(e: InputEvent): void;                         // касание: от Input (§3)
  pause(): void;                                        // приложение ушло в фон
  resume(): void;
  exit(): Promise<void>;                                // выход: снять подписки, таймеры, звуки
  onReturn?(fromId: SceneId, result: SceneResult): void; // вернулись из дочерней сцены
}

type SceneParams = Record<string, string | number | boolean | null>;   // только сериализуемое
type SceneResult = Record<string, string | number | boolean | null>;

interface AppContext {
  scenes: SceneManager; input: Input; progress: Progress; dayLock: DayLock;
  assets: AssetLoader; content: ContentLoader; audio: Audio; scoring: Scoring;
  updater: Updater; debug: boolean;
}
```

### 1.2 Жизненный цикл
`constructor` → `enter` → (`update` → `render`) каждый кадр, `onInput` по событию, `pause`/`resume` при сворачивании → `exit`.
Сцена рисует только в своём `root`. После `exit` у неё не остаётся слушателей, таймеров, звуков и ссылок из глобальных объектов (тест 1.3).

### 1.3 Ошибки
- Исключение в `enter` → SceneManager пишет в лог и делает `replace('error', { code, from })`.
- Исключение в `update`, `render` или `onInput` → то же. Цикл кадров не останавливается.
- Исключение в `exit` → в лог, переход продолжается.

### 1.4 Сцены — закрытый список (9)
| id | Зона | Параметры запуска | Результат / куда уходит |
|---|---|---|---|
| `title` | D | — | `go('season')` или `go('settings')` |
| `season` | D | — | `go('intro', { n })`, `go('diary')`, `back()` → title |
| `intro` | D | `n: number` — номер выпуска; `replay: boolean` | `go('trial', { n, idx: 0 })`. Создаёт RunState, если его нет |
| `trial` | A (trial-host) | `n: number`, `idx: number` — номер испытания в выпуске | следующее испытание: `replace('trial', { n, idx: idx+1 })`; последнее — `replace('result', { n })`; ошибка задания — §11.4 |
| `result` | D | `n: number` | `go('season')`. Если Катя последняя в выпуск выбывания — кнопка «Переиграть» → `replace('intro', { n, replay: true })` |
| `diary` | D | — | `finish({ changed: boolean })` → season.onReturn |
| `settings` | D | — | `back()` |
| `debug` | A | — | `finish({ reload: boolean })`; доступна только при `progress.settings().test` |
| `error` | A | `code: string`, `from: string` | `replace('season')` |

Наложения (не сцены): «Поверните iPad», баннер обновления (Updater), модальное подтверждение — `src/core/overlay.js`.

---

## 2. SceneManager — переключение, параметры, результат
```ts
interface SceneManager {
  register(cls: typeof Scene): void;                    // регистрация — из файла регистрации своей зоны
  go(id: SceneId, params?: SceneParams): Promise<void>; // кладёт текущую в стек
  replace(id: SceneId, params?: SceneParams): Promise<void>;   // без стека
  back(): Promise<void>;                                // предыдущая; стек пуст → title
  finish(result: SceneResult): Promise<void>;           // как back, но предыдущая получает onReturn(id, result)
  current(): { id: SceneId; params: SceneParams };
  onChange(fn: (id: SceneId) => void): () => void;      // возвращает отписку
}
```
- **Переход:** `exit` текущей → очистка root → затемнение 300 мс → новая сцена: `constructor` и `enter`. Стек не глубже 10.
- **Параметры** — только через `params`. Тяжёлые данные сцена берёт сама из Progress или ContentLoader по id.
- **Ошибки:**

| Ситуация | Код | Что происходит |
|---|---|---|
| `register` с занятым id или id не из §1.4 | `SCENE_REGISTER` | бросает при старте — ошибка разработки, ловит тест 1.1 |
| `go` к незарегистрированной сцене | `SCENE_UNKNOWN` | лог, остаёмся на текущей |
| `go` во время перехода | — | очередь, выполняется последний запрос |
| исключение сцены | `SCENE_CRASH` | лог + `replace('error')` |

---

## 3. Input — касания
```ts
interface Input {
  onEvent(fn: (e: InputEvent) => void): () => void;     // SceneManager подписывает активную сцену
  toStage(clientX: number, clientY: number): { x: number; y: number };
  setEnabled(on: boolean): void;                        // во время перехода сцен — выключен
}
type InputAction = 'tap' | 'drag-start' | 'drag' | 'drag-end' | 'hold';   // закрытый список
interface InputEvent { action: InputAction; x: number; y: number; target: Element | null; t: number }
```
- Pointer Events, работает **только первый палец**, остальные игнорируются.
- `tap` — отпускание быстрее 300 мс и сдвиг меньше 10 px. `hold` — удержание 500 мс без сдвига. Иначе drag.
- Двойной тык и масштабирование страницы выключены. Контекстное меню и выделение текста подавлены.
- **Ошибки:** нет. Событие вне сцены (поля) приходит с координатами за пределами 0..1024 / 0..768, сцена его игнорирует.

---

## 4. Progress — прогресс и сохранение

### 4.1 Ключи localStorage (закрытый список)
| Ключ | Содержимое |
|---|---|
| `s6:v2:progress` | `ProgressData` |
| `s6:v2:settings` | `Settings` |
| `s6:v2:draws` | `DrawState` — история выборки заданий |
| `s6:v2:run` | `RunState` — выпуск в процессе |
| `s6:v2:progress.corrupt` | копия испорченных данных (создаётся только при сбое) |

### 4.2 Формат сохранения
```ts
interface ProgressData {
  schema: 2;
  episodes: Record<number, { firstDate: DateKey; stars: 0|1|2|3; points: number; bestPoints: number; attempts: number }>;
  power: number;
  totalPoints: number;
  rivals: Record<RivalId, { points: number; eliminatedAfter: number | null }>;
  guest: { enabled: boolean; points: number };          // режим «Гость», этап 4
  case: { clues: string[]; links: Array<[string, string]> };
  skeptic: { pendingTraps: number };                    // ложных подсказок к следующему выпуску (0 или 1)
  achievements: string[];
  openedOn: Record<number, DateKey>;                    // когда выпуск стал доступен (для DayLock)
}
interface Settings { music: boolean; sfx: boolean; voice: boolean; test: boolean; musicVolume?: number }   // 2.5: громкость музыки 0..1, по умолчанию 1
interface DrawState { [poolKey: string]: { bag: string[]; recent: string[] } }   // poolKey = 'shirma:1'
interface RunState { n: number; attempt: number; seed: number; idx: number; taskIds: string[]; results: TrialResult[] }
```

### 4.3 Интерфейс
```ts
interface Progress {
  get(): Readonly<ProgressData>;
  update(mutator: (draft: ProgressData) => void): void;   // копия → изменение → проверка по схеме → запись
  settings(): Readonly<Settings>;
  setSettings(patch: Partial<Settings>): void;
  run(): RunState | null; saveRun(r: RunState): void; clearRun(): void;
  draws(): DrawState; saveDraws(d: DrawState): void;
  recordEpisode(n: number, score: EpisodeScore, rivals: RivalsOutcome): void;
  reset(): void;                                        // настройки, в том числе test, сохраняются
  exportCode(): string; importCode(code: string): boolean;   // резервная копия текстом (debug)
  subscribe(fn: (p: Readonly<ProgressData>) => void): () => void;
  readonly persistent: boolean;                         // false — пишем только в память
  readonly recovered: boolean;                          // true — данные были испорчены
}
```
- Первое прохождение выпуска начисляет силу. Повторное улучшает `stars` и `bestPoints`, силу не даёт, `attempts` +1.
- Каждое завершённое испытание сразу дописывается в `RunState`. После перезапуска выпуск продолжается с `idx` (Т-21).

### 4.4 Ошибки
| Ситуация | Что происходит |
|---|---|
| JSON не читается | копия в `…progress.corrupt`, старт с нуля, `recovered = true`. Оболочка показывает сообщение. Ничего не удаляется молча |
| localStorage недоступен или переполнен | работа в памяти, `persistent = false`. Оболочка предупреждает: «прогресс не сохранится» |
| `schema` 1 (прототип) | миграция в 2 при загрузке |
| `schema` новее известной | только чтение + предупреждение |
| `update` не прошёл проверку | изменение отброшено, `PROGRESS_INVALID` в лог |
| `importCode` с битым кодом | `false`, текущий прогресс не тронут |

---

## 5. Audio — звуки, голос, глушение
```ts
interface Audio {
  unlock(): Promise<void>;                              // на первом касании (требование iOS); до этого всё — тихо
  music(id: MusicId | null, opts?: { fadeMs?: number }): void;   // одна фоновая дорожка по кругу; null — стоп
  sfx(id: SfxId, opts?: { volume?: number }): void;
  say(textKey: string): Promise<void>;                  // реплика в очередь voice
  stopAll(): void;
  setMuted(channel: AudioChannel, on: boolean): void;
  isMuted(channel: AudioChannel): boolean;
  pauseAll(): void; resumeAll(): void;
}
```
- **Источник звука:** в версии 1.0 музыка и звуки синтезируются Web Audio по описанию из `data/audio.json` (§12.7). Если для id указан файл (`file`), берётся файл (.m4a, AAC). Правило подмены — как у картинок: файл есть → он, нет → синтез.
- **Голос (2.1):** встроенный синтез речи iOS, русский, работает без сети. `sayText(text, {pitch, rate})` — одна реплика за раз, новая прерывает старую; `praise(text)` — голос ведущего со звоном; `laugh(jab)` — злорадный смех скептика и колкость (низкий голос), без голоса — синтезированный смех. Субтитры показывает вызывающий (для испытаний — trial-host через `ctx.react`).
- **Глушение:** каналы `music`, `sfx`, `voice` и `all`. Состояние берётся из `Progress.settings()`.
- **Ошибки:** нет файла, ошибка декодирования, звук не разблокирован → одно предупреждение в лог на id, дальше тишина. Audio никогда не бросает исключений и не задерживает игру. `say` всегда завершается.

---

## 6. AssetLoader — картинки
```ts
interface AssetLoader {
  init(): Promise<void>;                                // читает assets/gpt/index.json (если нет — пусто)
  image(id: string): Promise<ImageSource>;
  has(id: string): boolean;                             // есть ли картинка из ChatGPT
  preload(ids: string[]): Promise<void>;
}
type ImageSource =
  | { kind: 'bitmap'; img: HTMLImageElement; w: number; h: number }   // assets/gpt/<id>.webp
  | { kind: 'svg'; url: string; w: number; h: number }                // assets/art/<id>.svg
  | { kind: 'drawn'; draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void };   // рисует код
```
**Правило подмены (Т-17):** для id ищем по порядку:
1. `assets/gpt/<id>.webp`, если id есть в `assets/gpt/index.json` (файл кладёт ChatGPT, список собирает `tools/gpt-index`);
2. `assets/art/<id>.svg`;
3. функцию-рисовальщик из `src/core/art-fallback.js` по префиксу id (`bg-`, `char-`, `rival-`, `room-`, `foto-`).

Сцена не знает, какой вариант пришёл: она рисует `ImageSource` через общий помощник `drawImageSource` из `src/core/art.js`.

**Ошибки:** файл не загрузился → следующий вариант по порядку и одно предупреждение. Нет ни одного варианта → `{ kind: 'drawn' }`, то есть нейтральная заглушка (тёмная карта с вопросом). Исключений нет.

---

## 7. Scoring — очки, звёзды, соперники
Чистые функции без побочных эффектов. Все числа берутся из balance.json (§12.6), в коде их нет.
```ts
interface Scoring {
  trial(r: TrialResult, b: TrialBalance): TrialScore;
  episode(n: number, scores: TrialScore[]): EpisodeScore;
  rivals(n: number, player: EpisodeScore, state: ProgressData, rng: Rng, hintsUsed?: number, results?: TrialResult[]): RivalsOutcome;
  guestGain(n: number, results: TrialResult[]): number;   // 2.6: base уровня × guest.accuracy + balance.guest.winBonus за забранное испытание
  title(totalPoints: number): { id: string; label: string };
}
interface TrialScore { points: number; stars: 0|1|2|3; breakdown: { base: number; hints: number; mistakes: number; time: number } }
interface EpisodeScore { points: number; stars: 0|1|2|3; powerGain: number; newClues: string[] }
interface RivalsOutcome {
  table: Array<{ id: RivalId | 'player' | 'guest'; points: number; place: number }>;
  eliminated: RivalId | null;
  playerMustReplay: boolean;
  skepticTraps: 0 | 1;                                  // ловушки скептика на следующий выпуск
}
```
- **Очки испытания:** `points = max(0, round(base × accuracy) − hintCost × hintsUsed − mistakeCost × mistakes + (solved && timeMs < par ? timeBonus : 0))`. Если не решено, итог × `unsolvedFactor`.
- **Звёзды:** 3 — решено, без подсказок, `points ≥ stars3`; 2 — решено, `points ≥ stars2`; 1 — решено; 0 — не решено.
- **Выпуск:** очки складываются, звёзды — среднее с округлением вниз, `powerGain` — сумма звёзд всех испытаний.
- **Соперники:** очки бота = `base × clamp(N(skill, spread), 0, 1)` через `rng` с seed выпуска, поэтому воспроизводимо. Выбывание только после выпусков из `eliminateAfter`: уходит последний из оставшихся. Если последняя игрок — `playerMustReplay = true`, никто не выбывает.
- **Скептик:** `skepticTraps = hintsUsed выпуска ≥ 2 ? 1 : 0`.
- **Гость (2.6):** если `guest.enabled`, строка `guest` попадает в таблицу (места), но не выбывает и не влияет на выбывание и `playerMustReplay`. Ходы по очереди — только Ширма и Багажник (`ctx.turn`); Кате испытание засчитывается решённым, её accuracy — по её ошибкам; достижения за испытание, которое забрал гость, не выдаются.
- **Ошибки:** вход вне диапазонов (accuracy вне 0..1, неизвестный уровень, n вне 1..12) → бросает `SCORE_INPUT`. Это ошибка разработки, ловит тест 4.1.

---

## 8. DayLock — замок по дням (вместо таймера)
```ts
interface DayLock {
  today(): DateKey;
  availability(n: number): 'done' | 'open' | 'wait' | 'locked';
  quotaLeft(): number;                                  // сколько ещё можно открыть сегодня
  markStarted(n: number): void;                         // фиксирует openedOn[n], если его нет
}
```
- Выпуски строго по порядку: `locked` — предыдущий не пройден; `wait` — дневной лимит исчерпан; `open` — можно играть; `done` — пройден, можно переигрывать всегда.
- Лимит: `daily.weekday` в будни, `daily.saturday` в субботу (balance.json). Выпуск считается «открытым сегодня» по `openedOn`, поэтому уже открытый не закрывается, даже если перевести часы назад.
- В режиме теста лимита нет.
- **Ошибки:** дата устройства не читается → считаем, что сегодня новый день, предупреждение в лог. Игра не блокируется.

---

## 9. ContentLoader и Rng — данные
### 9.1 ContentLoader
```ts
interface ContentLoader {
  init(): Promise<void>;                                // season, balance, texts, characters, case, audio; проверка схем
  episode(n: number): Episode;                          // §12.1
  balance(): Balance;                                   // §12.6
  trialBalance(type: TrialType, level: Level): TrialBalance;
  character(id: CharacterId): Character;                // §12.3
  clue(id: string): Clue;                               // §12.4
  pool(type: TrialType, level: Level): Promise<Task[]>; // только валидные
  draw(type: TrialType, level: Level, rng: Rng): Promise<Task>;
  text(key: string, vars?: Record<string, string | number>): string;
  pickText(prefix: string, rng: Rng): string;           // случайная реплика из группы без повтора подряд (похвалы, колкости)
}
```
**Ошибки:**
| Ситуация | Код | Что происходит |
|---|---|---|
| файл не найден или нет сети без кэша | `CONTENT_MISSING` | в `init` — сцена error «не удалось загрузить игру»; в `pool` — выпуск помечается «в разработке» |
| битый JSON | `CONTENT_PARSE` | так же |
| не совпадает со схемой | `CONTENT_INVALID` | в `init` — сцена error; в `pool` битое задание пропускается, лог с путём к полю |
| пул пуст | `CONTENT_EMPTY` | выпуск «в разработке» |
| нет ключа текста | — | возвращает `[key]` + предупреждение; тест 2.4 ловит такие ключи заранее |

### 9.2 Случайность с сохранением выборки
```ts
interface Rng { next(): number; int(min: number, max: number): number; pick<T>(a: T[]): T; shuffle<T>(a: T[]): T[] }
function createRng(seed: number): Rng;                  // src/core/rng.js, детерминированный (mulberry32)
```
- seed выпуска = хеш(n, attempt), хранится в RunState. После перезапуска задания те же, при переигровке — другие.
- `draw` — «мешок»: пул перемешивается, задания берутся по очереди. Когда мешок пуст, он перемешивается заново, а последние `noRepeatLast` (3) выпавших ставятся в его конец (при пуле 5 первые 2 позиции — всегда «новые»). Состояние — `Progress.draws()`.
- `Math.random` в коде запрещён везде, кроме `createRng` для начального seed (тест 1.8).

---

## 10. Updater — обновление
```ts
interface Updater {
  register(): Promise<void>;                            // регистрирует sw.js
  readonly version: string;                             // из sw.js, видна в settings и debug
  onReady(fn: (newVersion: string) => void): () => void; // новая версия скачана
  applyNow(): Promise<void>;                            // только если текущая сцена title или season
}
```
- `sw.js` кэширует всё из списка `precache.json`. Список генерирует `tools/build-precache` при выкладке, руками его не правят. Кэш называется `s6-<version>`.
- При запуске с сетью проверяется новая версия. Она скачивается в фоне, затем `onReady` → баннер «Доступна новая версия — Обновить» на title или season.
- `applyNow` на другой сцене откладывается до ближайшего перехода на title или season. Идущий выпуск не прерывается: RunState сохранён, после обновления выпуск продолжается.
- Старые кэши удаляются после активации новой версии.
- **Ошибки:** service worker не поддерживается или не зарегистрировался → игра работает онлайн, предупреждение в лог и в debug. Ошибка загрузки новой версии → остаёмся на старой, попытка при следующем запуске. Исключений нет.

---

## 11. Trial — единый контракт испытания
### 11.1 Модуль
```ts
interface TrialModule {
  readonly type: TrialType;
  readonly schemaVersion: 1;
  create(ctx: TrialContext): TrialInstance;
}
interface TrialInstance {                               // повторяет жизненный цикл сцены
  start(field: HTMLElement, task: Task, level: Level): Promise<void>;   // field — поле 960×600 внутри рамки
  update(dtMs: number): void;
  render(): void;
  onInput(e: InputEvent): void;                         // координаты уже переведены в поле
  pause(): void; resume(): void;
  destroy(): void;                                      // trial-host вызывает всегда
}
interface TrialContext {
  rng: Rng; audio: Audio; assets: AssetLoader;
  text(key: string, vars?: object): string;
  balance: TrialBalance;
  traps: 0 | 1;                                         // ловушки скептика (2.4): Ширма добавляет 1 ложную подсказку (признак обманки, item.<id>.trait), Багажник — 1 ложную улику обманке; остальные испытания не используют
  power: { get(): number; spend(n: number, reason: string): boolean };   // false — не хватает, ничего не списано
  hint(kind: string): void;
  react(kind: 'correct' | 'mistake'): void;           // 2.1: реакция шоу — похвала голосом или злорадный смех скептика + субтитр
  item(id: string): { id: string; labelKey: string; art: string };   // 2.1: предмет из items.json
  turn?: { who: 'player' | 'guest'; next(): void };     // режим «Гость», этап 4: ходы по очереди
  finish(result: TrialResult): void;                    // ровно один раз
  fail(err: GameError): void;
}
interface TrialResult {
  type: TrialType; taskId: string; level: Level;
  solved: boolean;
  accuracy: number;                                     // 0..1 — доля верного по логике испытания
  hintsUsed: number; powerSpent: number; mistakes: number;
  timeMs: number;                                       // активное время, без пауз
  caseClues: string[];                                  // найденные улики сквозного дела
  guest?: { solved: boolean; accuracy: number; winner: 'player' | 'guest' };   // режим вдвоём (2.6)
}
```
### 11.2 Вход и выход
Вход: `Task` (§12.2) от ContentLoader.draw и уровень. Выход: `TrialResult` через `ctx.finish`. Очки из результата считает Scoring (§7), одинаково для всех испытаний.

### 11.3 Правила
- Рисует только в `field`. Не трогает Progress, хранилище, сеть и чужой DOM.
- Случайность только через `ctx.rng`.
- Не содержит текстов и чисел: тексты — через `ctx.text`, числа — из `ctx.balance` и задания.
- Держит ≥ 30 кадров/с (тест 9.2).
- После `destroy` нет слушателей, таймеров, rAF (цикл анимации) и звуков (тест 1.4).

### 11.4 Ошибки
- Задание не по схеме или нет ассета → `ctx.fail({ code: 'TASK_INVALID' })`. trial-host помечает задание битым на эту сессию и берёт следующее из мешка. Три битых подряд → сцена error.
- Исключение внутри испытания → trial-host вызывает `destroy` и действует как при `TASK_INVALID`.
- Повторный `finish` → игнорируется, предупреждение.

### 11.5 Реестр
`src/trials/index.js` (зона B): `export const TRIALS: Record<TrialType, TrialModule>`. Новое испытание = модуль + строка в реестре + схема + файл данных + тип в §13.2 (через оркестратора). Движок не меняется. Тип из season.json без модуля в реестре → `TRIAL_UNKNOWN`, выпуск помечается «в разработке».

---

## 12. Данные контента
Шов между контентом (зона C) и кодом (A, B, D). Формальные схемы — `schemas/*.schema.json`, их проверяет тест группы 2. Каждый файл начинается с `"schema": 1`.

### 12.1 Выпуск — `data/season.json`
```json
{ "schema": 1, "episodes": [
  { "n": 1, "title": "Отбор", "introKey": "host.ep1.intro", "outroKey": "host.ep1.outro",
    "trials": [ { "type": "shirma", "level": 1 } ],
    "clues": ["clue-01"] } ] }
```
Ровно 12 выпусков, 1–3 испытания в каждом, всего 15. Каждое сочетание тип×уровень ровно один раз. Улик всего 22.

### 12.2 Задание — `data/trials/<type>.json`
Конверт: `{ "schema": 1, "type": "<type>", "tasks": [ { "id": "<type>-<ур>-<nnn>", "level": 1, "payload": { … } } ] }`. На каждый уровень не меньше 5 заданий.

| type | payload | Ограничения |
|---|---|---|
| shirma | `{ "answer": "kettle", "options": ["kettle","clock","teapot","lamp"], "hints": [ { "kind": "silhouette\|sound\|warmth\|detail\|smell", "textKey": "…", "fake": false } ] }` | варианты — id предметов (§12.5); 4/5/6 по уровню; 3–5 подсказок; `answer` среди `options`; `fake` только на уровне 3 |
| bagazhnik | `{ "cars": [ { "id": "c1", "body": "sedan\|hatch\|suv\|van", "color": "#5b3a8c", "clues": [ { "kind": "sag\|fog\|track\|sound\|smell", "textKey": "…", "fake": false } ] } ], "target": "c1" }` | машин 6/10/15; у цели ≥ 2 настоящих улик; ложных 0/1/2 |
| misterx | `{ "categories": [ { "key": "job", "labelKey": "…", "values": [ { "id": "pilot", "labelKey": "…" } ] } ], "people": [ { "id": "x", "labelKey": "…" }, { "id": "a", "labelKey": "…" } ], "clues": [ { "textKey": "…", "rule": ["is","a","job","pilot"] } ], "solution": { "x": { "job": "pilot" } }, "ask": "x" }` | людей = значений в категории (каждое значение ровно у одного человека); 3×3 / 4×4 / 4×5 (категорий × значений); решение единственное (тест-решатель 2.6); `rule` — машинная форма подсказки для решателя, испытание её не читает: `["is",p,cat,val]`, `["not",p,cat,val]`, `["link",cat1,val1,cat2,val2]` (у кого val1, у того и val2), `["unlink",cat1,val1,cat2,val2]` |
| foto | `{ "photo": "foto-1-01", "items": [ { "labelKey": "…", "art": "item-key" } ], "statements": [ { "textKey": "…", "true": true, "explainKey": "…" } ], "pick": 2 }` | `photo` — id картинки (foto-<ур>-<nn>); `items` — вещи человека: подпись обязательна, `art` (id из items.json) — по желанию; утверждений 5/6/8, верных ровно `pick` = 2/3/4; утверждения проверяемы по фото и вещам |
| komnata | `{ "room": "room-1", "light": 0.14, "objects": [ { "id": "jar", "labelKey": "…", "x": 0.31, "y": 0.62, "r": 0.03, "clue": null } ], "find": ["jar"], "timeLimitSec": null }` | `objects` — предметы, реально видимые на картинке комнаты (координаты центра и радиус — доли ширины/высоты картинки); найти 3/5/7; луч 0.14/0.11/0.08; все `find` есть в `objects`; предметы не перекрываются; `clue` — id улики дела или null; `timeLimitSec` = null |

### 12.3 Персонаж — `data/characters.json`
`{ "id": "agata", "name": "Агата", "role": "rival|host|skeptic", "color": "#8c2f5b", "portrait": "rival-agata", "skill": 0.75, "spread": 0.15, "lines": "rival.agata" }` — 7 записей (§13.3). `skill` и `spread` только у соперников.

### 12.4 Улика сквозного дела — `data/case.json`
`{ "schema": 1, "titleKey": "case.title", "clues": [ { "id": "clue-01", "episode": 1, "textKey": "…", "item": "letter" } ], "links": [ ["clue-01","clue-07"] ], "solutionKey": "case.solution" }` — ровно 22 улики, у каждой ровно один выпуск. Правильных связей 8–12.

### 12.5 Предмет — `data/items.json`
`{ "id": "kettle", "labelKey": "item.kettle", "art": "item-kettle" }` — не меньше 40 предметов к версии 1.0 (в демо 14). `art` → `assets/art/<art>.svg`.

### 12.6 Баланс — `data/balance.json`
```json
{ "schema": 1, "startPower": 3, "daily": { "weekday": 1, "saturday": 2 },
  "noRepeatLast": 3, "eliminateAfter": [3, 6, 9, 11], "lowFx": false,
  "hintPrice": 1,
  "trials": { "shirma": { "1": { "base": 100, "hintCost": 15, "mistakeCost": 20, "par": 90000, "timeBonus": 20, "unsolvedFactor": 0.3, "stars2": 50, "stars3": 80 } } },
  "titles": [ { "id": "t1", "labelKey": "title.t1", "from": 0 } ] }
```
`trials` заполнен для всех 15 сочетаний.

### 12.7 Тексты и звуки
- `data/texts.json`: `{ "schema": 1, "texts": { "host.ep1.intro": "…" } }`. Подстановки `{name}`. Группы для `pickText`: `host.praise.1…12`, `skeptic.jab.1…12`.
- `data/audio.json`: `{ "schema": 1, "sounds": { "sfx-cloth": { "synth": "noise", "ms": 400, "file": null } } }`. Если `file` не null, звук берётся из файла.

---

## 13. Закрытые списки (расширяет только оркестратор)
1. **Сцены (9):** `title, season, intro, trial, result, diary, settings, debug, error`.
2. **Типы испытаний (5):** `shirma, bagazhnik, misterx, foto, komnata`.
3. **Персонажи (7):** `host, skeptic, agata, elisey, baron, miroslava, timur`. Соперники (`RivalId`) — последние 5.
4. **Действия ввода (5):** `tap, drag-start, drag, drag-end, hold`.
5. **Каналы звука (4):** `music, sfx, voice, all`.
6. **Коды ошибок (11):**

| Код | Модуль |
|---|---|
| SCENE_REGISTER, SCENE_UNKNOWN, SCENE_CRASH | SceneManager |
| TRIAL_UNKNOWN, TASK_INVALID | trial-host / Trial |
| PROGRESS_INVALID | Progress |
| SCORE_INPUT | Scoring |
| CONTENT_MISSING, CONTENT_PARSE, CONTENT_INVALID, CONTENT_EMPTY | ContentLoader |

7. **Ключи хранилища (5):** §4.1.
8. **Префиксы ассетов (6):** `bg-, char-, rival-, room-, foto-, item-`.

---

## 14. Журнал изменений
- 1.0 — 24.11.2026 — первая версия.
- 2.6 — 24.11.2026 — режим «Играем вдвоём»: ctx.turn, TrialResult.guest.winner, Scoring.guestGain, balance.guest.winBonus.
- 2.5 — 24.11.2026 — достижения: data/achievements.json (id, titleKey, descKey, icon, rule; виды правил episodes, starEpisodes, cleanRun, trial, survived, title, season, caseSolved), ContentLoader.achievements(); Settings.musicVolume, Audio.setMusicVolume(v).
- 2.4 — 24.11.2026 — ловушки скептика добавляет само испытание (сверх данных уровня: ложных может стать на 1 больше, чем в §12.2); признаки предметов item.<id>.trait / traitKind в texts.json.
- 2.3 — 24.11.2026 — Фото-дело: вещи с подписью (labelKey) вместо id предмета; Тёмная комната: предметы картинки с id и labelKey.
- 2.2 — 24.11.2026 — формат Мистера Икс: значения и люди с labelKey, поле rule для решателя.
- 2.1 — 24.11.2026 — базовая озвучка: `ctx.react`, `ctx.item`, голос в Audio (`sayText`, `praise`, `laugh`).
- 2.0 — 24.11.2026 — по полному ТЗ: жизненный цикл сцены (update/render/onInput), результат сцены (`finish`/`onReturn`), Input, AssetLoader с правилом подмены, DayLock вместо таймера, Updater, раздел «Данные контента», закрытые списки, режим «Гость» в контрактах, ключи хранилища `s6:v2:`.
