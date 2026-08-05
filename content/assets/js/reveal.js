/* Появление блоков при скролле.

   Зачем: после кино-сцены движение на странице исчезало полностью, и нижние
   восемь экранов читались как другой сайт. Хореография намеренно сдержанная:
   14px подъёма и прозрачность, без масштаба, поворота и параллакса. Волна идёт
   по соседям внутри группы, а не по всей странице, иначе низ страницы ползёт
   слишком долго.

   Начальное скрытое состояние включает класс на <html>, который ставится
   встроенным скриптом в <head>. Тот же скрипт снимает класс по таймауту, если
   этот файл не загрузился: страница без анимации нормальна, страница из
   невидимого текста нет. */
(function () {
  'use strict';

  var root = document.documentElement;

  // движение отключено в системе: показываем всё сразу и уходим
  if (matchMedia('(prefers-reduced-motion: reduce)').matches ||
      !('IntersectionObserver' in window)) {
    root.className = root.className.replace(' js-reveal', '');
    return;
  }

  // кино-сцена и шапка живут по своим правилам, их не трогаем
  var SEL = [
    '.head-wrap', '.path', '.step', '.honest > div', '.reqs > div',
    '.aside-card', '.sheet', '.other a', '.faq', '.docs'
  ].join(',');

  var nodes = Array.prototype.slice.call(document.querySelectorAll(SEL))
    .filter(function (n) { return !n.closest('#film') && !n.closest('.topbar'); });

  if (!nodes.length) {
    root.className = root.className.replace(' js-reveal', '');
    return;
  }

  // индекс считается среди соседей с тем же родителем: четыре карточки в ряд
  // должны выходить волной, а идущие следом заголовки начинать отсчёт заново
  var seen = new Map();
  nodes.forEach(function (n) {
    n.setAttribute('data-rv', '');
    var k = n.parentNode;
    var i = seen.get(k) || 0;
    n.style.setProperty('--rv-i', Math.min(i, 5));
    seen.set(k, i + 1);
  });

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add('in');
      io.unobserve(e.target);   // одноразово: повтор при обратном скролле мельтешит
    });
  }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });

  nodes.forEach(function (n) { io.observe(n); });

  root.dataset.rvOk = '1';   // сигнал сторожевому таймауту в <head>
})();
