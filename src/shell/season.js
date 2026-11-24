import { Scene } from '../core/scene-manager.js';
import { TRIALS } from '../trials/index.js';
import { stars, esc, actionOf, topbar, bgAttr } from './ui.js';

export class SeasonScene extends Scene {
  static get id() { return 'season'; }
  async enter(root, params) {
    await super.enter(root, params);
    const c = this.app.content;
    this.ready = {};
    for (const ep of c.episodes()) {
      let ok = true;
      for (const t of ep.trials) { if (!TRIALS[t.type] || !(await c.available(t.type, t.level))) ok = false; }
      this.ready[ep.n] = ok;
    }
    this.draw();
  }
  draw() {
    const app = this.app, c = app.content, p = app.progress.get(), dl = app.dayLock;
    const cards = c.episodes().map((ep) => {
      const st = dl.availability(ep.n), ready = this.ready[ep.n];
      let foot;
      if (st === 'done') foot = '<span class="stars">' + stars(p.episodes[ep.n].stars) + '</span>';
      else if (st === 'open') foot = ready ? '<span class="play">' + this.t('ui.play') + '</span>' : '<span class="soon">' + this.t('ui.soon') + '</span>';
      else if (st === 'wait') foot = '<span class="waitt">' + this.t('ui.tomorrow') + '</span>';
      else foot = '<span class="lock">🔒</span>';
      const tap = (st === 'open' || st === 'done') && ready;
      const names = ep.trials.map((t) => this.t('trial.' + t.type + '.name')).join(' + ');
      return '<div class="card ' + st + (ready ? '' : ' notready') + '"' + (tap ? ' data-action="ep" data-n="' + ep.n + '"' : '') + '>' +
        '<div class="num">' + ep.n + '</div><div class="ctitle">' + esc(ep.title) + '</div>' +
        '<div class="ctrial">' + esc(names) + '</div><div class="cfoot">' + foot + '</div></div>';
    }).join('');
    const finished = dl.nextEpisode() === null;
    const info = finished ? this.t('ui.seasonDone') :
      app.debug ? this.t('ui.testNoLock') : this.t(dl.availability(dl.nextEpisode()) === 'open' ? 'ui.todayOpen' : 'ui.todayWait');
    const title = app.scoring.title(p.totalPoints).label;
    this.root.innerHTML =
      '<div class="screen season"' + bgAttr(app, 'bg-season') + '>' + topbar(this, 'title') +
        '<h2>' + this.t('ui.season') + '</h2>' +
        '<p class="info">' + esc(title) + ' · ' + this.t('ui.points') + ': ' + p.totalPoints + ' · ' + info + '</p>' +
        '<div class="grid">' + cards + '</div>' +
        '<div class="row">' +
          '<button class="btn small ghost" data-action="diary">' + this.t('ui.diary') + ' (' + p.case.clues.length + ')</button>' +
          (app.debug ? '<button class="btn small ghost testb" data-action="debug">' + this.t('ui.debug') + '</button>' : '') +
        '</div>' +
      '</div>';
  }
  onInput(e) {
    const a = actionOf(e); if (!a) return;
    this.app.audio.sfx('tap');
    if (a.act === 'title') this.app.scenes.replace('title');
    if (a.act === 'ep') this.app.scenes.go('intro', { n: +a.el.getAttribute('data-n') });
    if (a.act === 'diary') this.app.scenes.go('diary');
    if (a.act === 'debug') this.app.scenes.go('debug');
  }
  onReturn() { this.draw(); }
}
