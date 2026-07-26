"""Правки по второму вердикту жюри.

Главное: с экрана убирается служебный текст с именем заказчика.
Внутренние заметки команды не должны попадать в пользовательский интерфейс.
"""
import pathlib
import re

ROOT = pathlib.Path(r"C:\Users\Сергей\Downloads\егор-сайт\content")

# нейтральный экран после отправки: без служебных формулировок и без имён
DONE_BLOCK = '''<div class="form-done" id="formDone">
    <h3 style="color:#fafaf9">Заявка сформирована</h3>
    <p style="margin-top:8px">Скопируйте текст ниже и отправьте его мне в мессенджер. Так я сразу увижу вашу ситуацию и отвечу по делу.</p>
    <pre id="donePayload" style="margin-top:14px;white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:13.5px;color:rgba(250,250,249,.86)"></pre>
    <button class="btn btn-primary" type="button" id="copyBtn" style="margin-top:16px">Скопировать текст</button>
  </div>'''

BAD_PHRASES = ["Приёмник заявок", "рабочий контакт Егора", "заглушка"]

for f in sorted(ROOT.glob("*.html")):
    html = f.read_text(encoding="utf-8")

    html = re.sub(r'<div class="form-done" id="formDone">.*?</div>\s*(?=</section>)',
                  DONE_BLOCK + "\n", html, flags=re.S)

    # на мобиле десктопный кадр не используется, и браузер справедливо ругается
    html = html.replace(
        '<link rel="preload" as="image" href="assets/film/frames/f_001.webp" fetchpriority="high">',
        '<link rel="preload" as="image" href="assets/film/frames/f_001.webp" '
        'fetchpriority="high" media="(min-width: 861px)">\n'
        '<link rel="preload" as="image" href="assets/film/frames-m/f_001.webp" '
        'fetchpriority="high" media="(max-width: 860px)">')

    # знаки вопроса в FAQ: вопрос без знака вопроса читается как заголовок
    def add_q(m):
        t = m.group(1).rstrip()
        return f"<summary>{t}{'' if t.endswith('?') else '?'}</summary>"
    html = re.sub(r"<summary>([^<]+)</summary>", add_q, html)

    for bad in BAD_PHRASES:
        if bad in html:
            raise SystemExit(f"{f.name}: в интерфейсе осталась служебная фраза «{bad}»")

    f.write_text(html, encoding="utf-8")
    print(f"{f.name}: очищено")

print("Готово")
