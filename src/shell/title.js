import { Scene } from '../core/scene-manager.js';
import { candles, EYE } from './ui.js';
import { confirmBox } from '../core/overlay.js';

export class TitleScene extends Scene {
  static get id() { return 'title'; }
  async enter(root, params) {
    await super.enter(root, params);
    this.taps = 0;
    this.draw();
  }
  draw() {
    const app = this.app, started = Object.keys(app.progress.get().episodes).length > 0 || !!app.progress.run();
    this.root.innerHTML =
      '<div class="screen center title-screen">' + candles() +
        (app.debug ? '<div class="test-badge">' + this.t('ui.testBadge') + '</div>' : '') +
        '<div class="eye" data-action="eye">' + EYE + '</div>' +
        '<h1>' + this.t('ui.gameTitle') + '</h1>' +
        '<p class="sub">' + this.t('ui.gameSub') + '</p>' +
        '<div class="menu">' +
          '<button class="btn gold" data-action="season">' + this.t(started ? 'ui.continue' : 'ui.start') + '</button>' +
          '<button class="btn ghost" data-action="settings">' + this.t('ui.settings') + '</button>' +
        '</div>' +
        (app.progress.recovered ? '<p class="warn">' + this.t('ui.recovered') + '</p>' : '') +
        (!app.progress.persistent ? '<p class="warn">' + this.t('ui.noStorage') + '</p>' : '') +
      '</div>';
  }
  onInput(e) {
    if (e.action !== 'tap' || !e.target || !e.target.closest) return;
    const a = e.target.closest('[data-action]'); if (!a) return;
    const act = a.getAttribute('data-action');
    if (act === 'season') { this.app.audio.sfx('tap'); this.app.scenes.go('season'); }
    if (act === 'settings') { this.app.audio.sfx('tap'); this.app.scenes.go('settings'); }
    if (act === 'eye') {
      this.taps++;
      clearTimeout(this.tapTimer);
      this.tapTimer = this.later(() => { this.taps = 0; }, 3000);
      if (this.taps >= 7) {
        this.taps = 0;
        const on = !this.app.progress.settings().test;
        this.app.progress.setSettings({ test: on });
        this.draw();
        confirmBox(this.t(on ? 'ui.testOn' : 'ui.testOff'), 'OK');
      }
    }
  }
}
