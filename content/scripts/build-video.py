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
FPS = 30
GRAIN = 1.6                     # шум не сжимается: на видео он стоит мегабайтов

"""Монтаж, а не плотность кадров.

Первая версия просто уплотнила исходную раскадровку с 12 fps до 30 и всё
равно читалась рывками. Замер по готовому файлу объяснил почему: план длился
в среднем 0.65 секунды, минимальный 0.4, и межкадровая разница внутри плана
держалась около 2, а на каждой склейке подскакивала до 7. Семнадцать разных
картинок за одиннадцать секунд это клиповая нарезка: сколько кадров в секунду
ни поставь, мельтешит сам материал.

Поэтому: планов вдвое меньше, каждый вдвое длиннее, переход занимает почти
половину плана. Склейка раз в полторы секунды вместо каждой половины, и
картинки не сменяются, а перетекают.
"""
# девять исходников из семнадцати, равномерно по спуску: облака, море,
# остров, побережье, город, вода у берега. Порядок кадров это сам сюжет,
# поэтому берём через один, а не подряд
PICK = [0, 2, 4, 6, 8, 10, 12, 14, 16]
SHOT = 46                       # 1.53 сек на план
# Переход длиннее самого показа. Пик межкадровой разницы на склейке прямо
# пропорционален скорости изменения прозрачности: при 18 кадрах она менялась
# на 8% за кадр и склейка всё ещё выстреливала втрое выше фона. На 28 кадрах
# это 5%, и переход перестаёт читаться событием.
BLEND = 32                      # 1.07 сек перетекания
# Длительность видео от BLEND не зависит: переход накладывается на начало
# плана, а не добавляется к нему. Поэтому удлинять его дёшево. Цена другая:
# чем длиннее, тем дольше кадр держится смесью двух картинок и тем мягче
# выглядит. Выше 70 процентов плана уходить нельзя, начинается двоение.
ZOOM = 1.13                     # наезд за план, одинаковый: разнобой читался рывком

PLAN = [SHOT] * len(PICK)

TARGETS = [
    ("cyprus-descent.mp4", bf.OUT_W, bf.OUT_H, 25),
    ("cyprus-descent-m.mp4", bf.MOB_W, bf.MOB_H, 26),
]


def render(w: int, h: int, out_dir: pathlib.Path) -> int:
    all_sources = bf.load_sources()
    sources = [bf.grade(all_sources[i]) for i in PICK]

    written = 0
    for i, n in enumerate(PLAN):
        for local in range(n):
            # t доводится до единицы: раньше зум не доходил до конца плана
            # и на склейке камера заметно откатывалась назад
            t = local / max(1, n - 1)
            frame = bf.ken_burns(sources[i], t, ZOOM)

            transition = local < BLEND and i > 0
            if transition:
                # предыдущий план продолжает наезжать под уходящим кадром,
                # иначе на переходе движение останавливается
                t_prev = min(1.0, 1.0 + local / max(1, PLAN[i - 1] - 1) * 0.12)
                prev = bf.ken_burns(sources[i - 1], min(1.0, t_prev), ZOOM)
                alpha = bf.smoothstep((local + 1) / (BLEND + 1))
                frame = Image.blend(prev, frame, alpha)
                # смаз только в середине перехода: на всём переходе он давал
                # мыло там, где кадр уже почти чистый
                mid = 1 - abs((local + 1) / (BLEND + 1) * 2 - 1)
                if mid > 0.15:
                    frame = frame.filter(ImageFilter.GaussianBlur(1.1 * mid))

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
    print(f"{len(PICK)} планов по {SHOT/FPS:.2f} сек, переход {BLEND/FPS:.2f} сек, "
          f"итого {sum(PLAN)} кадров при {FPS} fps = {sum(PLAN)/FPS:.1f} сек")
    for name, w, h, crf in TARGETS:
        encode(name, w, h, crf)
    print("Готово")
