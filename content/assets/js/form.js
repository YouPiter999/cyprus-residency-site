/* Форма заявки: валидация, состояния, сборка текста обращения.
   Рабочий контакт Егора подставляется одной строкой в TARGET, всё остальное готово. */
(function(){
  'use strict';
  var form = document.getElementById('leadForm');
  if (!form) return;
  var done = document.getElementById('formDone');
  var TARGET = null;   // например 'https://t.me/username?text='

  function focusFirstInvalid(){
    var bad = document.querySelector('[aria-invalid="true"]');
    if (bad){ bad.focus({preventScroll:true}); bad.scrollIntoView({block:'center'}); }
  }

  form.addEventListener('submit', function(e){
    e.preventDefault();
    var name = document.getElementById('name');
    var contact = document.getElementById('contact');
    var about = document.getElementById('about');
    var consent = document.getElementById('consent');
    var ok = true;

    function mark(el, errId, bad){
      var err = document.getElementById(errId);
      if (err) err.classList.toggle('on', bad);
      el.setAttribute('aria-invalid', bad ? 'true' : 'false');
      if (bad) ok = false;
    }
    mark(name, 'errName', name.value.trim().length < 2);
    mark(contact, 'errContact', contact.value.trim().length < 3);
    mark(consent, 'errConsent', !consent.checked);

    // фокус уводим на первое невалидное поле: иначе он остаётся на кнопке
    // и человек с клавиатуры не понимает, куда его отправили
    if (!ok){ focusFirstInvalid(); return; }

    var text = 'Заявка на разбор ситуации\n'
             + 'Основание: ' + (document.title.split(':')[0]) + '\n'
             + 'Имя: ' + name.value.trim() + '\n'
             + 'Связь: ' + contact.value.trim() + '\n'
             + 'Ситуация: ' + (about.value.trim() || 'не указана');

    if (TARGET){ location.href = TARGET + encodeURIComponent(text); return; }

    form.style.display = 'none';
    done.classList.add('on');
    var pre = document.getElementById('donePayload');
    if (pre) pre.textContent = text;
    done.scrollIntoView({block:'center'});

    var copy = document.getElementById('copyBtn');
    if (copy){
      copy.addEventListener('click', function(){
        navigator.clipboard.writeText(text).then(function(){
          copy.textContent = 'Скопировано';
        }, function(){
          // буфер может быть недоступен без https: выделяем текст руками
          var r = document.createRange();
          r.selectNodeContents(pre);
          var s = getSelection(); s.removeAllRanges(); s.addRange(r);
          copy.textContent = 'Выделено, нажмите Ctrl+C';
        });
      });
    }
  });
})();
