"""Готовит сгенерированные картинки разделов под палитру сайта.

Зачем отдельный шаг. Pollinations отдаёт бледные и мягкие кадры, каждый в
своей экспозиции. Положить их на страницу как есть — получить набор разных
фотографий рядом с фильмом, снятым в одной цветовой кривой. Поэтому гоним
их через ту же `grade()` из build-film.py, что и планы нырка: нормализация
экспозиции к общей точке, увод синевы в оливу, лёгкая десатурация. После
этого картинки разделов и кадры фильма читаются как одна съёмка.

Резкость: у генератора всё немного мыльное, и на светлой бумаге это видно.
Unsharp сильнее, чем в фильме (там кадр и так дожимается наездом).

Кроп вертикальный, параметр `focus` — какая доля картинки остаётся сверху.
У коридора важен низ с полосами света и дверь в конце, поэтому 0.28, а не
центр.
"""
import importlib.util
import pathlib

from PIL import Image, ImageEnhance, ImageFilter

_spec = importlib.util.spec_from_file_location(
    "buildfilm", pathlib.Path(__file__).parent / "build-film.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)

SRC = pathlib.Path(__file__).parent.parent / "assets" / "img" / "src"
DST = pathlib.Path(__file__).parent.parent / "assets" / "img"

# имя, соотношение сторон, доля сверху при кропе, (яркость, контраст), резкость
#
# Про яркость. `grade()` нормализует экспозицию всех кадров к одной точке —
# для фильма это спасение, иначе соседние планы прыгают. Но картинка раздела
# живёт не среди своих, а на подложке секции, и светлый кадр на чернильном
# фоне светит фарой. Поэтому у «отказа» отдельная поправка вниз.
JOBS = [
    # index, «Когда отказывают»: стоит в липком блоке рядом со стопкой
    # карточек. Высота блока ограничена экраном: вводка плюс высокий кадр
    # перестают помещаться, и sticky тихо перестаёт работать. Отсюда 3:2,
    # хотя исходник вертикальный — важное (полосы света и дверь в конце)
    # лежит в средней трети, её и оставляем.
    ("otkaz", 3 / 2, 0.42, (0.88, 1.16), 95),
    # index, «Как я беру деньги»: под текстом левой колонки, которая
    # кончалась раньше правой. Кадр 16:10 закрыл дыру и тут же сделал
    # обратную: колонка стала на 299px ДЛИННЕЕ соседней. Нужна полоса, а не
    # картинка, поэтому то же соотношение, что у полос на внутренних
    # страницах. Фокус ниже центра: важен стол, а не потолок.
    ("razbor", 1024 / 430, 0.55, (1.0, 1.06), 95),
    # полосы на внутренних страницах, между «Что понадобится» и «Деньги»
    ("terrasa", 1024 / 430, 0.5, (1.0, 1.0), 48),
    ("stol-okno", 1024 / 430, 0.5, (1.0, 1.0), 48),
    ("dom", 1024 / 430, 0.5, (1.0, 1.0), 48),
    ("ulica", 1024 / 430, 0.5, (1.0, 1.0), 48),
]


def crop_to(img: Image.Image, ratio: float, focus: float) -> Image.Image:
    w, h = img.size
    want_h = w / ratio
    if want_h <= h:
        top = (h - want_h) * focus
        return img.crop((0, round(top), w, round(top + want_h)))
    want_w = h * ratio
    left = (w - want_w) / 2
    return img.crop((round(left), 0, round(left + want_w), h))


def run() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for name, ratio, focus, (bright, contrast), sharpen in JOBS:
        src = SRC / f"{name}.jpg"
        if not src.exists():
            raise SystemExit(f"{name}: нет исходника {src}")

        img = Image.open(src).convert("RGB")
        img = crop_to(img, ratio, focus)
        img = bf.grade(img)
        if bright != 1.0:
            img = ImageEnhance.Brightness(img).enhance(bright)
        if contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast)
        img = img.filter(ImageFilter.UnsharpMask(radius=0.9, percent=sharpen,
                                                 threshold=3))
        # чётность не нужна (это не видео), но кратность двойке бережёт
        # AVIF от лишнего паддинга
        w, h = img.size
        img = img.crop((0, 0, w - w % 2, h - h % 2))

        out = DST / f"{name}.avif"
        img.save(out, "AVIF", quality=64)
        print(f"{name}.avif  {img.size[0]}x{img.size[1]}  "
              f"{out.stat().st_size / 1024:.0f} КБ")


if __name__ == "__main__":
    run()
