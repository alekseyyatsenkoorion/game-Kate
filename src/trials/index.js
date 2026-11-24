// Реестр испытаний (contracts.md §11.5): тип → модуль.
import { Shirma } from './shirma/shirma.js';
import { Bagazhnik } from './bagazhnik/bagazhnik.js';
import { MisterX } from './misterx/misterx.js';
import { Komnata } from './komnata/komnata.js';
import { Foto } from './foto/foto.js';

export const TRIALS = { shirma: Shirma, bagazhnik: Bagazhnik, misterx: MisterX, komnata: Komnata, foto: Foto };
