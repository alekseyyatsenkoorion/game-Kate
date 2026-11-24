// Scoring — чистые функции, числа из balance.json (contracts.md §7).
import { gameError } from './log.js';

function bad(msg) { return gameError('SCORE_INPUT', 'Scoring', msg); }

export class Scoring {
  constructor(content) { this.content = content; }
  trial(r, b) {
    if (!(r.accuracy >= 0 && r.accuracy <= 1)) throw bad('accuracy ' + r.accuracy);
    if ([1, 2, 3].indexOf(r.level) < 0) throw bad('level ' + r.level);
    const base = Math.round(b.base * r.accuracy);
    const hints = b.hintCost * r.hintsUsed, mistakes = b.mistakeCost * r.mistakes;
    const time = r.solved && r.timeMs < b.par ? b.timeBonus : 0;
    let points = Math.max(0, base - hints - mistakes + time);
    if (!r.solved) points = Math.round(points * b.unsolvedFactor);
    let stars = 0;
    if (r.solved) stars = 1;
    if (r.solved && points >= b.stars2) stars = 2;
    if (r.solved && r.hintsUsed === 0 && points >= b.stars3) stars = 3;
    return { points, stars, breakdown: { base, hints: -hints, mistakes: -mistakes, time } };
  }
  episode(n, scores) {
    if (!(n >= 1 && n <= 12)) throw bad('n ' + n);
    const points = scores.reduce((s, x) => s + x.points, 0);
    const sumStars = scores.reduce((s, x) => s + x.stars, 0);
    return { points, stars: Math.floor(sumStars / scores.length), powerGain: sumStars, newClues: [] };
  }
  rivals(n, player, state, rng, hintsUsed) {
    const bal = this.content.balance();
    const ep = this.content.episode(n);
    const rows = [];
    this.content.characters().filter((c) => c.role === 'rival').forEach((c) => {
      const st = state.rivals[c.id] || { points: 0, eliminatedAfter: null };
      if (st.eliminatedAfter) return;
      let gained = 0;
      ep.trials.forEach((t) => {
        const b = this.content.trialBalance(t.type, t.level);
        gained += Math.round(b.base * Math.min(1, Math.max(0, rng.normal(c.skill, c.spread))));
      });
      rows.push({ id: c.id, points: st.points + gained, gained });
    });
    const playerTotal = state.totalPoints + player.points;
    rows.push({ id: 'player', points: playerTotal, gained: player.points });
    rows.sort((a, b) => b.points - a.points);
    rows.forEach((r, i) => { r.place = i + 1; });
    let eliminated = null, playerMustReplay = false;
    if (bal.eliminateAfter.indexOf(n) >= 0) {
      const last = rows[rows.length - 1];
      if (last.id === 'player') playerMustReplay = true; else eliminated = last.id;
    }
    return { table: rows, eliminated, playerMustReplay, skepticTraps: (hintsUsed || 0) >= 2 ? 1 : 0 };
  }
  title(totalPoints) {
    const ts = this.content.balance().titles.filter((t) => totalPoints >= t.from);
    const t = ts[ts.length - 1];
    return { id: t.id, label: this.content.text(t.labelKey) };
  }
}
