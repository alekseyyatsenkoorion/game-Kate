import { Scene } from '../core/scene-manager.js';
import { confirmBox } from '../core/overlay.js';
import { actionOf, topbar } from './ui.js';
import { loadAchievements, achievementsPanel, achievementsCount } from './achievements.js';

const VOL_STEPS = [0, 0.25, 0.5, 0.75, 1];      // 5 шагов громкости музыки, 0 — выкл

export class SettingsScene extends Scene {
  static get id() { return 'settings'; }
  async enter(root, params) {
    await super.enter(root, params);
    this.panel = false;
    this.ach = await loadAchievements(this.app);
    this.draw();
  }
  vol() { const v = this.app.progress.settings().musicVolume; return typeof v === 'number' ? v : 1; }
  draw() {
    const s = this.app.progress.settings();
    const row = (key, on) => '<button class="btn ghost" data-action="tg" data-k="' + key + '">' + this.t('ui.set.' + key) + ': ' + this.t(on ? 'ui.on' : 'ui.off') + '</button>';
    const cur = this.vol();
    const steps = VOL_STEPS.map((v) => '<button class="btn small vstep' + (Math.abs(v - cur) < 0.01 ? ' gold' : ' ghost') +
      '" data-action="vol" data-v="' + v + '">' + Math.round(v * 100) + '%</button>').join('');
    this.root.innerHTML =
      '<div class="screen center settings">' + topbar(this, 'back') +
        '<h2>' + this.t('ui.settings') + '</h2>' +
        '<div class="menu">' + row('music', s.music) +
          '<div class="vol"><span class="vol-l">' + this.t('ui.set.musicVolume') + '</span>' + steps + '</div>' +
          row('sfx', s.sfx) + row('voice', s.voice) +
          '<button class="btn ghost" data-action="ach">' + this.t('ach.list') + ' (' + achievementsCount(this.app, this.ach) + '/' + this.ach.length + ')</button>' +
          '<button class="btn ghost" data-action="reset">' + this.t('ui.restart') + '</button></div>' +
        '<p class="info">' + this.t('ui.installHint') + '</p>' +
        '<p class="info small">v' + this.app.updater.version + '</p>' +
        (this.panel ? achievementsPanel(this, this.ach) : '') +
      '</div>';
  }
  // setMuted('music', true) в ядре забывает дорожку — после включения запускаем фон заново (как intro)
  ensureMusic() { const au = this.app.audio; if (!au.isMuted('music') && this.vol() > 0 && !au.musicNode) au.music('ambient'); }
  async onInput(e) {
    const a = actionOf(e); if (!a) return;
    if (a.act === 'noop') return;
    this.app.audio.sfx('tap');
    if (a.act === 'ach') { this.panel = true; this.draw(); return; }
    if (a.act === 'ach-close') { this.panel = false; this.draw(); return; }
    if (a.act === 'back') this.app.scenes.back();
    if (a.act === 'tg') {
      const k = a.el.getAttribute('data-k');
      this.app.audio.setMuted(k, this.app.progress.settings()[k]);
      if (k === 'voice' && !this.app.audio.isMuted('voice')) this.app.audio.praise(this.t('ui.voiceTest'));
      if (k === 'music') this.ensureMusic();
      this.draw();
    }
    if (a.act === 'vol') {
      const v = +a.el.getAttribute('data-v');
      if (v > 0 && this.app.audio.isMuted('music')) this.app.audio.setMuted('music', false);   // выбрали громкость — музыка включается
      this.app.audio.setMusicVolume(v);
      this.ensureMusic();
      this.draw();
    }
    if (a.act === 'reset') {
      const ok = await confirmBox(this.t('ui.restartAsk'), this.t('ui.restartYes'), this.t('ui.cancel'));
      if (ok) { this.app.progress.reset(); this.app.scenes.replace('title'); }
    }
  }
}
