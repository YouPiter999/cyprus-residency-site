"""Собирает сцену спуска на Кипр как видео, а не как секвенцию картинок.

Зачем отдельно от build-film.py. Секвенция сделана на 12 кадрах в секунду:
столько картинок ещё разумно тянуть по сети поштучно. Но 12 fps дискретны
сами по себе, и на автопрогоне это видно как рывки. Подмешивание соседнего
кадра прозрачностью не лечит: два кадра, наложенные друг на друга, дают
двоение, а не движение.

Здесь движение считается честно. Ken Burns у нас программный, поэтому
промежуточные положения камеры можно посчитать точно, а не угадывать
интерполяцией. Раскадровка та же, просто плотнее в 2.5 раза.

Зерно намеренно слабее, чем в секвенции: шум не сжимается, и на видео
каждая единица зерна стоит сотен килобайт.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

# переиспользуем обработку кадров из build-film.py: дублировать цветокоррекцию
# и виньетку значит однажды поправить одну и забыть про другую
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "buildfilm", pathlib.Path(__file__).parent / "build-film.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)

from PIL import Image, ImageFilter

ROOT = bf.ROOT
FPS = 30                        # 12 читались рывками, 30 идут слитно
SCALE = FPS / bf.FPS            # во столько раз плотнее исходной раскадровки
BLEND = max(2, round(bf.BLEND * SCALE))
GRAIN = 1.6                     # шум не сжимается: на видео он стоит мегабайтов

PLAN = [max(1, round(n * SCALE)) for n in bf.PLAN_FRAMES]

TARGETS = [
    ("cyprus-descent.mp4", bf.OUT_W, bf.OUT_H, 25),
    ("cyprus-descent-m.mp4", bf.MOB_W, bf.MOB_H, 26),
]


def render(w: int, h: int, out_dir: pathlib.Path) -> int:
    sources = [bf.grade(s) for s in bf.load_sources()]
    # наезд считаем от ИСХОДНОЙ длины плана: иначе на плотной раскадровке
    # zoom_end упрётся в потолок и движение станет одинаковым у всех планов
    zends = [bf.zoom_end(n) for n in bf.PLAN_FRAMES]

    written = 0
    for i, n in enumerate(PLAN):
        for local in range(n):
            t = local / max(1, n + BLEND - 1)
            frame = bf.ken_burns(sources[i], t, zends[i])

            transition = local < BLEND and i > 0
            if transition:
                prev_n = PLAN[i - 1]
                t_prev = (prev_n + local) / max(1, prev_n + BLEND - 1)
                prev = bf.ken_burns(sources[i - 1], min(t_prev, 1.0), zends[i - 1])
                alpha = bf.smoothstep((local + 1) / (BLEND + 1))
                frame = Image.blend(prev, frame, alpha)
                frame = frame.filter(ImageFilter.GaussianBlur(1.4))

            frame = bf.fit(frame, w, h)
            frame = bf.vignette(frame)
            if not transition:
                frame = frame.filter(ImageFilter.UnsharpMask(radius=0.8, percent=35,
                                                             threshold=3))
            frame = bf.grain(frame, GRAIN)

            written += 1
            frame.save(out_dir / f"p_{written:04d}.png")
    return written


def encode(name: str, w: int, h: int, crf: int) -> None:
    """ffmpeg спотыкается о кириллицу в пути, поэтому работаем из временной
    папки с относительными именами и переносим готовый файл на место."""
    if w % 2 or h % 2:
        sys.exit(f"{name}: нечётный размер {w}x{h}, libx264 такое не кодирует")

    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        n = render(w, h, tmp)
        # -g 10: ключевой кадр каждые треть секунды. Прокрутка гоняет
        # currentTime по произвольным точкам, и на редких ключевых кадрах
        # браузер отматывает назад к ближайшему, что и есть рывок
        cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", "p_%04d.png",
               "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-crf", str(crf), "-g", "10", "-keyint_min", "10",
               "-sc_threshold", "0", "-movflags", "+faststart", "-an", name]
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
    print(f"Раскадровка {sum(bf.PLAN_FRAMES)} кадров при {bf.FPS} fps "
          f"превращается в {sum(PLAN)} при {FPS} fps")
    for name, w, h, crf in TARGETS:
        encode(name, w, h, crf)
    print("Готово")
