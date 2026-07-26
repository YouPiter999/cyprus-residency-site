"""Собирает самодостаточную версию сайта одним HTML-файлом для просмотра и отправки.

Артефакт не может тянуть внешние ресурсы, поэтому всё вшивается data-URI:
шрифты, GSAP, кадры сцены. Кадры пережимаются: полная лента на 134 кадра
в base64 весила бы больше трёх мегабайт.
"""
import base64
import io
import pathlib
import re

from PIL import Image

ROOT = pathlib.Path(r"C:\Users\Сергей\Downloads\егор-сайт\content")
OUT = ROOT / "share" / "vnzh-kipra-preview.html"

SHARE_FRAMES = 40          # из 134: на глаз разница невелика, вес втрое меньше
FRAME_W, FRAME_H = 800, 334
FRAME_Q = 42


def b64(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def build_frames() -> list[str]:
    files = sorted((ROOT / "assets/film/frames").glob("f_*.avif"))
    step = (len(files) - 1) / (SHARE_FRAMES - 1)
    out = []
    for k in range(SHARE_FRAMES):
        im = Image.open(files[round(k * step)]).convert("RGB")
        im = im.resize((FRAME_W, FRAME_H), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=FRAME_Q, method=6)
        out.append(b64(buf.getvalue(), "image/webp"))
    return out


def inline_fonts() -> str:
    """Только кириллические и латинские подмножества нужных начертаний."""
    want = [("Onest", 700, "onest-700-5.woff2"), ("Onest", 700, "onest-700-6.woff2"),
            ("Onest", 600, "onest-600-2.woff2"), ("Onest", 600, "onest-600-3.woff2"),
            ("Manrope", 400, "manrope-400-2.woff2"), ("Manrope", 400, "manrope-400-3.woff2"),
            ("Manrope", 600, "manrope-600-8.woff2"), ("Manrope", 600, "manrope-600-9.woff2")]
    css = []
    for fam, w, name in want:
        p = ROOT / "assets/fonts" / name
        if not p.exists():
            continue
        css.append("@font-face{font-family:'%s';font-weight:%d;font-style:normal;"
                   "font-display:swap;src:url(%s) format('woff2')}"
                   % (fam, w, b64(p.read_bytes(), "font/woff2")))
    return "\n".join(css)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    # CSS внутрь, ссылки на файлы убираем
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    css += "\n" + (ROOT / "assets/css/film.css").read_text(encoding="utf-8")
    css = re.sub(r"@font-face\{[^}]+\}", "", css)          # свои @font-face выкидываем
    css = inline_fonts() + "\n" + css
    html = re.sub(r'<link rel="stylesheet"[^>]*>', "", html)
    html = re.sub(r'<link rel="preload"[^>]*>', "", html)
    html = html.replace("</head>", f"<style>{css}</style>\n</head>")

    # GSAP внутрь
    js = ""
    for name in ("gsap.min.js", "ScrollTrigger.min.js"):
        js += (ROOT / "assets/js" / name).read_text(encoding="utf-8") + "\n"
    html = re.sub(r'<script src="assets/js/(gsap|ScrollTrigger)\.min\.js"></script>', "", html)
    html = html.replace("<script src=\"assets/js/form.js\"></script>",
                        "<script>%s</script>" % (ROOT / "assets/js/form.js").read_text(encoding="utf-8"))
    html = html.replace("</head>", f"<script>{js}</script>\n</head>")

    # кадры внутрь: подменяем загрузчик на массив data-URI
    frames = build_frames()
    arr = "window.__FRAMES=[" + ",".join('"%s"' % f for f in frames) + "];"
    html = html.replace("</head>", f"<script>{arr}</script>\n</head>")
    html = html.replace(
        "  var DIR = MOB ? 'assets/film/frames-m/' : 'assets/film/frames/';\n"
        "  var COUNT = MOB ? 45 : 134;",
        "  var COUNT = window.__FRAMES.length;")
    html = html.replace(
        "  function src(i){ return DIR + 'f_' + String(i+1).padStart(3,'0') + '.avif'; }",
        "  function src(i){ return window.__FRAMES[i]; }")
    html = html.replace("var CW = MOB ? 600 : 960, CH = MOB ? 750 : 400;",
                        "var CW = %d, CH = %d;" % (FRAME_W, FRAME_H))
    html = html.replace('<canvas id="seq" width="960" height="400"',
                        '<canvas id="seq" width="%d" height="%d"' % (FRAME_W, FRAME_H))

    # ссылки на подстраницы в одностраничной версии никуда не ведут
    html = re.sub(r'<a class="path( tall)?" href="[^"]+\.html">', r'<div class="path\1">', html)
    html = html.replace("</a>\n  </div>\n\n  <p style=\"margin-top:26px", "</div>\n  </div>\n\n  <p style=\"margin-top:26px")
    html = re.sub(r'(<div class="path[^"]*">.*?)</a>', r"\1</div>", html, flags=re.S)
    html = html.replace('<span class="go">Как это работает</span>',
                        '<span class="go">Отдельная страница в полной версии</span>')
    html = re.sub(r'<nav class="foot-nav".*?</nav>', "", html, flags=re.S)
    html = html.replace('<a class="brand" href="index.html">', '<span class="brand">')
    html = html.replace("ВНЖ Кипра</a>\n    <a class=\"btn btn-primary\" href=\"#zapis\">",
                        "ВНЖ Кипра</span>\n    <a class=\"btn btn-primary\" href=\"#zapis\">")

    # мобильной вертикальной ленты в этой версии нет, кадры одни на всё
    html = html.replace("var MOB = lowEnd || innerWidth < 860;", "var MOB = false;")

    OUT.write_text(html, encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"{OUT}\n{kb:.0f} КБ, кадров {len(frames)}")
    if "assets/" in html:
        left = set(re.findall(r'assets/[\w./-]+', html))
        print("ОСТАЛИСЬ ВНЕШНИЕ ССЫЛКИ:", left)


if __name__ == "__main__":
    main()
