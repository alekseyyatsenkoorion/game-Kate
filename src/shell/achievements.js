// Достижения (зона D): описания — data/achievements.json, условия — правила rule.kind ниже.
// Проверка — после записи выпуска (result) и при открытии разгадки дела. Запись — progress.achievements.
import { log } from '../core/log.js';
import { esc } from './ui.js';

let defs = null;

// Описания берёт ContentLoader.achievements() (data/achievements.json).
export async function loadAchievements(app) {
  if (defs) return defs;
  const c = app.content;
  let list = null;
  if (typeof c.achievements === 'function') list = c.achievements();
  if (!Array.isArray(list)) { log.warn('ACH_LOAD', 'achievements.json not loaded'); list = []; }
  defs = list.filter((a) => a && a.id && a.titleKey && a.rule);
  return defs;
}

function titleRank(app, id) { return app.content.balance().titles.findIndex((t) => t.id === id); }
function done(st) { return Object.keys(st.episodes || {}); }

// x: { app, state, results?, caseSolved? }
const RULES = {
  episodes: (r, x) => done(x.state).length >= r.min,
  starEpisodes: (r, x) => done(x.state).filter((n) => x.state.episodes[n].stars >= r.stars).length >= r.min,
  // испытание, которое забрал гость (режим вдвоём), Кате в зачёт достижений не идёт
  cleanRun: (r, x) => !!x.results && x.results.length > 0 && x.results.every((t) => t && t.solved && !t[r.zero] && !(t.guest && t.guest.winner === 'guest')),
  trial: (r, x) => !!x.results && x.results.some((t) => t && t.type === r.type && (r.level == null || t.level === r.level) && t.solved && !t[r.zero] && !(t.guest && t.guest.winner === 'guest')),
  survived: (r, x) => Object.keys(x.state.rivals || {}).some((id) => x.state.rivals[id].eliminatedAfter != null),
  title: (r, x) => { const need = titleRank(x.app, r.id); return need >= 0 && titleRank(x.app, x.app.scoring.title(x.state.totalPoints).id) >= need; },
  season: (r, x) => done(x.state).length >= x.app.content.episodes().length,
  caseSolved: (r, x) => !!x.caseSolved
};

// Проверяет условия, записывает новые достижения, возвращает их описания.
export async function awardAchievements(app, extra) {
  const list = await loadAchievements(app);
  const st = app.progress.get(), have = st.achievements || [];
  const x = Object.assign({ app, state: st }, extra || {});
  const fresh = list.filter((a) => {
    if (have.indexOf(a.id) >= 0) return false;
    const f = RULES[a.rule.kind];
    if (!f) { log.warn('ACH_RULE_' + a.rule.kind, 'unknown achievement rule'); return false; }
    try { return !!f(a.rule, x); } catch (e) { log.warn('ACH_CHECK_' + a.id, String(e)); return false; }
  });
  if (fresh.length) app.progress.update((d) => { d.achievements = (d.achievements || []).concat(fresh.map((a) => a.id)); });
  return fresh;
}

// Плашки-тосты на экране сцены: по очереди, каждая со звоном, сами исчезают.
export function showToasts(scene, list, delayMs) {
  if (!list || !list.length || !scene.root || scene.gone) return;
  let box = scene.root.querySelector('.ach-toasts');
  if (!box) { box = document.createElement('div'); box.className = 'ach-toasts'; scene.root.appendChild(box); }
  list.forEach((a, i) => {
    scene.later(() => {
      const el = document.createElement('div');
      el.className = 'ach-toast';
      el.setAttribute('data-action', 'ach-toast');
      el.innerHTML = '<span class="ach-ico">' + esc(a.icon || '') + '</span><span class="ach-txt"><span class="ach-new">' +
        esc(scene.t('ach.new')) + '</span><span class="ach-name">' + esc(scene.t(a.titleKey)) + '</span></span>';
      box.appendChild(el);
      scene.app.audio.sfx('chime');
      scene.later(() => el.classList.add('out'), 4600);
      scene.later(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 5200);
    }, (delayMs || 0) + i * 900);
  });
}

// Список для настроек: полученные — яркие, остальные — тусклые с подсказкой.
export function achievementsPanel(scene, list) {
  const have = scene.app.progress.get().achievements || [];
  const items = list.map((a) => {
    const got = have.indexOf(a.id) >= 0;
    return '<div class="ach-item' + (got ? ' got' : '') + '"><span class="ach-ico">' + esc(a.icon || '') + '</span>' +
      '<span class="ach-txt"><span class="ach-name">' + esc(scene.t(a.titleKey)) + '</span><span class="ach-desc">' + esc(scene.t(a.descKey)) + '</span></span></div>';
  }).join('');
  const k = list.filter((a) => have.indexOf(a.id) >= 0).length;
  return '<div class="ach-panel" data-action="ach-close"><div class="ach-box" data-action="noop">' +
    '<h2>' + esc(scene.t('ach.list')) + '</h2>' +
    '<p class="info">' + esc(scene.t('ach.count', { k, n: list.length })) + '</p>' +
    '<div class="ach-grid">' + items + '</div>' +
    '<button class="btn small gold" data-action="ach-close">' + esc(scene.t('ui.close')) + '</button>' +
  '</div></div>';
}

export function achievementsCount(app, list) {
  const have = app.progress.get().achievements || [];
  return list.filter((a) => have.indexOf(a.id) >= 0).length;
}
