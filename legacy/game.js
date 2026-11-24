// «Шестое чувство» — каркас: экраны, сохранение, замок по дням, режим теста.
(function () {
  'use strict';

  var KEY = 'sixth-sense-save-v1';
  var app = document.getElementById('app');
  var modal = document.getElementById('modal');
  var state = load();
  var run = null;          // текущий выпуск: { n, idx, stars: [] }
  var eyeTaps = 0, eyeTimer = null;

  // ---------- сохранение ----------
  function defaults() { return { v: 1, done: {}, power: 3, sound: true, test: false }; }
  function load() {
    try {
      var s = JSON.parse(localStorage.getItem(KEY));
      if (s && s.v === 1) return s;
    } catch (e) {}
    return defaults();
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }

  // ---------- дни и замок ----------
  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function today() { var d = new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function quota() { return new Date().getDay() === 6 ? 2 : 1; }   // суббота — два выпуска
  function doneToday() {
    var c = 0, t = today();
    for (var k in state.done) if (state.done[k].date === t) c++;
    return c;
  }
  function nextEp() {
    for (var i = 0; i < EPISODES.length; i++) if (!state.done[EPISODES[i].n]) return EPISODES[i].n;
    return null;
  }
  function status(n) {
    if (state.done[n]) return 'done';
    if (n !== nextEp()) return 'locked';
    if (state.test || doneToday() < quota()) return 'open';
    return 'wait';
  }

  // ---------- утилиты ----------
  function ep(n) { return EPISODES[n - 1]; }
  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function starStr(k) { var s = ''; for (var i = 1; i <= 3; i++) s += i <= k ? '★' : '☆'; return s; }
  function sum(a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i]; return s; }
  function avgStars(a) { return Math.round(sum(a) / a.length); }
  function trialNames(e) { return e.trials.map(function (t) { return TRIALS[t.id].name; }).join(' + '); }

  var EYE = '<svg viewBox="0 0 100 60" class="eye-svg"><path d="M5 30 Q50 -10 95 30 Q50 70 5 30Z" fill="none" stroke="currentColor" stroke-width="4"/><circle cx="50" cy="30" r="13" fill="currentColor"/><circle cx="55" cy="25" r="4" fill="#0d0716"/></svg>';
  function candles() {
    return '<div class="candles left"><i class="c c1"></i><i class="c c2"></i></div>' +
           '<div class="candles right"><i class="c c3"></i><i class="c c1"></i></div>';
  }
  function testBadge() { return state.test ? '<div class="test-badge">ТЕСТ</div>' : ''; }
  function topbar(back) {
    return '<div class="topbar">' +
      (back ? '<button class="btn small ghost" data-action="' + back + '">← Назад</button>' : '<span></span>') +
      '<div class="power">Сила: <b>' + state.power + '</b></div></div>';
  }

  // ---------- экраны ----------
  function renderTitle() {
    var started = Object.keys(state.done).length > 0;
    app.innerHTML =
      '<div class="screen title-screen">' + candles() + testBadge() +
        '<div class="eye" data-action="eye">' + EYE + '</div>' +
        '<h1>Шестое чувство</h1>' +
        '<p class="sub">мистическое шоу испытаний</p>' +
        '<div class="menu">' +
          '<button class="btn gold" data-action="season">' + (started ? 'Продолжить сезон' : 'Начать сезон') + '</button>' +
          '<button class="btn ghost" data-action="settings">Настройки</button>' +
        '</div>' +
      '</div>';
  }

  function renderSeason() {
    var cards = EPISODES.map(function (e) {
      var st = status(e.n), foot;
      if (st === 'done') foot = '<span class="stars">' + starStr(state.done[e.n].stars) + '</span>';
      else if (st === 'open') foot = '<span class="play">Играть</span>';
      else if (st === 'wait') foot = '<span class="wait">Откроется завтра</span>';
      else foot = '<span class="lock">🔒</span>';
      return '<div class="card ' + st + '"' + (st === 'open' || st === 'done' ? ' data-action="ep" data-n="' + e.n + '"' : '') + '>' +
        '<div class="num">' + e.n + '</div>' +
        '<div class="ctitle">' + esc(e.title) + '</div>' +
        '<div class="ctrial">' + esc(trialNames(e)) + '</div>' +
        '<div class="cfoot">' + foot + '</div></div>';
    }).join('');

    var finished = nextEp() === null;
    var info = finished ? 'Сезон пройден!' :
      (state.test ? 'Режим теста: замок по дням снят' :
        'Сегодня доступно выпусков: ' + Math.max(0, quota() - doneToday()) + ' из ' + quota());

    app.innerHTML =
      '<div class="screen season">' + testBadge() + topbar('title') +
        '<h2>Сезон</h2><p class="info">' + info + '</p>' +
        '<div class="grid">' + cards + '</div>' +
        (state.test ? testPanel() : '') +
      '</div>';
  }

  function testPanel() {
    return '<div class="test-panel">' +
      '<button class="btn small ghost" data-action="t-pass">Пройти текущий (★★★)</button>' +
      '<button class="btn small ghost" data-action="t-reset">Сбросить прогресс</button>' +
      '<button class="btn small ghost" data-action="t-off">Выключить режим теста</button>' +
      '</div>';
  }

  function renderIntro(n) {
    var e = ep(n), replay = !!state.done[n];
    app.innerHTML =
      '<div class="screen intro">' + candles() + testBadge() + topbar('season') +
        '<div class="ep-label">Выпуск ' + e.n + '</div>' +
        '<h2>' + esc(e.title) + '</h2>' +
        '<div class="host"><div class="host-name">Ведущий</div><p>' + esc(e.intro) + '</p></div>' +
        '<div class="trial-list">Испытание: <b>' + esc(trialNames(e)) + '</b></div>' +
        (replay ? '<p class="info">Выпуск уже пройден. Переигровка улучшит звёзды, но не даст силы.</p>' : '') +
        '<button class="btn gold" data-action="start" data-n="' + n + '">Начать испытание</button>' +
      '</div>';
  }

  function renderTrial() {
    var e = ep(run.n), t = e.trials[run.idx], tr = TRIALS[t.id];
    var part = e.trials.length > 1 ? ' · часть ' + (run.idx + 1) + ' из ' + e.trials.length : '';
    app.innerHTML =
      '<div class="screen trial">' + testBadge() + topbar('season') +
        '<div class="ep-label">Выпуск ' + e.n + part + ' · уровень ' + t.lvl + '</div>' +
        '<h2>' + esc(tr.name) + '</h2>' +
        '<p class="rules">' + esc(tr.rules) + '</p>' +
        '<div class="stage">Испытание в разработке</div>' +
        '<div class="stub">Заглушка — выберите результат:' +
          '<button class="btn small ghost" data-action="res" data-s="1">★</button>' +
          '<button class="btn small ghost" data-action="res" data-s="2">★★</button>' +
          '<button class="btn small ghost" data-action="res" data-s="3">★★★</button>' +
        '</div>' +
      '</div>';
  }

  function finishEpisode() {
    var n = run.n, st = avgStars(run.stars), prev = state.done[n], gain = 0;
    if (!prev) {
      gain = sum(run.stars);
      state.power += gain;
      state.done[n] = { date: today(), stars: st };
    } else if (st > prev.stars) {
      prev.stars = st;
    }
    save();
    renderResult(n, st, gain);
    run = null;
  }

  function renderResult(n, st, gain) {
    var e = ep(n);
    var phrase = st === 3 ? 'Невероятно. Даже скептик промолчал.' :
                 st === 2 ? 'Хороший результат. Но вы чувствовали, что могли точнее?' :
                            'Скептик доволен — а это плохой знак. Соберитесь.';
    app.innerHTML =
      '<div class="screen result">' + candles() + testBadge() +
        '<div class="ep-label">Итоги выпуска ' + e.n + '</div>' +
        '<h2>' + esc(e.title) + '</h2>' +
        '<div class="big-stars">' + starStr(st) + '</div>' +
        '<div class="host"><div class="host-name">Ведущий</div><p>' + phrase + '</p></div>' +
        (gain ? '<p class="gain">+' + gain + ' силы</p>' : '') +
        '<button class="btn gold" data-action="season">В сезон</button>' +
      '</div>';
  }

  function renderSettings() {
    app.innerHTML =
      '<div class="screen settings">' + testBadge() + topbar('title') +
        '<h2>Настройки</h2>' +
        '<div class="menu">' +
          '<button class="btn ghost" data-action="sound">Звук: ' + (state.sound ? 'включён' : 'выключен') + '</button>' +
          '<button class="btn ghost" data-action="ask-reset">Начать сезон заново</button>' +
        '</div>' +
        '<p class="info">Чтобы прогресс не потерялся, добавьте игру на экран «Домой»: Поделиться → На экран «Домой».</p>' +
      '</div>';
  }

  // ---------- модальное окно ----------
  function showModal(text, buttons) {
    modal.innerHTML = '<div class="box"><p>' + esc(text) + '</p><div class="row">' +
      buttons.map(function (b) {
        return '<button class="btn small ' + (b.gold ? 'gold' : 'ghost') + '" data-action="' + b.action + '">' + esc(b.label) + '</button>';
      }).join('') + '</div></div>';
    modal.className = '';
  }
  function hideModal() { modal.className = 'hidden'; modal.innerHTML = ''; }

  function resetProgress() {
    var test = state.test;
    state = defaults();
    state.test = test;
    save();
  }

  // ---------- действия ----------
  var actions = {
    title: renderTitle,
    season: renderSeason,
    settings: renderSettings,
    ep: function (el) { renderIntro(+el.getAttribute('data-n')); },
    start: function (el) {
      run = { n: +el.getAttribute('data-n'), idx: 0, stars: [] };
      renderTrial();
    },
    res: function (el) {
      run.stars.push(+el.getAttribute('data-s'));
      run.idx++;
      if (run.idx < ep(run.n).trials.length) renderTrial(); else finishEpisode();
    },
    sound: function () { state.sound = !state.sound; save(); renderSettings(); },
    'ask-reset': function () {
      showModal('Начать сезон заново? Весь прогресс будет потерян.', [
        { label: 'Отмена', action: 'close' },
        { label: 'Начать заново', action: 'do-reset', gold: true }
      ]);
    },
    'do-reset': function () { hideModal(); resetProgress(); renderTitle(); },
    close: hideModal,
    eye: function () {
      eyeTaps++;
      clearTimeout(eyeTimer);
      eyeTimer = setTimeout(function () { eyeTaps = 0; }, 3000);
      if (eyeTaps >= 7) {
        eyeTaps = 0;
        state.test = !state.test; save(); renderTitle();
        showModal(state.test ? 'Режим теста включён' : 'Режим теста выключен', [{ label: 'OK', action: 'close', gold: true }]);
      }
    },
    't-pass': function () {
      var n = nextEp();
      if (!n) return;
      state.done[n] = { date: today(), stars: 3 };
      state.power += 3 * ep(n).trials.length;
      save(); renderSeason();
    },
    't-reset': function () { resetProgress(); renderSeason(); },
    't-off': function () { state.test = false; save(); renderSeason(); }
  };

  function onTap(ev) {
    var el = ev.target.closest('[data-action]');
    if (!el) return;
    var fn = actions[el.getAttribute('data-action')];
    if (fn) fn(el);
  }
  app.addEventListener('click', onTap);
  modal.addEventListener('click', onTap);

  renderTitle();
})();
