import { Scene } from '../core/scene-manager.js';
import { esc, actionOf, topbar } from './ui.js';

// Дневник сквозного дела: улики карточками, связи — линиями. Тык по двум уликам связывает/развязывает.
export class DiaryScene extends Scene {
  static get id() { return 'diary'; }
  async enter(root, params) { await super.enter(root, params); this.sel = null; this.changed = false; this.draw(); }
  pos(i) { const col = i % 4, row = Math.floor(i / 4); return { x: 40 + col * 236, y: 180 + row * 145 }; }
  draw() {
    const c = this.app.content, p = this.app.progress.get();
    const ids = p.case.clues;
    const cards = ids.map((id, i) => {
      const cl = c.clue(id), q = this.pos(i);
      return '<div class="clue' + (this.sel === id ? ' sel' : '') + '" data-action="clue" data-id="' + id + '" style="left:' + q.x + 'px;top:' + q.y + 'px">' +
        '<div class="clue-n">' + this.t('ui.episodeN', { n: cl.episode }) + '</div><div class="clue-t">' + esc(this.t(cl.textKey)) + '</div></div>';
    }).join('');
    const lines = p.case.links.map((l) => {
      const a = ids.indexOf(l[0]), b = ids.indexOf(l[1]); if (a < 0 || b < 0) return '';
      const pa = this.pos(a), pb = this.pos(b);
      return '<line x1="' + (pa.x + 108) + '" y1="' + (pa.y + 65) + '" x2="' + (pb.x + 108) + '" y2="' + (pb.y + 65) + '"/>';
    }).join('');
    this.root.innerHTML =
      '<div class="screen diary">' + topbar(this, 'back') +
        '<h2>' + this.t('case.title') + '</h2>' +
        '<p class="info">' + (ids.length ? this.t('ui.diaryHelp') : this.t('ui.diaryEmpty')) + '</p>' +
        '<div class="diary-pad" style="height:' + Math.max(0, 60 + Math.ceil(ids.length / 4) * 145 - 588) + 'px"></div>' +
        '<svg class="links" width="1024" height="' + Math.max(768, 200 + Math.ceil(ids.length / 4) * 145) + '">' + lines + '</svg>' + cards +
      '</div>';
  }
  onInput(e) {
    const a = actionOf(e); if (!a) return;
    if (a.act === 'back') { this.app.scenes.finish({ changed: this.changed }); return; }
    if (a.act === 'clue') {
      const id = a.el.getAttribute('data-id');
      if (!this.sel) { this.sel = id; this.app.audio.sfx('tap'); }
      else if (this.sel === id) this.sel = null;
      else {
        const x = this.sel, y = id;
        this.app.progress.update((d) => {
          const i = d.case.links.findIndex((l) => (l[0] === x && l[1] === y) || (l[0] === y && l[1] === x));
          if (i >= 0) d.case.links.splice(i, 1); else d.case.links.push([x, y]);
        });
        this.changed = true; this.sel = null; this.app.audio.sfx('star');
      }
      this.draw();
    }
  }
}
