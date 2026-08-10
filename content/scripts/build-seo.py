"""Пишет robots.txt, sitemap.xml и llms.txt и проверяет, что пять страниц
согласованы между собой.

Запускать ПОСЛЕ build-pages.py. Скрипт ничего не выдумывает: заголовки и
описания страниц он берёт из того же PAGES, из которого собраны сами
страницы, а режим индексации из siteinfo.PUBLISHED.

Что он ловит (каждый пункт это реальная ошибка из соседних проектов):
- страница без canonical или с чужим canonical;
- og:url, разъехавшийся с canonical;
- страница, у которой meta robots не совпадает с общим переключателем;
- карта сайта, оставшаяся от закрытого сайта, или её отсутствие у открытого.
"""
import datetime
import importlib.util
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import siteinfo  # noqa: E402

ROOT = siteinfo.ROOT


def load_pages():
    """PAGES живут в build-pages.py, дефис в имени не даёт обычного импорта."""
    path = pathlib.Path(__file__).resolve().parent / "build-pages.py"
    spec = importlib.util.spec_from_file_location("build_pages", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PAGES


PAGES = load_pages()

HOME = {
    "slug": "",
    "title": "ВНЖ Кипра: разбор ситуации и сопровождение до карты резидента",
    "desc": "Помогаю получить вид на жительство Республики Кипр: разбираю "
            "ситуацию, подбираю основание, собираю документы и веду до решения "
            "миграционной службы.",
    "h1": "Главная",
}

ALL = [HOME] + PAGES


# ─────────────────────────────────────────────── файлы

def file_for(slug):
    return ROOT / ("index.html" if slug == "" else f"{slug}.html")


def lastmod(slug):
    ts = file_for(slug).stat().st_mtime
    return datetime.date.fromtimestamp(ts).isoformat()


def write_robots():
    if siteinfo.PUBLISHED:
        body = (
            "# Сайт открыт. Режимом управляет PUBLISHED в scripts/siteinfo.py,\n"
            "# этот файл переписывается скриптом scripts/build-seo.py.\n"
            "#\n"
            "# ВАЖНО: на GitHub Pages в подпапке robots.txt не работает вовсе.\n"
            "# Он читается только с корня домена, а сайт лежит в подкаталоге.\n"
            "# Настоящий замок это meta robots на каждой странице. Файл здесь\n"
            "# на случай переезда на свой домен, где он заработает.\n"
            "User-agent: *\n"
            "Allow: /\n"
            "\n"
            f"Sitemap: {siteinfo.BASE_URL}sitemap.xml\n"
        )
    else:
        body = (
            "# Сайт ещё не запущен: нет контактов, статуса консультанта и цен.\n"
            "# Индексировать нечего, а полуготовая страница в выдаче хуже её\n"
            "# отсутствия.\n"
            "#\n"
            "# Открывается ОДНИМ переключателем PUBLISHED в scripts/siteinfo.py,\n"
            "# после него прогнать build-pages.py и build-seo.py. Руками этот\n"
            "# файл не править: он переписывается сборкой.\n"
            "User-agent: *\n"
            "Disallow: /\n"
        )
    (ROOT / "robots.txt").write_text(body, encoding="utf-8")


def write_sitemap():
    path = ROOT / "sitemap.xml"
    if not siteinfo.PUBLISHED:
        if path.exists():
            path.unlink()
            return "удалена (сайт закрыт)"
        return "не нужна (сайт закрыт)"
    urls = []
    for p in ALL:
        prio = "1.0" if p["slug"] == "" else "0.8"
        urls.append(
            "  <url>\n"
            f"    <loc>{siteinfo.canonical(p['slug'])}</loc>\n"
            f"    <lastmod>{lastmod(p['slug'])}</lastmod>\n"
            f"    <priority>{prio}</priority>\n"
            "  </url>"
        )
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls) + "\n</urlset>\n")
    path.write_text(body, encoding="utf-8")
    return f"{len(urls)} адресов"


def write_llms():
    """Короткая карта сайта для ИИ-поиска.

    Смысл тот же, что у sitemap, но для читателя-модели: чем сайт является,
    какие у него разделы и где первоисточник. Пока сайт закрыт, файла нет:
    приглашать краулеров на недоделанную страницу незачем.
    """
    path = ROOT / "llms.txt"
    if not siteinfo.PUBLISHED:
        if path.exists():
            path.unlink()
            return "удалён (сайт закрыт)"
        return "не нужен (сайт закрыт)"

    lines = [
        f"# {siteinfo.SITE_NAME}",
        "",
        "> Сопровождение при получении вида на жительство Республики Кипр "
        "(южный Кипр, ЕС). Разбор ситуации, подбор основания, сбор и проверка "
        "документов, сопровождение на подаче.",
        "",
        "Сайт не публикует конкретные пороги дохода, суммы инвестиций и сроки "
        "рассмотрения. Они меняются и зависят от состава семьи, поэтому вместо "
        "своей цифры каждая страница ведёт на официальный портал Республики "
        "Кипр. Ссылки ниже.",
        "",
        "## Основания для ВНЖ",
        "",
    ]
    for p in PAGES:
        lines.append(f"- [{p['h1']}]({siteinfo.canonical(p['slug'])}): {p['desc']}")
    lines += [
        "",
        "## Первоисточники",
        "",
        f"- [Migration Department Республики Кипр]({siteinfo.MD_HUB})",
    ]
    seen = set()
    for p in PAGES:
        for url, title in siteinfo.OFFICIAL.get(p["slug"], []):
            if url not in seen:
                seen.add(url)
                lines.append(f"- [{title}]({url})")
    lines += [
        "",
        "## Оговорка",
        "",
        "Информация на сайте носит справочный характер и не является "
        "юридической консультацией. Решение принимает миграционная служба "
        "Республики Кипр.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return f"{len(PAGES) + 1} разделов"


# ─────────────────────────────────────────────── синхронизация и проверки

ROBOTS_RE = re.compile(r'<meta name="robots" content="[^"]*">')

FAQ_START = ("<!-- FAQ-JSONLD-START. Собирается scripts/build-seo.py из ВИДИМОГО\n"
             "     блока вопросов ниже. Руками не править: перезапишется. -->")
FAQ_END = "<!-- FAQ-JSONLD-END -->"
FAQ_BLOCK_RE = re.compile(
    re.escape("<!-- FAQ-JSONLD-START") + r".*?" + re.escape(FAQ_END), re.S)
# видимый вопрос и ответ: <details><summary>В</summary><p>О</p></details>
FAQ_ITEM_RE = re.compile(
    r"<details><summary>(.*?)</summary><p>(.*?)</p></details>", re.S)


def sync_index_faq():
    """Разметка FAQ главной собирается из видимого блока, а не пишется рядом.

    У подстраниц эта проблема решена генератором: там и текст, и FAQPage
    берутся из одного списка. У главной блок свёрстан руками, и рядом лежала
    отдельная копия тех же вопросов в JSON. Две копии одного текста расходятся
    всегда, а разметка, обещающая не то, что видит человек, это клоакинг.
    """
    import json
    path = ROOT / "index.html"
    html = path.read_text(encoding="utf-8")

    faq_div = re.search(r'<div class="faq">(.*?)</div>', html, re.S)
    if not faq_div:
        raise SystemExit("index.html: не найден видимый блок <div class=\"faq\">")
    items = FAQ_ITEM_RE.findall(faq_div.group(1))
    if not items:
        raise SystemExit("index.html: в блоке FAQ не разобран ни один вопрос")

    node = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": re.sub(r"<[^>]+>", "", q).strip(),
             "acceptedAnswer": {"@type": "Answer",
                                "text": re.sub(r"<[^>]+>", "", a).strip()}}
            for q, a in items
        ],
    }
    block = (FAQ_START + '\n<script type="application/ld+json">'
             + json.dumps(node, ensure_ascii=False) + "</script>\n" + FAQ_END)

    if not FAQ_BLOCK_RE.search(html):
        raise SystemExit(
            "index.html: нет меток FAQ-JSONLD-START/END вокруг разметки FAQ. "
            "Оберните ими блок <script type=\"application/ld+json\"> с FAQPage.")
    new = FAQ_BLOCK_RE.sub(lambda m: block, html, count=1)
    if new != html:
        path.write_text(new, encoding="utf-8")
        return f"пересобран из {len(items)} видимых вопросов"
    return f"уже совпадает, {len(items)} вопросов"


def sync_index_robots():
    """index.html пишется руками, поэтому переключатель доносим сюда сами.

    Подстраницы НЕ трогаем: их владелец build-pages.py, и правка выхлопа
    генератора возвращается при первой же пересборке. Их только проверяем.
    """
    path = ROOT / "index.html"
    html = path.read_text(encoding="utf-8")
    want = siteinfo.robots_meta()
    new, n = ROBOTS_RE.subn(want, html)
    if n != 1:
        raise SystemExit(f"index.html: ожидался один meta robots, найдено {n}")
    if new != html:
        path.write_text(new, encoding="utf-8")
        return "обновлён"
    return "уже верный"


def check():
    problems = []
    want_robots = siteinfo.robots_meta()
    for p in ALL:
        name = file_for(p["slug"]).name
        html = file_for(p["slug"]).read_text(encoding="utf-8")
        canon = siteinfo.canonical(p["slug"])

        if want_robots not in html:
            problems.append(
                f"{name}: meta robots не совпадает с PUBLISHED. "
                f"Прогоните build-pages.py")
        found = re.findall(r'<link rel="canonical" href="([^"]+)">', html)
        if found != [canon]:
            problems.append(f"{name}: canonical {found or 'отсутствует'}, "
                            f"ожидался [{canon}]")
        og = re.findall(r'<meta property="og:url" content="([^"]+)">', html)
        if og != [canon]:
            problems.append(f"{name}: og:url {og or 'отсутствует'} "
                            f"разъехался с canonical")
        n_h1 = html.count("<h1")
        if n_h1 != 1:
            problems.append(f"{name}: h1 должен быть ровно один, найдено {n_h1}")
        n_faq = html.count('"FAQPage"')
        if n_faq != 1:
            problems.append(f"{name}: FAQPage должен быть ровно один, "
                            f"найдено {n_faq}")

        # Разметка обязана обещать ровно то, что видит человек. Считаем
        # видимые вопросы и вопросы в JSON-LD: расхождение это клоакинг,
        # причём такой, который никто не заметит глазами.
        faq_div = re.search(r'<div class="faq">(.*?)</div>', html, re.S)
        visible = len(FAQ_ITEM_RE.findall(faq_div.group(1))) if faq_div else 0
        in_schema = html.count('"@type": "Question"')
        if visible != in_schema:
            problems.append(f"{name}: видимых вопросов {visible}, "
                            f"в разметке {in_schema}")

    og_file = ROOT / siteinfo.OG_IMAGE
    if not og_file.exists():
        problems.append(f"{siteinfo.OG_IMAGE} не собран: превью в мессенджерах "
                        f"будет пустым")

    # согласованность замка: половина закрытого сайта хуже, чем обе половины
    robots_txt = (ROOT / "robots.txt").read_text(encoding="utf-8")
    closed_txt = "Disallow: /" in robots_txt
    if siteinfo.PUBLISHED and closed_txt:
        problems.append("robots.txt всё ещё закрывает сайт при PUBLISHED=True")
    if not siteinfo.PUBLISHED and not closed_txt:
        problems.append("robots.txt открыт при PUBLISHED=False")
    if siteinfo.PUBLISHED and not (ROOT / "sitemap.xml").exists():
        problems.append("сайт открыт, а карты сайта нет")
    return problems


def main():
    write_robots()
    print("robots.txt   переписан")
    print(f"sitemap.xml  {write_sitemap()}")
    print(f"llms.txt     {write_llms()}")
    print(f"index.html   meta robots {sync_index_robots()}")
    print(f"index.html   FAQ-разметка {sync_index_faq()}")

    problems = check()
    if problems:
        print("\nНАЙДЕНЫ РАСХОЖДЕНИЯ:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)
    mode = "ОТКРЫТ" if siteinfo.PUBLISHED else "закрыт"
    print(f"\nПроверка пройдена. Сайт {mode} для поисковиков, "
          f"все {len(ALL)} страниц согласованы.")


if __name__ == "__main__":
    main()
