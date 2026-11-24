import { Scene } from '../core/scene-manager.js';
import { createRng, hashSeed } from '../core/rng.js';
import { candles, stars, esc, actionOf } from './ui.js';

export class ResultScene extends Scene {
  static get id() { return 'result'; }
  async enter(root, params) {
    await super.enter(root, params);
    const app = this.app, c = app.content, n = +params.n, ep = c.episode(n);
    const run = app.progress.run();
    if (!run || run.n !== n || run.results.length < ep.trials.length) { app.scenes.replace('season'); return; }
    this.n = n;
    const state = app.progress.get();
    const first = !state.episodes[n];
    const scores = run.results.map((r, i) => app.scoring.trial(r, c.trialBalance(ep.trials[i].type, ep.trials[i].level)));
    const epScore = app.scoring.episode(n, scores);
    const hintsUsed = run.results.reduce((s, r) => s + r.hintsUsed, 0);
    const rng = createRng(hashSeed('rivals', n, run.attempt));
    const riv = first ? app.scoring.rivals(n, epScore, state, rng, hintsUsed) : null;
    const clues = (ep.clues || []).concat(...run.results.map((r) => r.caseClues || []));
    this.mustReplay = !!(riv && riv.playerMustReplay);
    if (!this.mustReplay) app.progress.recordEpisode(n, epScore, riv, clues, app.dayLock.today());
    app.progress.clearRun();

    const prng = createRng(hashSeed('praise', n, run.attempt, Date.now()));
    const hostLine = epScore.stars >= 2 ? c.pickText('host.praise', prng) : this.t('host.lowScore');
    const skLine = epScore.stars <= 1 || hintsUsed >= 2 ? c.pickText('skeptic.jab', prng) : this.t('skeptic.grudging');
    let table = '';
    if (riv) {
      table = '<table class="rivals">' + riv.table.map((r) => {
        const name = r.id === 'player' ? this.t('ui.you') : c.character(r.id).name;
        const out = r.id === riv.eliminated ? ' <span class="out">' + this.t('ui.eliminated') + '</span>' : '';
        return '<tr class="' + (r.id === 'player' ? 'me' : '') + '"><td>' + r.place + '</td><td>' + esc(name) + out + '</td><td>' + r.points + '</td></tr>';
      }).join('') + '</table>';
    }
    const gotClues = !this.mustReplay && first && clues.length ? '<p class="gain">' + this.t('ui.newClues', { k: clues.length }) + '</p>' : '';
    root.innerHTML =
      '<div class="screen result">' + candles() +
        '<div class="ep-label">' + this.t('ui.resultsOf', { n }) + '</div>' +
        '<h2>' + esc(ep.title) + '</h2>' +
        '<div class="res-row"><div class="res-left">' +
          '<div class="big-stars">' + stars(epScore.stars) + '</div>' +
          '<p class="pts">' + this.t('ui.points') + ': <b>' + epScore.points + '</b>' + (first && !this.mustReplay ? ' · +' + epScore.powerGain + ' ' + this.t('ui.powerGen') : '') + '</p>' +
          '<div class="host"><div class="host-name">' + this.t('char.host.name') + '</div><p>' + esc(hostLine) + '</p></div>' +
          '<div class="host skeptic"><div class="host-name">' + this.t('char.skeptic.name') + '</div><p>' + esc(skLine) + '</p></div>' +
          gotClues +
        '</div>' + (table ? '<div class="res-right"><h3>' + this.t('ui.standings') + '</h3>' + table +
          (this.mustReplay ? '<p class="warn">' + this.t('ui.mustReplay') + '</p>' : '') + '</div>' : '') +
        '</div>' +
        (this.mustReplay ? '<button class="btn gold" data-action="replay">' + this.t('ui.replay') + '</button>'
                         : '<button class="btn gold" data-action="season">' + this.t('ui.toSeason') + '</button>') +
      '</div>';
    app.audio.sfx('star');
    if (epScore.stars >= 2) app.audio.praise(hostLine); else app.audio.laugh(skLine);
  }
  onInput(e) {
    const a = actionOf(e); if (!a) return;
    this.app.audio.sfx('tap');
    if (a.act === 'season') this.app.scenes.replace('season');
    if (a.act === 'replay') this.app.scenes.replace('intro', { n: this.n });
  }
}
