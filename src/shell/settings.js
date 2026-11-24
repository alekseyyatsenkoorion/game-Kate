import { Scene } from '../core/scene-manager.js';
import { confirmBox } from '../core/overlay.js';
import { actionOf, topbar } from './ui.js';

export class SettingsScene extends Scene {
  static get id() { return 'settings'; }
  async enter(root, params) { await super.enter(root, params); this.draw(); }
  draw() {
    const s = this.app.progress.settings();
    const row = (key, on) => '<button class="btn ghost" data-action="tg" data-k="' + key + '">' + this.t('ui.set.' + key) + ': ' + this.t(on ? 'ui.on' : 'ui.off') + '</button>';
    this.root.innerHTML =
      '<div class="screen center settings">' + topbar(this, 'back') +
        '<h2>' + this.t('ui.settings') + '</h2>' +
        '<div class="menu">' + row('music', s.music) + row('sfx', s.sfx) + row('voice', s.voice) +
          '<button class="btn ghost" data-action="reset">' + this.t('ui.restart') + '</button></div>' +
        '<p class="info">' + this.t('ui.installHint') + '</p>' +
        '<p class="info small">v' + this.app.updater.version + '</p>' +
      '</div>';
  }
  async onInput(e) {
    const a = actionOf(e); if (!a) return;
    this.app.audio.sfx('tap');
    if (a.act === 'back') this.app.scenes.back();
    if (a.act === 'tg') {
      const k = a.el.getAttribute('data-k');
      this.app.audio.setMuted(k, this.app.progress.settings()[k]);
      if (k === 'voice' && !this.app.audio.isMuted('voice')) this.app.audio.praise(this.t('ui.voiceTest'));
      this.draw();
    }
    if (a.act === 'reset') {
      const ok = await confirmBox(this.t('ui.restartAsk'), this.t('ui.restartYes'), this.t('ui.cancel'));
      if (ok) { this.app.progress.reset(); this.app.scenes.replace('title'); }
    }
  }
}
