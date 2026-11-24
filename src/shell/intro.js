import { Scene } from '../core/scene-manager.js';
import { candles, esc, actionOf, topbar, bgAttr, portrait } from './ui.js';

export class IntroScene extends Scene {
  static get id() { return 'intro'; }
  async enter(root, params) {
    await super.enter(root, params);
    const app = this.app, n = +params.n, ep = app.content.episode(n);
    this.n = n;
    const run = app.progress.run();
    this.resumeIdx = run && run.n === n ? run.idx || 0 : 0;
    if (run && run.n !== n) app.progress.clearRun();      // начали другой выпуск — старый незавершённый сбрасывается
    const replay = !!app.progress.get().episodes[n];
    const traps = app.progress.get().skeptic.pendingTraps;
    const intro = this.t(ep.introKey);
    const names = ep.trials.map((t) => this.t('trial.' + t.type + '.name') + ' (' + this.t('ui.level', { l: t.level }) + ')').join(' + ');
    root.innerHTML =
      '<div class="screen intro"' + bgAttr(app, 'bg-studio') + '>' + candles() + topbar(this, 'season') +
        '<div class="ep-label">' + this.t('ui.episodeN', { n }) + '</div>' +
        '<h2>' + esc(ep.title) + '</h2>' +
        '<div class="host with-p">' + portrait(app, 'host', 64) + '<div><div class="host-name">' + this.t('char.host.name') + '</div><p>' + esc(intro) + '</p></div></div>' +
        (traps && !replay ? '<div class="host skeptic with-p">' + portrait(app, 'skeptic', 64) + '<div><div class="host-name">' + this.t('char.skeptic.name') + '</div><p>' + this.t('skeptic.trapWarn') + '</p></div></div>' : '') +
        '<div class="trial-list">' + this.t('ui.trials') + ': <b>' + esc(names) + '</b></div>' +
        '<p class="info small">' + this.t('trial.' + ep.trials[Math.min(this.resumeIdx, ep.trials.length - 1)].type + '.rules') + '</p>' +
        (replay ? '<p class="info">' + this.t('ui.replayNote') + '</p>' : '') +
        this.guestRow() +
        '<button class="btn gold" data-action="start">' + this.t(this.resumeIdx ? 'ui.resume' : 'ui.startTrial') + '</button>' +
      '</div>';
    if (app.audio.unlocked) app.audio.sayText(intro);
  }
  // Переключатель «Играем вдвоём» (Т-19): хранится в progress.guest.enabled
  guestOn() { const g = this.app.progress.get().guest; return !!(g && g.enabled); }
  guestRow() {
    const on = this.guestOn();
    return '<div class="guest-row"><button class="btn small guest-tg' + (on ? ' is-on' : ' ghost') + '" data-action="guest">' +
      this.t('ui.guestToggle') + ': ' + this.t(on ? 'ui.on' : 'ui.off') + '</button>' +
      '<span class="guest-hint">' + this.t('ui.guestHint') + '</span></div>';
  }
  toggleGuest() {
    const on = !this.guestOn();
    this.app.progress.update((d) => { d.guest = Object.assign({ enabled: false, points: 0 }, d.guest, { enabled: on }); });
    const row = this.root.querySelector('.guest-row');
    if (row) row.outerHTML = this.guestRow();
  }
  onInput(e) {
    const a = actionOf(e); if (!a) return;
    this.app.audio.sfx('tap');
    if (a.act === 'guest') { this.toggleGuest(); return; }
    if (a.act === 'season') { this.app.audio.stopAll(); this.app.audio.music('ambient'); this.app.scenes.replace('season'); }
    if (a.act === 'start') {
      if (this.app.audio.speech) this.app.audio.speech.cancel();
      const ep = this.app.content.episode(this.n);
      if (this.resumeIdx >= ep.trials.length) this.app.scenes.replace('result', { n: this.n });   // все испытания сыграны — сразу итоги
      else this.app.scenes.replace('trial', { n: this.n, idx: this.resumeIdx });
    }
  }
}
