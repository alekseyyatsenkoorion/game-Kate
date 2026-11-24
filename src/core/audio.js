// Audio — синтез звуков (Web Audio) и голос (синтез речи iOS, русский) — contracts.md §5.
// Никогда не бросает исключений и не задерживает игру.
import { log } from './log.js';
import { createRng, randomSeed } from './rng.js';

const MUSIC_VOL = 1.4;
const midi = (n) => 440 * Math.pow(2, (n - 69) / 12);
// ре минор: Dm — B♭ — Gm — A (гармонический минор даёт «загадочную» доминанту)
const CHORDS = [[50, 53, 57], [46, 50, 53], [43, 46, 50], [45, 49, 52], [50, 53, 57], [46, 50, 53], [48, 52, 55], [45, 49, 52]];
const SCALE = [50, 52, 53, 55, 57, 58, 61, 62];

export class Audio {
  constructor(progress) {
    this.progress = progress;
    this.ctx = null; this.master = null; this.musicNode = null;
    this.unlocked = false; this.paused = false;
    this.voice = null;
    this.speech = typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null;
    if (this.speech) {
      const pick = () => {
        const vs = this.speech.getVoices() || [];
        this.voice = vs.find((v) => /^ru/i.test(v.lang) && /milena|милена/i.test(v.name)) || vs.find((v) => /^ru/i.test(v.lang)) || null;
      };
      pick();
      try { this.speech.addEventListener('voiceschanged', pick); } catch (e) { /* старые браузеры */ }
    }
  }
  _s() { return this.progress.settings(); }
  isMuted(ch) {
    const s = this._s();
    if (ch === 'music') return !s.music;
    if (ch === 'sfx') return !s.sfx;
    if (ch === 'voice') return !s.voice;
    return !s.music && !s.sfx && !s.voice;
  }
  setMuted(ch, on) {
    if (ch === 'all') this.progress.setSettings({ music: !on, sfx: !on, voice: !on });
    else this.progress.setSettings({ [ch]: !on });
    if (this.isMuted('music')) this.music(null); else if (this.wantMusic) this.music(this.wantMusic);
    if (this.isMuted('voice') && this.speech) this.speech.cancel();
  }
  async unlock() {
    if (this.unlocked) return;
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) {
        this.ctx = new AC();
        this.master = this.ctx.createGain(); this.master.gain.value = 0.8; this.master.connect(this.ctx.destination);
        if (this.ctx.state === 'suspended') await this.ctx.resume();
      }
      if (this.speech) { const u = new SpeechSynthesisUtterance(' '); u.volume = 0; this.speech.speak(u); }
      this.unlocked = true;
      if (this.wantMusic) this.music(this.wantMusic);
    } catch (e) { log.warn('AUDIO_UNLOCK', String(e)); }
  }

  // ---------- голос ----------
  sayText(text, opts) {
    return new Promise((resolve) => {
      if (!this.speech || !this.unlocked || this.isMuted('voice') || !text) { resolve(); return; }
      try {
        this.speech.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'ru-RU'; if (this.voice) u.voice = this.voice;
        u.pitch = (opts && opts.pitch) || 1; u.rate = (opts && opts.rate) || 1;
        let done = false; const fin = () => { if (!done) { done = true; this.duckMusic(false); resolve(); } };
        this.duckMusic(true);
        u.onend = fin; u.onerror = fin;
        setTimeout(fin, 8000);
        this.speech.speak(u);
      } catch (e) { log.warn('VOICE', String(e)); resolve(); }
    });
  }
  // Похвала — голосом ведущего
  praise(text) { this.sfx('chime'); return this.sayText(text, { pitch: 1.05, rate: 1.0 }); }
  // Злорадный смех скептика + колкость. Без голоса — синтезированный смех.
  laugh(jab) {
    if (this.speech && this.unlocked && !this.isMuted('voice')) {
      return this.sayText('Ха-ха-ха-ха! ' + (jab || ''), { pitch: 0.55, rate: 0.95 });
    }
    this.sfx('laugh');
    return Promise.resolve();
  }
  stopAll() { if (this.speech) this.speech.cancel(); this.music(null); }
  pauseAll() { this.paused = true; try { if (this.ctx) this.ctx.suspend(); if (this.speech) this.speech.cancel(); } catch (e) {} }
  resumeAll() { this.paused = false; try { if (this.ctx) this.ctx.resume(); } catch (e) {} if (this.musicNode) this.musicNode.next = 0; }

  // ---------- музыка: генеративная мистическая (Web Audio, без файлов) ----------
  // Медленные аккорды гармонического ре минора (пэд), «музыкальная шкатулка» сверху,
  // редкий низкий колокол; всё через синтезированную реверберацию. Голос приглушает музыку.
  music(id) {
    this.wantMusic = id;
    this._stopMusic();
    if (!id || !this.ctx || this.isMuted('music')) return;
    try {
      const c = this.ctx;
      const out = c.createGain(); out.gain.value = 0; out.gain.setTargetAtTime(MUSIC_VOL, c.currentTime, 2);
      const duck = c.createGain(); duck.gain.value = 1;
      const rev = c.createConvolver(); rev.buffer = this._impulse();
      const wet = c.createGain(); wet.gain.value = 0.55;
      const dry = c.createGain(); dry.gain.value = 0.6;
      const bus = c.createGain();
      bus.connect(dry); bus.connect(rev); rev.connect(wet);
      dry.connect(duck); wet.connect(duck); duck.connect(out); out.connect(this.master);
      const rng = createRng(randomSeed());
      const m = { out, duck, bus, rng, next: c.currentTime + 0.2, bar: 0, timer: 0, nodes: new Set() };
      m.timer = setInterval(() => this._schedule(m), 250);
      this.musicNode = m;
      this._schedule(m);
    } catch (e) { log.warn('MUSIC', String(e)); }
  }
  _stopMusic() {
    const m = this.musicNode; if (!m) return;
    this.musicNode = null;
    clearInterval(m.timer);
    try {
      m.out.gain.setTargetAtTime(0, this.ctx.currentTime, 0.5);
      setTimeout(() => { m.nodes.forEach((n) => { try { n.stop(); } catch (e) {} }); try { m.out.disconnect(); } catch (e) {} }, 2500);
    } catch (e) {}
  }
  _impulse() {
    if (this._imp) return this._imp;
    const c = this.ctx, len = Math.floor(c.sampleRate * 3.2), b = c.createBuffer(2, len, c.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = b.getChannelData(ch); let s = 777 + ch * 99;
      for (let i = 0; i < len; i++) { s = (s * 16807) % 2147483647; d[i] = (s / 1073741823.5 - 1) * Math.pow(1 - i / len, 2.6); }
    }
    this._imp = b; return b;
  }
  _note(m, type, freq, t, a, d, vol) {
    const c = this.ctx, o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + a + d);
    o.connect(g); g.connect(m.bus); o.start(t); o.stop(t + a + d + 0.1);
    m.nodes.add(o); o.onended = () => m.nodes.delete(o);
  }
  _schedule(m) {
    if (!this.ctx || this.paused || this.musicNode !== m) return;
    const c = this.ctx, BAR = 8;                       // аккорд держится 8 секунд
    if (m.next < c.currentTime) m.next = c.currentTime + 0.1;
    while (m.next < c.currentTime + 1.0) {
      const t = m.next, chord = CHORDS[m.bar % CHORDS.length], r = m.rng;
      // пэд: три голоса аккорда, по два слегка расстроенных генератора
      chord.forEach((n) => {
        const f = midi(n);
        this._note(m, 'triangle', f, t, 2.5, BAR, 0.05);
        this._note(m, 'sine', f * 1.003, t + 0.3, 2.5, BAR, 0.04);
      });
      this._note(m, 'sine', midi(chord[0] - 12), t, 3, BAR, 0.07);       // бас
      // шкатулка: 4–7 нот из аккорда и гаммы, неровный ритм
      const k = r.int(4, 7);
      for (let i = 0; i < k; i++) {
        const nt = t + 0.6 + r.next() * (BAR - 1.5);
        const pool = chord.map((n) => n + 24).concat(SCALE.map((n) => n + 24));
        const f = midi(r.pick(pool));
        this._note(m, 'sine', f, nt, 0.005, 1.8, 0.035);
        this._note(m, 'sine', f * 2.01, nt, 0.005, 0.6, 0.008);        // «стеклянный» обертон
      }
      // редкий колокол: неровные обертоны
      if (m.bar % 2 === 1 && r.next() < 0.7) {
        const f = midi(chord[0] - 12), bt = t + r.next() * 3;
        [1, 2.76, 5.4].forEach((h, i) => this._note(m, 'sine', f * h, bt, 0.01, 5 - i, 0.05 / (i + 1)));
      }
      m.bar++; m.next += BAR;
    }
  }
  duckMusic(on) {
    const m = this.musicNode; if (!m || !this.ctx) return;
    try { m.duck.gain.setTargetAtTime(on ? 0.35 : 1, this.ctx.currentTime, 0.3); } catch (e) {}
  }

  // ---------- звуки ----------
  sfx(id, opts) {
    if (!this.ctx || this.isMuted('sfx') || this.paused) return;
    const vol = (opts && opts.volume) || 1;
    try {
      const f = SFX[id];
      if (!f) { log.warn('SFX_' + id, 'Нет звука ' + id); return; }
      f(this.ctx, this.master, vol);
    } catch (e) { log.warn('SFX_ERR_' + id, String(e)); }
  }
}

function env(c, dest, t, a, d, peak) {
  const g = c.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(peak, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + a + d);
  g.connect(dest); return g;
}
function noise(c, dur) {
  const b = c.createBuffer(1, Math.floor(c.sampleRate * dur), c.sampleRate), d = b.getChannelData(0);
  let s = 12345; for (let i = 0; i < d.length; i++) { s = (s * 16807) % 2147483647; d[i] = s / 1073741823.5 - 1; }
  const n = c.createBufferSource(); n.buffer = b; return n;
}
function tone(c, dest, type, f, t, a, d, peak) {
  const o = c.createOscillator(); o.type = type; o.frequency.setValueAtTime(f, t);
  o.connect(env(c, dest, t, a, d, peak)); o.start(t); o.stop(t + a + d + 0.05); return o;
}

const SFX = {
  tap(c, m, v) { tone(c, m, 'sine', 660, c.currentTime, 0.005, 0.08, 0.15 * v); },
  cloth(c, m, v) {
    const t = c.currentTime, n = noise(c, 0.6), f = c.createBiquadFilter(); f.type = 'bandpass'; f.frequency.value = 1800; f.Q.value = 0.6;
    n.connect(f); f.connect(env(c, m, t, 0.12, 0.45, 0.35 * v)); n.start(t);
  },
  chime(c, m, v) {
    const t = c.currentTime; [784, 988, 1175, 1568].forEach((f, i) => tone(c, m, 'sine', f, t + i * 0.09, 0.005, 0.9, 0.18 * v));
  },
  wrong(c, m, v) { const t = c.currentTime; tone(c, m, 'triangle', 220, t, 0.01, 0.35, 0.25 * v); tone(c, m, 'triangle', 207, t + 0.15, 0.01, 0.4, 0.2 * v); },
  knock(c, m, v) {
    const t = c.currentTime; [0, 0.22, 0.38].forEach((d) => {
      const o = c.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(140, t + d); o.frequency.exponentialRampToValueAtTime(60, t + d + 0.12);
      o.connect(env(c, m, t + d, 0.003, 0.15, 0.6 * v)); o.start(t + d); o.stop(t + d + 0.2);
    });
  },
  trunk(c, m, v) { const t = c.currentTime; tone(c, m, 'square', 90, t, 0.002, 0.08, 0.2 * v); tone(c, m, 'sawtooth', 300, t + 0.05, 0.05, 0.4, 0.05 * v); },
  power(c, m, v) { const t = c.currentTime; const o = c.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(400, t); o.frequency.exponentialRampToValueAtTime(1200, t + 0.25); o.connect(env(c, m, t, 0.01, 0.3, 0.15 * v)); o.start(t); o.stop(t + 0.4); },
  star(c, m, v) { tone(c, m, 'sine', 1320, c.currentTime, 0.005, 0.5, 0.2 * v); },
  // Синтезированный «злорадный смех»: слоги «ха» с придыханием, высота падает
  laugh(c, m, v) {
    const t0 = c.currentTime;
    for (let i = 0; i < 6; i++) {
      const t = t0 + i * 0.17, f0 = 150 - i * 9;
      const h = noise(c, 0.05), hf = c.createBiquadFilter(); hf.type = 'highpass'; hf.frequency.value = 1500;
      h.connect(hf); hf.connect(env(c, m, t, 0.005, 0.05, 0.12 * v)); h.start(t);
      const o = c.createOscillator(); o.type = 'sawtooth'; o.frequency.setValueAtTime(f0 * 1.1, t + 0.03); o.frequency.linearRampToValueAtTime(f0, t + 0.13);
      const f1 = c.createBiquadFilter(); f1.type = 'bandpass'; f1.frequency.value = 750; f1.Q.value = 5;
      const f2 = c.createBiquadFilter(); f2.type = 'bandpass'; f2.frequency.value = 1150; f2.Q.value = 6;
      const g = env(c, m, t + 0.03, 0.015, 0.11, 0.5 * v);
      o.connect(f1); o.connect(f2); f1.connect(g); f2.connect(g); o.start(t + 0.03); o.stop(t + 0.2);
    }
  }
};
