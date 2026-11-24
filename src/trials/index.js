// Реестр испытаний (contracts.md §11.5): тип → модуль.
import { Shirma } from './shirma/shirma.js';
import { Bagazhnik } from './bagazhnik/bagazhnik.js';

export const TRIALS = { shirma: Shirma, bagazhnik: Bagazhnik };
