// Лог: каждое предупреждение — один раз на ключ. Хранит последние 100 записей для debug.
const seen = new Set();
const entries = [];

function push(level, key, msg, details) {
  entries.push({ level, key, msg, t: Date.now() });
  if (entries.length > 100) entries.shift();
  const fn = level === 'error' ? console.error : console.warn;
  fn('[s6]', key, msg, details || '');
}

export const log = {
  warn(key, msg, details) { if (seen.has(key)) return; seen.add(key); push('warn', key, msg, details); },
  error(key, msg, details) { push('error', key, msg, details); },
  entries() { return entries.slice(); }
};

export function gameError(code, module, message, details) {
  const e = new Error(message);
  e.code = code; e.module = module; e.details = details;
  return e;
}
