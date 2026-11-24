// Input: касания → InputEvent в координатах сцены 1024×768. Только первый палец.
export class Input {
  constructor(stage) {
    this.stage = stage;
    this.fns = new Set();
    this.enabled = true;
    this.pid = null;
    this.start = null;
    this.dragging = false;
    this.holdTimer = 0;
    this.holdFired = false;
    stage.addEventListener('pointerdown', (e) => this.down(e));
    window.addEventListener('pointermove', (e) => this.move(e));
    window.addEventListener('pointerup', (e) => this.up(e));
    window.addEventListener('pointercancel', (e) => this.up(e, true));
    stage.addEventListener('contextmenu', (e) => e.preventDefault());
    document.addEventListener('gesturestart', (e) => e.preventDefault());
    document.addEventListener('dblclick', (e) => e.preventDefault());
  }
  onEvent(fn) { this.fns.add(fn); return () => this.fns.delete(fn); }
  setEnabled(on) { this.enabled = on; if (!on) this.reset(); }
  toStage(cx, cy) {
    const r = this.stage.getBoundingClientRect();
    return { x: (cx - r.left) * 1024 / r.width, y: (cy - r.top) * 768 / r.height };
  }
  emit(action, e, target) {
    if (!this.enabled) return;
    const p = this.toStage(e.clientX, e.clientY);
    const ev = { action, x: p.x, y: p.y, target: target || null, t: performance.now() };
    this.fns.forEach((fn) => fn(ev));
  }
  reset() { clearTimeout(this.holdTimer); this.pid = null; this.start = null; this.dragging = false; this.holdFired = false; }
  down(e) {
    if (this.pid !== null) return;           // второй палец игнорируется
    this.pid = e.pointerId;
    this.start = { x: e.clientX, y: e.clientY, t: performance.now(), target: e.target };
    this.dragging = false; this.holdFired = false;
    clearTimeout(this.holdTimer);
    this.holdTimer = setTimeout(() => {
      if (this.start && !this.dragging) { this.holdFired = true; this.emit('hold', e, this.start.target); }
    }, 500);
  }
  move(e) {
    if (e.pointerId !== this.pid || !this.start) return;
    const dx = e.clientX - this.start.x, dy = e.clientY - this.start.y;
    if (!this.dragging && dx * dx + dy * dy > 100) {
      this.dragging = true; clearTimeout(this.holdTimer);
      this.emit('drag-start', this.start, this.start.target);
    }
    if (this.dragging) this.emit('drag', e, this.start.target);
  }
  up(e, cancel) {
    if (e.pointerId !== this.pid || !this.start) return;
    clearTimeout(this.holdTimer);
    const quick = performance.now() - this.start.t < 300;
    if (this.dragging) this.emit('drag-end', e, this.start.target);
    else if (!cancel && !this.holdFired && quick) this.emit('tap', e, this.start.target);
    else if (!cancel && !this.holdFired) this.emit('tap', e, this.start.target); // медленный тык тоже тык
    this.reset();
  }
}
