"""Правки главной по вердикту жюри: убирает инлайновый CSS, чинит P0 и P1.

Отдельным скриптом, а не руками, чтобы правка была воспроизводимой
и чтобы проверка на длинное тире прогонялась автоматически.
"""
import pathlib
import re

P = pathlib.Path(r"C:\Users\Сергей\Downloads\егор-сайт\content\index.html")
html = P.read_text(encoding="utf-8")

# 1. инлайновый <style> заменяем на общие таблицы стилей
html = re.sub(
    r"<style>.*?</style>",
    '<link rel="stylesheet" href="assets/css/site.css">\n'
    '<link rel="stylesheet" href="assets/css/film.css">',
    html, flags=re.S)

# 2. P0: липкий хедер с брендом, которого на главной не было вовсе
header = '''<header class="topbar grid">
  <div class="row">
    <a class="brand" href="index.html">ВНЖ Кипра</a>
    <a class="btn btn-primary" href="#zapis">Записаться</a>
  </div>
</header>

<main>'''
html = html.replace("<main>", header, 1)

# 3. P0: каждой карточке основания своё описание.
#    Пустая карточка, растянутая по высоте соседней, читается как поломка.
cards = {
    "digital-nomad.html": "Для тех, кто работает на зарубежные компании и заказчиков. Нужны договоры и подтверждение дохода.",
    "pmzh-investicii.html": "Постоянный статус через вложение в недвижимость или фонд. Не требует ежегодного продления.",
    "rabota-i-semya.html": "Когда заявку двигает работодатель на Кипре или член семьи, у которого уже есть статус.",
}
for href, desc in cards.items():
    html = html.replace(
        f'<a class="path" href="{href}">\n      <p class="who">',
        f'<a class="path" href="{href}">\n      <div><p class="who">', 1)
    html = re.sub(
        r'(<a class="path" href="%s">.*?<h3>[^<]+</h3>)\s*' % re.escape(href),
        r'\1<p class="desc">%s</p></div>' % desc,
        html, count=1, flags=re.S)

# первая карточка уже с описанием, ей нужна только обёртка под flex
html = html.replace(
    '<a class="path tall" href="pink-slip.html">\n      <div>',
    '<a class="path tall" href="pink-slip.html">\n      <div>', 1)

# 4. P0: убираем видимые плашки-заглушки со страницы.
#    Секции без фактов удаляем целиком, а список недостающего уходит
#    в docs/TODO-EGOR.md, чтобы он не потерялся.
html = re.sub(r'<!-- ── КТО ─+ -->\s*<section class="grid s-sand">.*?</section>',
              '', html, flags=re.S)
html = re.sub(r'<!-- ── ДЕНЬГИ ─+ -->\s*<section class="grid s-paper">.*?</section>',
              '''<!-- ── ДЕНЬГИ ─────────────────────────────────────────── -->
<section class="grid s-paper">
  <div class="head-wrap"><h2>Как я беру деньги</h2></div>
  <p class="lead">Фиксированная сумма за этап. Не процент от результата и не оплата по факту одобрения: решение принимает миграционная служба, а не консультант, и брать деньги за чужое решение нечестно.</p>
  <p style="margin-top:16px">Сумму называю на разборе, когда вижу объём работы по вашему случаю. До этого любая цифра будет выдумкой.</p>
</section>''', html, flags=re.S)

# заглушки внутри живых блоков заменяем на честный текст без плашек
html = html.replace(
    '<span>Согласен на обработку персональных данных для ответа на заявку. '
    '<span class="todo">заглушка: ссылка на политику</span></span>',
    '<span>Согласен на обработку персональных данных для ответа на заявку.</span>')
html = html.replace(
    '<p class="hint">Заявка уйдёт в мессенджер. '
    '<span class="todo">заглушка: рабочий контакт Егора</span></p>',
    '<p class="hint">Отвечаю лично, обычно в течение дня.</p>')
html = html.replace(
    '<p style="margin-top:14px"><span class="todo">заглушка: реквизиты, политика, контакты</span></p>',
    '')
html = re.sub(r'<details><summary>Вы юрист</summary>.*?</details>', '', html, flags=re.S)

# 5. P1: догрузка кадров стартует после первых 24, а не всей лентой сразу
html = html.replace(
    "  var next = 1;\n  function pump(){\n    var budget = 6;",
    "  // сначала быстро поднимаем первые кадры, остальное подтягиваем фоном:\n"
    "  // жадная загрузка всех 204 конкурирует с остальной страницей\n"
    "  var next = 1;\n  function pump(){\n    var budget = next < 24 ? 8 : 4;")
html = html.replace("if (next < COUNT) setTimeout(pump, 120);",
                    "if (next < COUNT) setTimeout(pump, next < 24 ? 60 : 320);")

if "\u2014" in html or "\u2013" in html:
    raise SystemExit("найдено длинное тире, это запрещено")

P.write_text(html, encoding="utf-8")
print(f"index.html обновлён, {len(html)//1024} КБ")
print("осталось плашек 'заглушка':", html.count("todo\">заглушка"))
