// ContentLoader — загрузка данных из data/ (contracts.md §9).
import { log, gameError } from './log.js';

const BASE = 'data/';

async function getJson(path) {
  let res;
  try { res = await fetch(BASE + path, { cache: 'no-cache' }); }
  catch (e) { throw gameError('CONTENT_MISSING', 'ContentLoader', 'Нет файла ' + path); }
  if (!res.ok) throw gameError('CONTENT_MISSING', 'ContentLoader', 'Нет файла ' + path);
  const txt = await res.text();
  try { return JSON.parse(txt); } catch (e) { throw gameError('CONTENT_PARSE', 'ContentLoader', 'Битый JSON ' + path); }
}
function need(cond, path, field) { if (!cond) throw gameError('CONTENT_INVALID', 'ContentLoader', path + ': ' + field); }

// Минимальная проверка заданий по типу (полная — тесты зоны C по schemas/).
const TASK_CHECK = {
  shirma: (p) => Array.isArray(p.options) && p.options.indexOf(p.answer) >= 0 && Array.isArray(p.hints) && p.hints.length >= 3,
  bagazhnik: (p) => Array.isArray(p.cars) && p.cars.some((c) => c.id === p.target),
  misterx: (p) => !!p.solution && Array.isArray(p.categories),
  foto: (p) => Array.isArray(p.statements) && p.statements.filter((s) => s.true).length === p.pick,
  komnata: (p) => Array.isArray(p.objects) && (p.find || []).every((f) => p.objects.some((o) => o.id === f))
};

export class ContentLoader {
  constructor(progress) { this.progress = progress; this.pools = {}; this.lastPick = {}; }
  setProgress(p) { this.progress = p; }
  async init() {
    const [season, balance, texts, chars, cs, items] = await Promise.all([
      getJson('season.json'), getJson('balance.json'), getJson('texts.json'),
      getJson('characters.json'), getJson('case.json'), getJson('items.json')]);
    try { const a = await getJson('achievements.json'); this.achList = a.schema === 1 ? a.achievements : []; }
    catch (e) { log.warn('ACH_FILE', String(e.message)); this.achList = []; }
    need(season.schema === 1 && season.episodes && season.episodes.length === 12, 'season.json', 'episodes');
    need(balance.schema === 1 && balance.trials, 'balance.json', 'trials');
    need(texts.schema === 1 && texts.texts, 'texts.json', 'texts');
    this.seasonData = season; this.bal = balance; this.texts = texts.texts;
    this.chars = chars.characters; this.caseData = cs; this.itemList = items.items;
    this.itemMap = {}; this.itemList.forEach((i) => { this.itemMap[i.id] = i; });
  }
  achievements() { return this.achList || []; }
  episode(n) { return this.seasonData.episodes[n - 1]; }
  episodes() { return this.seasonData.episodes; }
  balance() { return this.bal; }
  trialBalance(type, level) {
    const t = this.bal.trials[type] && this.bal.trials[type][String(level)];
    if (!t) throw gameError('CONTENT_INVALID', 'ContentLoader', 'balance ' + type + ':' + level);
    return t;
  }
  characters() { return this.chars; }
  character(id) { return this.chars.find((c) => c.id === id); }
  clue(id) { return this.caseData.clues.find((c) => c.id === id); }
  item(id) { return this.itemMap[id]; }
  async pool(type, level) {
    if (!this.pools[type]) {
      let f;
      try { f = await getJson('trials/' + type + '.json'); }
      catch (e) { log.warn('POOL_' + type, String(e.message)); this.pools[type] = []; return []; }
      const ok = [];
      (f.tasks || []).forEach((t) => {
        const check = TASK_CHECK[type];
        if (t && t.id && t.payload && (!check || check(t.payload))) ok.push(Object.assign({ type }, t));
        else log.warn('TASK_BAD_' + (t && t.id), 'Задание пропущено: ' + (t && t.id));
      });
      this.pools[type] = ok;
    }
    return this.pools[type].filter((t) => t.level === level);
  }
  async available(type, level) { return (await this.pool(type, level)).length > 0; }
  async draw(type, level, rng, excludeIds) {
    const pool = (await this.pool(type, level)).filter((t) => !(excludeIds || []).includes(t.id));
    if (!pool.length) throw gameError('CONTENT_EMPTY', 'ContentLoader', 'Пустой пул ' + type + ':' + level);
    const key = type + ':' + level;
    const draws = this.progress.draws();
    const st = draws[key] || { bag: [], recent: [] };
    const ids = pool.map((t) => t.id);
    st.bag = st.bag.filter((id) => ids.includes(id));
    if (!st.bag.length) {
      let bag = rng.shuffle(ids);
      const recent = st.recent.slice(-this.bal.noRepeatLast);
      if (bag.length > recent.length + 1) {
        const head = bag.filter((id) => !recent.includes(id));
        const tail = bag.filter((id) => recent.includes(id));
        bag = head.slice(0, this.bal.noRepeatLast).concat(head.slice(this.bal.noRepeatLast), tail);
      }
      st.bag = bag;
    }
    const id = st.bag.shift();
    st.recent = st.recent.concat(id).slice(-10);
    draws[key] = st;
    this.progress.saveDraws(draws);
    return pool.find((t) => t.id === id);
  }
  text(key, vars) {
    let s = this.texts[key];
    if (s == null) { log.warn('TEXT_' + key, 'Нет текста ' + key); return '[' + key + ']'; }
    if (vars) Object.keys(vars).forEach((k) => { s = s.split('{' + k + '}').join(String(vars[k])); });
    return s;
  }
  pickText(prefix, rng) {
    const keys = Object.keys(this.texts).filter((k) => k.indexOf(prefix + '.') === 0);
    if (!keys.length) return '';
    let k = rng.pick(keys);
    if (keys.length > 1 && k === this.lastPick[prefix]) k = keys[(keys.indexOf(k) + 1) % keys.length];
    this.lastPick[prefix] = k;
    return this.texts[k];
  }
}
