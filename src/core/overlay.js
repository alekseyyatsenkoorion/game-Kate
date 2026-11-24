// Наложения поверх сцен: субтитры реплик, модальное подтверждение, баннер обновления.
let layer = null;
export function initOverlay(stage) {
  layer = document.createElement('div');
  layer.className = 'overlay-layer';
  stage.appendChild(layer);
}

let subTimer = 0;
export function subtitle(who, text, color) {
  if (!layer) return;
  let el = layer.querySelector('.subtitle');
  if (!el) { el = document.createElement('div'); el.className = 'subtitle'; layer.appendChild(el); }
  el.innerHTML = '';
  const w = document.createElement('div'); w.className = 'sub-who'; w.textContent = who; if (color) w.style.color = color;
  const t = document.createElement('div'); t.className = 'sub-text'; t.textContent = text;
  el.appendChild(w); el.appendChild(t);
  el.classList.add('show');
  clearTimeout(subTimer);
  subTimer = setTimeout(() => el.classList.remove('show'), Math.max(2500, text.length * 70));
}

export function confirmBox(text, okLabel, cancelLabel) {
  return new Promise((resolve) => {
    const m = document.createElement('div'); m.className = 'modal';
    const box = document.createElement('div'); box.className = 'box';
    const p = document.createElement('p'); p.textContent = text; box.appendChild(p);
    const row = document.createElement('div'); row.className = 'row';
    const mk = (label, val, gold) => {
      if (!label) return;
      const b = document.createElement('button'); b.className = 'btn small ' + (gold ? 'gold' : 'ghost'); b.textContent = label;
      b.addEventListener('click', () => { m.remove(); resolve(val); });
      row.appendChild(b);
    };
    mk(cancelLabel, false, false); mk(okLabel, true, true);
    box.appendChild(row); m.appendChild(box); layer.appendChild(m);
  });
}

export function banner(text, label, onTap) {
  if (!layer || layer.querySelector('.banner')) return;
  const b = document.createElement('div'); b.className = 'banner';
  const s = document.createElement('span'); s.textContent = text;
  const btn = document.createElement('button'); btn.className = 'btn small gold'; btn.textContent = label;
  btn.addEventListener('click', () => { if (onTap() !== false) b.remove(); });
  b.appendChild(s); b.appendChild(btn); layer.appendChild(b);
}
export function hideBanner() { const b = layer && layer.querySelector('.banner'); if (b) b.remove(); }
