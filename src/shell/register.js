// Регистрация сцен оболочки (зона D).
import { TitleScene } from './title.js';
import { SeasonScene } from './season.js';
import { IntroScene } from './intro.js';
import { ResultScene } from './result.js';
import { DiaryScene } from './diary.js';
import { SettingsScene } from './settings.js';

export function registerShell(scenes) {
  [TitleScene, SeasonScene, IntroScene, ResultScene, DiaryScene, SettingsScene].forEach((s) => scenes.register(s));
}
