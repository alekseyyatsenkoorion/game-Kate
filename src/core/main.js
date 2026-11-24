// Точка входа: собирает модули, регистрирует сцены, крутит цикл кадров.
import { log } from './log.js';
import { Input } from './input.js';
import { SceneManager } from './scene-manager.js';
import { Progress } from './progress.js';
import { DayLock } from './daylock.js';
import { ContentLoader } from './content-loader.js';
import { AssetLoader } from './asset-loader.js';
import { Audio } from './audio.js';
import { Scoring } from './scoring.js';
import { Updater } from './updater.js';
import { TrialHost } from './trial-host.js';
import { DebugScene, ErrorScene } from './debug-scene.js';
import { initOverlay, banner, hideBanner } from './overlay.js';
import { registerShell } from '../shell/register.js';

async function boot() {
  const stage = document.getElementById('stage');
  const host = document.getElementById('scene-host');
  initOverlay(stage);
  fit(stage);
  window.addEventListener('resize', () => fit(stage));

  const app = { debug: false };
  app.input = new Input(stage);
  app.scenes = new SceneManager(app, host);
  app.updater = new Updater();
  app.scenes.register(ErrorScene);

  app.content = new ContentLoader(null);
  try { await app.content.init(); }
  catch (e) { log.error(e.code || 'BOOT', e.message); await app.scenes.replace('error', { code: e.code || 'BOOT', from: 'boot' }); return; }

  app.progress = new Progress(app.content.balance(), app.content.characters());
  app.content.setProgress(app.progress);
  app.dayLock = new DayLock(app.progress, app.content.balance(), app.content.episodes().length);
  app.assets = new AssetLoader(); await app.assets.init();
  app.audio = new Audio(app.progress);
  app.scoring = new Scoring(app.content);
  Object.defineProperty(app, 'debug', { get: () => app.progress.settings().test });

  app.scenes.register(TrialHost);
  app.scenes.register(DebugScene);
  registerShell(app.scenes);

  app.input.onEvent((e) => {
    if (!app.audio.unlocked) app.audio.unlock().then(() => app.audio.music('ambient'));
    app.scenes.input(e);
  });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { app.scenes.pause(); app.audio.pauseAll(); } else { app.scenes.resume(); app.audio.resumeAll(); }
  });

  // Баннер обновления — только на заставке и карте сезона (contracts.md §10); в испытании не мешает.
  const showBanner = () => {
    const id = app.scenes.current().id;
    if (!app.updater.ready || (id !== 'title' && id !== 'season')) { hideBanner(); return; }
    banner(app.content.text('ui.updateReady'), app.content.text('ui.updateApply'), () => app.updater.applyNow(app.scenes.current().id));
  };
  app.updater.onReady(showBanner);
  app.scenes.onChange(showBanner);
  app.updater.register();

  // цикл кадров
  let last = performance.now();
  const loop = (t) => {
    const dt = Math.min(100, t - last); last = t;
    app.scenes.update(dt); app.scenes.render();
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);

  window.__s6 = app;                                   // для автотестов и отладки
  const run = app.progress.run();
  await app.scenes.replace('title', run ? { resume: run.n } : {});
}

function fit(stage) {
  const k = Math.min(window.innerWidth / 1024, window.innerHeight / 768);
  stage.style.transform = 'translate(-50%, -50%) scale(' + k + ')';
}

window.addEventListener('error', (e) => log.error('WINDOW', String(e.message)));
window.addEventListener('unhandledrejection', (e) => log.error('PROMISE', String(e.reason)));
boot();
