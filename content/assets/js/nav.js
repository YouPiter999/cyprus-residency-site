/* Две вещи про шапку, обе поймало слепое жюри.

   1. Мобильная навигация. Ниже 900px ссылки прячутся, и до сегодняшнего дня
      замены им не было: страница на 11.7 тысяч пикселей листалась только
      вручную. Панель собирается ИЗ УЖЕ СУЩЕСТВУЮЩИХ ссылок страницы, а не из
      второго списка в разметке: два списка одного меню расходятся всегда.

   2. Тёмный контекст. Кремовая полупрозрачная шапка над оливковыми и чёрными
      секциями просвечивала их текстом. Класс вешается по тому, что реально
      лежит под нижней кромкой шапки, а не по номерам секций.

   Если этот файл не доедет, страница остаётся рабочей: ссылки в подвале на
   месте, шапка просто не перекрашивается. */
(function () {
  'use strict';

  var bar = document.querySelector('.topbar');
  if (!bar) return;

  // ── панель ────────────────────────────────────────────────────────────
  var row = bar.querySelector('.row');
  var cta = row.querySelector('.btn');

  function collect() {
    var panel = document.createElement('nav');
    panel.className = 'mobnav';
    panel.id = 'mobnav';
    panel.setAttribute('aria-label', 'Меню');

    // разделы текущей страницы: берём из десктопного меню, если оно есть
    var top = bar.querySelector('.topnav');
    if (top && top.children.length) {
      var h = document.createElement('h2');
      h.textContent = 'Разделы';
      panel.appendChild(h);
      Array.prototype.forEach.call(top.children, function (a) {
        panel.appendChild(a.cloneNode(true));
      });
    }
    // основания: они одинаковы на всех страницах и уже лежат в подвале
    var foot = document.querySelector('.foot-nav');
    if (foot) {
      var h2 = document.createElement('h2');
      h2.textContent = 'Основания';
      panel.appendChild(h2);
      Array.prototype.forEach.call(foot.children, function (a) {
        if (/\.html$/.test(a.getAttribute('href') || '')) {
          panel.appendChild(a.cloneNode(true));
        }
      });
    }
    return panel;
  }

  var panel = collect();
  // панели без единой ссылки быть не должно: пустое меню хуже отсутствия
  if (!panel.querySelector('a')) return;
  document.body.appendChild(panel);

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'navtoggle';
  btn.setAttribute('aria-expanded', 'false');
  btn.setAttribute('aria-controls', 'mobnav');
  btn.setAttribute('aria-label', 'Меню');
  btn.innerHTML = '<span class="bars"><span></span><span></span><span></span></span>';
  row.insertBefore(btn, cta);

  function setOpen(open) {
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    panel.classList.toggle('on', open);
    document.body.classList.toggle('nav-open', open);
    // панель начинается под шапкой, а её высота на мобиле своя
    if (open) panel.style.top = Math.round(bar.getBoundingClientRect().bottom) + 'px';
  }

  btn.addEventListener('click', function () {
    setOpen(btn.getAttribute('aria-expanded') !== 'true');
  });

  // клик по ссылке закрывает: якорь на той же странице иначе уводит под панель
  panel.addEventListener('click', function (e) {
    if (e.target.closest('a')) setOpen(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && btn.getAttribute('aria-expanded') === 'true') {
      setOpen(false);
      btn.focus();
    }
  });

  // разворот экрана шире порога не должен оставлять панель висеть
  var mq = window.matchMedia('(min-width: 901px)');
  (mq.addEventListener ? mq.addEventListener.bind(mq, 'change') : mq.addListener.bind(mq))(
    function () { if (mq.matches) setOpen(false); }
  );

  // ── тёмный контекст ───────────────────────────────────────────────────
  // Смотрим, что лежит под нижней кромкой шапки. Это надёжнее списка секций:
  // порядок и число секций меняются, а кромка всегда там же.
  var ticking = false;
  function syncContext() {
    ticking = false;
    var y = bar.getBoundingClientRect().bottom + 2;
    var x = Math.round(window.innerWidth / 2);
    var els = document.elementsFromPoint(x, y);
    var dark = false;
    for (var i = 0; i < els.length; i++) {
      if (els[i] === bar || bar.contains(els[i]) || panel.contains(els[i])) continue;
      if (els[i].closest && els[i].closest('.on-dark')) { dark = true; }
      break;
    }
    bar.classList.toggle('over-dark', dark);
  }
  function onScroll() {
    if (!ticking) { ticking = true; requestAnimationFrame(syncContext); }
  }
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', onScroll);
  syncContext();
})();
