// Общие кусочки разметки оболочки.
export const EYE = '<svg viewBox="0 0 100 60" class="eye-svg"><path d="M5 30 Q50 -10 95 30 Q50 70 5 30Z" fill="none" stroke="currentColor" stroke-width="4"/><circle cx="50" cy="30" r="13" fill="currentColor"/><circle cx="55" cy="25" r="4" fill="#0d0716"/></svg>';

export function candles() {
  return '<div class="candles left"><i class="c c1"></i><i class="c c2"></i></div>' +
         '<div class="candles right"><i class="c c3"></i><i class="c c1"></i></div>';
}
export function stars(k) { let s = ''; for (let i = 1; i <= 3; i++) s += i <= k ? '★' : '☆'; return s; }
export function esc(t) {
  return String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
export function actionOf(e) {
  if (e.action !== 'tap' || !e.target || !e.target.closest) return null;
  const a = e.target.closest('[data-action]');
  return a ? { act: a.getAttribute('data-action'), el: a } : null;
}
export function topbar(scene, backAction) {
  const app = scene.app;
  return '<div class="topbar">' +
    (backAction ? '<button class="btn small ghost" data-action="' + backAction + '">' + scene.t('ui.back') + '</button>' : '<span></span>') +
    '<div class="power">' + scene.t('ui.power') + ': <b>' + app.progress.get().power + '</b></div></div>';
}

// Фон сцены: картинка из ChatGPT (если есть) под тёмной вуалью, иначе — фон по умолчанию.
export function bgAttr(app, id) {
  if (!app.assets.has(id)) return '';
  return ' style="background-image:linear-gradient(rgba(13,7,22,0.55),rgba(13,7,22,0.75)),url(' + app.assets.url(id) + ');background-size:cover;background-position:center"';
}
// Портрет персонажа: картинка из ChatGPT или медальон с инициалом в цвете персонажа.
export function portrait(app, charId, size) {
  const c = app.content.character(charId); if (!c) return '';
  const s = size || 64, id = c.portrait;
  if (app.assets.has(id)) return '<img class="portrait" src="' + app.assets.url(id) + '" width="' + s + '" height="' + s + '" alt="">';
  return '<span class="portrait medal" style="width:' + s + 'px;height:' + s + 'px;line-height:' + s + 'px;font-size:' + Math.round(s * 0.45) + 'px;border-color:' + c.color + ';color:' + c.color + '">' + esc(c.name.charAt(0)) + '</span>';
}
