"""Собирает фоновое видео первого экрана: ОДИН непрерывный план.

История вопроса. Сначала сцена была секвенцией из 17 картинок при 12 fps,
и её называли дёрганой. Уплотнение до 30 fps не помогло. Замер показал
причину: план длился 0.65 секунды, межкадровая разница внутри плана была
около 2, а на каждой склейке подскакивала до 7. Тогда планы удлинили вдвое
и переходы вчетверо, пик упал с 2.8 до 1.7 медианы, но дёрганье осталось,
потому что осталась его суть: девять разных картинок это девять смен
содержания, сколько их ни растягивай.

Отсюда решение: склеек нет вообще. Один кадр, одно медленное движение,
никаких переходов. Это и есть «как видео»: непрерывный план, а не монтаж.

Петля бесшовная по построению. Движение идёт туда и обратно по косинусу,
поэтому последний кадр совпадает с первым, а на развороте скорость равна
нулю и смена направления не читается. Обычный зацикленный зум в одну
сторону дал бы рывок на стыке цикла.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import math

# переиспользуем цветокоррекцию, виньетку и кроп из build-film.py
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "buildfilm", pathlib.Path(__file__).parent / "build-film.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)

from PIL import Image, ImageFilter

ROOT = bf.ROOT
FPS = 30
SECONDS = 18                 # медленно: это фон, а не аттракцион
FRAMES = FPS * SECONDS
GRAIN = 1.4                  # шум не сжимается, на видео он стоит мегабайтов

# Побережье с высоты. Намеренно без узнаваемых очертаний берега: сцена
# нарисована, и изображать конкретный Кипр она не должна.
SOURCE = 5                   # индекс в отсортированном списке src_*.jpg
ZOOM = 1.11                  # весь ход наезда за девять секунд
DRIFT = 0.05                 # сдвиг центра кадра вниз, доля высоты

TARGETS = [
    ("cyprus-descent.mp4", bf.OUT_W, bf.OUT_H, 24, "poster.avif"),
    # мобильный тяжелее по CRF: на телефонной сети вес важнее деталей
    ("cyprus-descent-m.mp4", bf.MOB_W, bf.MOB_H, 30, "poster-m.avif"),
]


def ken_burns(img: Image.Image, zoom: float, cy_shift: float) -> Image.Image:
    """Наезд с медленным сдвигом центра. Отдельный от build-film.py, потому
    что тому нужен ход внутри короткого плана, а тут одно длинное движение."""
    cw, ch = bf.SRC_W / zoom, bf.SRC_H / zoom
    cx = bf.SRC_W / 2
    cy = bf.SRC_H * (0.5 + cy_shift)
    left = max(0.0, min(bf.SRC_W - cw, cx - cw / 2))
    top = max(0.0, min(bf.SRC_H - ch, cy - ch / 2))
    return img.resize((bf.SRC_W, bf.SRC_H), Image.LANCZOS,
                      box=(left, top, left + cw, top + ch))


def base_image() -> Image.Image:
    files = sorted(bf.SRC.glob("src_*.jpg"))
    if SOURCE >= len(files):
        sys.exit(f"Исходник {SOURCE} не существует, всего {len(files)}")
    return bf.grade(Image.open(files[SOURCE]).convert("RGB"))


def frame_at(base: Image.Image, i: int, w: int, h: int) -> Image.Image:
    # 0 -> 1 -> 0 по косинусу: на краях скорость нулевая, поэтому и стык
    # цикла, и разворот движения не видны
    k = 0.5 - 0.5 * math.cos(2 * math.pi * i / FRAMES)
    frame = ken_burns(base, 1.0 + (ZOOM - 1.0) * k, DRIFT * k)
    frame = bf.fit(frame, w, h)
    frame = bf.vignette(frame)
    frame = frame.filter(ImageFilter.UnsharpMask(radius=0.8, percent=30,
                                                 threshold=3))
    return bf.grain(frame, GRAIN)


def render(w: int, h: int, out_dir: pathlib.Path) -> int:
    base = base_image()
    for i in range(FRAMES):
        frame_at(base, i, w, h).save(out_dir / f"p_{i + 1:04d}.png")
    return FRAMES


def write_poster(poster: str, w: int, h: int) -> None:
    """Постер обязан быть ПЕРВЫМ кадром этого же видео.

    До этого постером стоял `frames/f_001.avif` — первый кадр старой
    секвенции, то есть облака, тогда как видео начинается с побережья.
    Пока ролик не проигран, на экране стояла одна картинка, а с первым
    кадром подменялась другой: скачок содержания на старте, который
    читается как рывок ещё до того, как что-то начнёт двигаться.
    """
    dst = ROOT / poster
    frame_at(base_image(), 0, w, h).save(dst, "AVIF", quality=62)
    print(f"{poster}  {w}x{h}  {dst.stat().st_size / 1024:.0f} КБ")


def encode(name: str, w: int, h: int, crf: int) -> None:
    """ffmpeg спотыкается о кириллицу в пути, поэтому работаем из временной
    папки с относительными именами и переносим готовый файл на место."""
    if w % 2 or h % 2:
        sys.exit(f"{name}: нечётный размер {w}x{h}, libx264 такое не кодирует")

    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        n = render(w, h, tmp)
        # ключевые кадры редкие: сцена больше не перематывается прокруткой,
        # видео играет линейно, и частые ключевые только раздували файл
        cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", "p_%04d.png",
               "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-crf", str(crf), "-g", "120", "-movflags", "+faststart",
               "-an", name]
        r = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"{name}: ffmpeg упал\n{r.stderr[-600:]}")
        dst = ROOT / name
        shutil.move(str(tmp / name), str(dst))
        mb = dst.stat().st_size / 1024 / 1024
        print(f"{name}  {w}x{h}  {n} кадров  {n/FPS:.1f} сек  {mb:.2f} МБ")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    print(f"Один план, {SECONDS} сек, наезд до {ZOOM:.2f}, склеек нет")
    for name, w, h, crf, poster in TARGETS:
        encode(name, w, h, crf)
        write_poster(poster, w, h)
    print("Готово")
