// DayLock — замок по дням (contracts.md §8).
import { log } from './log.js';

function pad(n) { return n < 10 ? '0' + n : '' + n; }

export class DayLock {
  constructor(progress, balance, total) { this.progress = progress; this.balance = balance; this.total = total; this.now = () => new Date(); }
  today() {
    try { const d = this.now(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
    catch (e) { log.warn('DATE_BAD', 'Дата не читается'); return 'unknown'; }
  }
  quota() { return this.now().getDay() === 6 ? this.balance.daily.saturday : this.balance.daily.weekday; }
  openedToday() {
    const o = this.progress.get().openedOn, t = this.today();
    return Object.keys(o).filter((n) => o[n] === t).length;
  }
  quotaLeft() { return Math.max(0, this.quota() - this.openedToday()); }
  nextEpisode() {
    const eps = this.progress.get().episodes;
    for (let n = 1; n <= this.total; n++) if (!eps[n]) return n;
    return null;
  }
  availability(n) {
    const p = this.progress.get();
    if (p.episodes[n]) return 'done';
    if (n !== this.nextEpisode()) return 'locked';
    if (p.openedOn[n]) return 'open';                     // уже открытый не закрывается
    if (this.progress.settings().test || this.quotaLeft() > 0) return 'open';
    return 'wait';
  }
  markStarted(n) {
    if (this.progress.get().openedOn[n]) return;
    const t = this.today();
    this.progress.update((d) => { d.openedOn[n] = t; });
  }
}
