"""Единственный источник правды по адресам, запуску и первоисточникам.

Читают его И build-pages.py (штампует подстраницы), И build-seo.py (пишет
robots.txt, sitemap.xml, llms.txt и синхронизирует meta robots во всех пяти
файлах). Пока значение живёт в одном месте, разойтись слоям негде.

Зачем так. В STATE.md висело предупреждение «снимать noindex и Disallow
разом, иначе один останется и закроет сайт». Это ровно тот класс ошибки,
который лечится не памятью, а одним переключателем: PUBLISHED ниже.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────────────────
# ПЕРЕКЛЮЧАТЕЛЬ ЗАПУСКА. Один на весь сайт.
#
# False — сайт закрыт: noindex на всех страницах, Disallow в robots.txt,
#         sitemap.xml и llms.txt не существуют (нечего предлагать краулеру).
# True  — сайт открыт: noindex снят везде, robots пускает, карта и llms.txt
#         записаны.
#
# Менять ТОЛЬКО вместе с фактами Егора (docs/TODO-EGOR.md): контакты, статус,
# цены. Полуготовая страница в выдаче хуже её отсутствия.
# После правки обязательно прогнать: python scripts/build-pages.py
#                                     python scripts/build-seo.py
# ─────────────────────────────────────────────────────────────────────────
PUBLISHED = False

# Адрес, от которого считаются canonical, og:url и sitemap.
# Слэш на конце обязателен.
#
# ПЕРЕЕЗД НА СВОЙ ДОМЕН. Выбран rezidentkipra.com (проверен свободным 10.08.2026).
# Меняется ровно эта строка, дальше пересборка разносит адрес по всем страницам,
# карте и llms. Внутренние ссылки относительные, переписывать их не надо.
# Порядок и грабли расписаны в docs/STATE.md, раздел «Переезд на свой домен».
# Раскомментировать ТОЛЬКО когда домен куплен и DNS отвечает, иначе canonical
# будет указывать в пустоту.
# BASE_URL = "https://rezidentkipra.com/"
BASE_URL = "https://youpiter999.github.io/cyprus-residency-site/"

# Картинка для превью в мессенджерах. AVIF там не разворачивается почти нигде,
# поэтому лежит отдельный JPEG. Это первый кадр того же ролика, что и постер:
# превью и первый экран показывают одно и то же.
OG_IMAGE = "assets/img/og.jpg"
OG_IMAGE_W = 1200
OG_IMAGE_H = 630
OG_IMAGE_ALT = "Облака над морем с высоты, первый кадр заставки сайта"

# Имя, под которым сайт представляется: шапка, подвал, og:site_name, WebSite,
# карточка Google Business. Выбрано вместе с доменом 10.08.2026.
#
# Почему не «ВНЖ Кипра», как было раньше: это дескриптор услуги, а не имя.
# Спросить его у поисковика как бренд нельзя, поэтому брендовые запросы на
# него не накопятся никогда. На соседнем проекте они дали 619 показов из 778.
#
# В <title> страниц имя НЕ подставляется намеренно: там стоит запрос, по
# которому страницу ищут, и вытеснять его брендом значит менять работающее
# на красивое.
SITE_NAME = "Резидент Кипра"

# ─────────────────────────────────────────────────────────────────────────
# Первоисточники. Ссылки на официальный портал Республики Кипр.
#
# Смысл не в SEO-приёме, а в честности: конкретные пороги дохода, суммы и
# сроки на сайте намеренно не публикуются, потому что меняются. Вместо своей
# цифры даём читателю дорогу к первоисточнику.
#
# Все шесть адресов проверены живым браузером 10.08.2026: отдают 200, заголовки
# совпадают. Проверять curl'ом бесполезно, gov.cy отвечает ботам 403.
# Страницы на английском, читателя предупреждаем.
# ─────────────────────────────────────────────────────────────────────────
MD_HUB = "https://www.gov.cy/mip-md/en/"

OFFICIAL = {
    "pink-slip": [
        ("https://www.gov.cy/mip-md/en/documents/temporary-residence/visitors/",
         "Migration Department: Visitors"),
    ],
    "digital-nomad": [
        ("https://www.gov.cy/mip-md/en/documents/digital-nomads-and-family-members/",
         "Migration Department: Digital nomads and family members"),
    ],
    "pmzh-investicii": [
        ("https://www.gov.cy/mip-md/en/documents/companies-investors-permanent-residence-3/immigration-permits-for-investors/",
         "Migration Department: Immigration Permits for Investors"),
    ],
    "rabota-i-semya": [
        ("https://www.gov.cy/mip-md/en/documents/temporary-residence/work/",
         "Migration Department: Work"),
        ("https://www.gov.cy/mip-md/en/documents/temporary-residence/family-members/",
         "Migration Department: Family Members"),
    ],
}

# ─────────────────────────────────────────────────────────────────────────
# Факты о консультанте. Пока их нет, разметки о человеке и организации на
# сайте НЕТ вообще: выдуманный ProfessionalService в schema.org это ровно та
# же ложь, что выдуманный отзыв, только машиночитаемая.
#
# Как включить, когда Егор пришлёт данные: заполнить поля, поставить
# CONSULTANT_READY = True, прогнать build-pages.py и build-seo.py.
# Гард стоит в build_person_jsonld(): при False узел просто не печатается.
# ─────────────────────────────────────────────────────────────────────────
CONSULTANT_READY = False
CONSULTANT = {
    "name": "",          # имя, под которым работает
    "job_title": "",     # юрист / лицензированный консультант / частное лицо
    "telegram": "",      # https://t.me/...
    "phone": "",         # +357...
    "email": "",
    "area_served": "Кипр",
}


def robots_meta():
    """Строка meta robots под текущий режим. Одна на все пять страниц."""
    if PUBLISHED:
        return '<meta name="robots" content="index, follow, max-image-preview:large">'
    return '<meta name="robots" content="noindex, nofollow">'


def canonical(slug):
    """Канонический адрес страницы. Для главной это BASE_URL без index.html:
    иначе `/` и `/index.html` считаются двумя страницами с одним текстом."""
    if slug in ("", "index"):
        return BASE_URL
    return BASE_URL + slug + ".html"


def official_html(slug, indent="      "):
    """Видимый блок первоисточников для подстраницы."""
    items = OFFICIAL.get(slug)
    if not items:
        return ""
    links = ", ".join(
        f'<a href="{url}" rel="noopener nofollow" target="_blank">{title}</a>'
        for url, title in items)
    return (f'{indent}<p class="src">Первоисточник: {links}. '
            f'Официальный портал Республики Кипр, страницы на английском.</p>')


def build_person_jsonld():
    """Разметка о консультанте. Пустая строка, пока нет фактов."""
    if not CONSULTANT_READY:
        return ""
    import json
    node = {
        "@context": "https://schema.org",
        "@type": "ProfessionalService",
        "name": CONSULTANT["name"] or SITE_NAME,
        "url": BASE_URL,
        "areaServed": CONSULTANT["area_served"],
        "founder": {
            "@type": "Person",
            "name": CONSULTANT["name"],
            "jobTitle": CONSULTANT["job_title"],
        },
    }
    same_as = [u for u in (CONSULTANT["telegram"],) if u]
    if same_as:
        node["sameAs"] = same_as
    if CONSULTANT["phone"]:
        node["telephone"] = CONSULTANT["phone"]
    if CONSULTANT["email"]:
        node["email"] = CONSULTANT["email"]
    return ('<script type="application/ld+json">'
            + json.dumps(node, ensure_ascii=False) + '</script>')
