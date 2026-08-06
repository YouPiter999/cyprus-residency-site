"""Собирает сцену первого экрана: непрерывный спуск с облаков к воде.

Четыре захода, и только четвёртый дал движение.

1. Секвенция картинок при 12 fps. Дёргалась.
2. Те же картинки при 30 fps. Дёргалась так же: частота кадров ни при чём.
3. Девять планов вместо семнадцати, переход длиннее показа. Пик межкадровой
   разницы упал с 2.8 до 1.7 в медиане, но дёрганье осталось: растворение
   это НЕ движение. Два кадра, наложенные друг на друга, дают двоение.
4. Один кадр с наездом. Дёрганья нет, потому что нет и сцены: спуск
   выброшен, осталась фотография с зумом. Так делать было нельзя.

Здесь между соседними исходниками считается ОПТИЧЕСКИЙ ПОТОК: ffmpeg
оценивает, куда сместился каждый участок кадра, и рисует промежуточные
положения. Пиксели переезжают, а не проступают сквозь друг друга. Из
семнадцати нарисованных картинок выходит 680 кадров непрерывного полёта.

Поверх морфа идёт медленный наезд, посчитанный в PIL, а не фильтром
zoompan: тот квантует масштаб по кадрам и сам по себе даёт мелкую тряску.

Петля замкнута: в конец списка дописан первый исходник, поэтому последний
кадр перетекает в первый, и стык цикла не читается склейкой.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

# переиспользуем цветокоррекцию, виньетку, зерно и кроп из build-film.py
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "buildfilm", pathlib.Path(__file__).parent / "build-film.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)

from PIL import Image, ImageFilter

ROOT = bf.ROOT
FPS = 30
# Секунд на переход между соседними исходниками. Больше секунды: поток
# успевает довезти содержание плавно, и ни один участок кадра не прыгает.
STEP_SECONDS = 1.33
GRAIN = 1.2                  # шум не сжимается, на видео он стоит мегабайтов

ZOOM = 1.16                  # общий наезд за весь полёт, поверх морфа
DRIFT = 0.06                 # сдвиг центра кадра вниз, доля высоты

TARGETS = [
    ("cyprus-descent.mp4", bf.OUT_W, bf.OUT_H, 25, "poster.avif"),
    # мобильный тяжелее по CRF: на телефонной сети вес важнее деталей
    ("cyprus-descent-m.mp4", bf.MOB_W, bf.MOB_H, 31, "poster-m.avif"),
]

# Оценка движения. bidir считает поток в обе стороны, aobmc сглаживает
# границы блоков, vsbmc делит блок там, где внутри него движение разное.
# search_param поднят: между соседними исходниками смещения крупные, и на
# стандартном радиусе поток срывается в кашу.
#
# scd=none обязателен. По умолчанию minterpolate ищет смену сцены и там,
# где разница велика, НЕ интерполирует, а просто переключает кадр. Наши
# исходники нарисованы порознь, поэтому детектор срабатывал на переходах —
# ровно там, где нужно движение. В готовом файле это выглядело как одна
# честная склейка посреди полёта: кадры 19 и 20 разные картинки без
# единого промежуточного. Межкадровая разница на ней 36 при фоне 3.7.
MINTERPOLATE = ("minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:"
                "me_mode=bidir:me=umh:search_param=64:vsbmc=1:scd=none")


def flow_frames(work: pathlib.Path) -> list[pathlib.Path]:
    """Раскладывает исходники и достраивает между ними промежуточные кадры.

    ffmpeg спотыкается о кириллицу в пути, поэтому всё делается во временной
    папке с относительными именами.
    """
    sources = [bf.grade(s) for s in bf.load_sources()]
    sources.append(sources[0])          # замыкаем петлю: конец перетекает в начало
    for i, img in enumerate(sources):
        img.save(work / f"s_{i:03d}.png")

    rate = 1.0 / STEP_SECONDS
    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", f"{rate:.6f}",
           "-i", "s_%03d.png", "-vf", MINTERPOLATE.format(fps=FPS),
           "-f", "image2", "m_%04d.png"]
    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"minterpolate упал\n{r.stderr[-800:]}")

    frames = sorted(work.glob("m_*.png"))
    if len(frames) < FPS * 10:
        sys.exit(f"Поток дал всего {len(frames)} кадров, это не полёт")
    # последний кадр это снова первый исходник: в петле он лишний, иначе
    # на стыке цикла один и тот же кадр показывается дважды
    return frames[:-1]


def push_in(img: Image.Image, k: float) -> Image.Image:
    """Наезд с медленным сдвигом центра вниз. k от 0 в начале до 1 в конце."""
    zoom = 1.0 + (ZOOM - 1.0) * k
    w, h = img.size
    cw, ch = w / zoom, h / zoom
    cx, cy = w / 2, h * (0.5 + DRIFT * k)
    left = max(0.0, min(w - cw, cx - cw / 2))
    top = max(0.0, min(h - ch, cy - ch / 2))
    return img.resize((w, h), Image.LANCZOS,
                      box=(left, top, left + cw, top + ch))


def dress(src: pathlib.Path, k: float, w: int, h: int) -> Image.Image:
    """Кадр потока → кадр сцены: наезд, кроп под формат, виньетка, зерно."""
    frame = push_in(Image.open(src).convert("RGB"), k)
    frame = bf.fit(frame, w, h)
    frame = bf.vignette(frame)
    frame = frame.filter(ImageFilter.UnsharpMask(radius=0.8, percent=30,
                                                 threshold=3))
    return bf.grain(frame, GRAIN)


def encode(name: str, w: int, h: int, crf: int,
           frames: list[pathlib.Path], work: pathlib.Path) -> None:
    if w % 2 or h % 2:
        sys.exit(f"{name}: нечётный размер {w}x{h}, libx264 такое не кодирует")

    out = pathlib.Path(tempfile.mkdtemp())
    try:
        n = len(frames)
        for i, src in enumerate(frames):
            dress(src, i / (n - 1), w, h).save(out / f"p_{i + 1:04d}.png")
        # ключевые кадры редкие: сцена играет линейно и прокруткой не
        # перематывается, частые ключевые только раздували бы файл
        cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
               "-i", "p_%04d.png", "-c:v", "libx264", "-profile:v", "high",
               "-pix_fmt", "yuv420p", "-crf", str(crf), "-g", "120",
               "-movflags", "+faststart", "-an", name]
        r = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"{name}: ffmpeg упал\n{r.stderr[-600:]}")
        dst = ROOT / name
        shutil.move(str(out / name), str(dst))
        mb = dst.stat().st_size / 1024 / 1024
        print(f"{name}  {w}x{h}  {n} кадров  {n / FPS:.1f} сек  {mb:.2f} МБ")
    finally:
        shutil.rmtree(out, ignore_errors=True)


def write_poster(poster: str, w: int, h: int, first: pathlib.Path) -> None:
    """Постер обязан быть ПЕРВЫМ кадром этого же видео.

    До этого постером стоял `frames/f_001.avif` — кадр старой секвенции,
    и он не совпадал с началом ролика. Пока видео не пошло, на экране
    стояла одна картинка, а с первым кадром подменялась другой: скачок
    содержания ещё до того, как что-то начнёт двигаться.
    """
    dst = ROOT / poster
    dress(first, 0.0, w, h).save(dst, "AVIF", quality=62)
    print(f"{poster}  {w}x{h}  {dst.stat().st_size / 1024:.0f} КБ")


if __name__ == "__main__":
    work = pathlib.Path(tempfile.mkdtemp())
    try:
        print("Считаю оптический поток между исходниками...")
        frames = flow_frames(work)
        print(f"{len(frames)} кадров полёта, {len(frames) / FPS:.1f} сек")
        for name, w, h, crf, poster in TARGETS:
            encode(name, w, h, crf, frames, work)
            write_poster(poster, w, h, frames[0])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("Готово")
