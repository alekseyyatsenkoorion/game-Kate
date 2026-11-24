// Сцена debug (режим теста) и сцена error.
import { Scene } from './scene-manager.js';
import { log } from './log.js';

export class DebugScene extends Scene {
  static get id() { return 'debug'; }
  async enter(root, params) {
    await super.enter(root, params);
    if (!this.app.progress.settings().test) { this.app.scenes.replace('season'); return; }
    this.draw();
  }
  draw(msg) {
    const opts = [];
    for (let i = 1; i <= 12; i++) opts.push('<button class="btn small ghost" data-go="' + i + '">' + i + '</button>');
    this.root.innerHTML =
      '<div class="screen debug">' +
        '<div class="topbar"><button class="btn small ghost" data-action="back">' + this.t('ui.back') + '</button><h2>' + this.t('ui.debug') + '</h2><span class="ver">v' + this.app.updater.version + '</span></div>' +
        '<p class="info">' + this.t('ui.debugJump') + '</p><div class="row wrap">' + opts.join('') + '</div>' +
        '<div class="row wrap">' +
          '<button class="btn small ghost" data-action="pass">' + this.t('ui.debugPass') + '</button>' +
          '<button class="btn small ghost" data-action="power">+5 ' + this.t('ui.power') + '</button>' +
          '<button class="btn small ghost" data-action="reset">' + this.t('ui.debugReset') + '</button>' +
          '<button class="btn small ghost" data-action="export">' + this.t('ui.debugExport') + '</button>' +
          '<button class="btn small ghost" data-action="import">' + this.t('ui.debugImport') + '</button>' +
          '<button class="btn small ghost" data-action="off">' + this.t('ui.debugOff') + '</button>' +
        '</div>' +
        '<textarea class="code" spellcheck="false" placeholder="' + this.t('ui.debugCodeHint') + '">' + (msg || '') + '</textarea>' +
        '<div class="log">' + log.entries().slice(-8).map((e) => '<div>' + e.level + ' ' + e.key + '</div>').join('') + '</div>' +
      '</div>';
  }
  jump(n) {
    const today = this.app.dayLock.today();
    this.app.progress.clearRun();
    this.app.progress.update((d) => {
      d.episodes = {}; d.openedOn = {};
      for (let i = 1; i < n; i++) { d.episodes[i] = { firstDate: today, stars: 2, points: 60, bestPoints: 60, attempts: 1 }; d.openedOn[i] = today; }
    });
    this.app.scenes.replace('intro', { n });
  }
  onInput(e) {
    if (e.action !== 'tap' || !e.target || !e.target.closest) return;
    const go = e.target.closest('[data-go]');
    if (go) { this.jump(+go.getAttribute('data-go')); return; }
    const a = e.target.closest('[data-action]'); if (!a) return;
    const p = this.app.progress, act = a.getAttribute('data-action');
    if (act === 'back') this.app.scenes.replace('season');
    if (act === 'pass') {
      const n = this.app.dayLock.nextEpisode(); if (!n) return;
      const today = this.app.dayLock.today();
      p.clearRun();
      p.update((d) => { d.episodes[n] = { firstDate: today, stars: 3, points: 100, bestPoints: 100, attempts: 1 }; d.openedOn[n] = today; d.power += 3; });
      this.draw();
    }
    if (act === 'power') { p.update((d) => { d.power += 5; }); this.draw(); }
    if (act === 'reset') { p.reset(); this.draw(); }
    if (act === 'export') this.draw(p.exportCode());
    if (act === 'import') { const ok = p.importCode(this.root.querySelector('.code').value); this.draw(ok ? 'OK' : '—'); }
    if (act === 'off') { p.setSettings({ test: false }); this.app.scenes.replace('title'); }
  }
}

export class ErrorScene extends Scene {
  static get id() { return 'error'; }
  async enter(root, params) {
    await super.enter(root, params);
    const msg = this.app.content && this.app.content.texts ? this.t('ui.errorText') : 'Что-то пошло не так';
    const btn = this.app.content && this.app.content.texts ? this.t('ui.toSeason') : 'В сезон';
    root.innerHTML = '<div class="screen center"><h2>' + msg + '</h2><p class="info">' + (params.code || '') + '</p>' +
      '<button class="btn gold" data-action="season">' + btn + '</button></div>';
  }
  onInput(e) {
    if (e.action === 'tap' && e.target && e.target.closest && e.target.closest('[data-action]')) {
      if (this.app.content && this.app.content.seasonData) this.app.scenes.replace('season'); else location.reload();
    }
  }
}
