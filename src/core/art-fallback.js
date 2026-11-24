// Рисовальщики «по умолчанию»: если нет ни картинки из ChatGPT, ни SVG.
export function fallbackDrawer(id) {
  return function (ctx, w, h) {
    const g = ctx.createRadialGradient(w / 2, h / 2, 10, w / 2, h / 2, Math.max(w, h) / 1.4);
    g.addColorStop(0, '#2a1544'); g.addColorStop(1, '#0d0716');
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = 'rgba(241,200,107,0.5)';
    ctx.font = Math.round(h / 3) + 'px Georgia'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('?', w / 2, h / 2);
  };
}
