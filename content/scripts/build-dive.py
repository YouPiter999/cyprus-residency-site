"""Собирает сцену первого экрана: непрерывный нырок с высоты к воде.

Чем это отличается от предыдущего захода (build-video.py) и почему он был
выброшен. Там движение пытался нести МОРФ: оптический поток перетаскивал
пиксели одной картинки в другую, а поверх шёл медленный общий наезд. Морф
между несвязанными сценами это всегда каша, сколько его ни сглаживай, и
владелец сказал прямо: это не видео.

Здесь движение несёт МАСШТАБ. Камера всё время падает вперёд с постоянной
скоростью, а картинки только сменяют друг друга внутри этого падения. Так
устроен тот самый «эффект камеры из космоса»: глаз следит за наездом, и
пока наезд не прерывается, сцена читается как съёмка. Смена картинки в
этот момент проходит мимо внимания.

Устройство одного шага. За шаг камера приближается ровно вдвое (ZOOM_STEP),
поэтому скорость наезда нигде не меняется: масштаб растёт по показательной,
а глаз читает показательный рост масштаба как равномерное движение вперёд.
Картинка k показывается от масштаба 1 (кадр целиком) до 2 (центр кадра во
весь экран). В начале своего шага она проступает сквозь предыдущую, а та в
это время доезжает свой наезд дальше, до 2.46, размывается и гаснет.

Отсюда важное следствие: масштаб МЕНЬШЕ единицы не нужен ни разу. Показать
картинку мельче кадра нельзя, за её краем ничего нет, и все схемы, где
следующая сцена «подъезжает издалека», упираются в это. Здесь наоборот:
уходящая сцена переезжает свой предел и уходит в размытие, а приходящая
всегда начинается резкой и целой.

Исходники увеличены вдвое заранее: наезд доходит до 2.46, и без запаса
разрешения конец каждого шага превращался бы в мыло.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np

# переиспользуем цветокоррекцию, виньетку, зерно и кроп из build-film.py
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "buildfilm", pathlib.Path(__file__).parent / "build-film.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)

from PIL import Image, ImageFilter

ROOT = bf.ROOT
FPS = 30

STEP_SECONDS = 1.2       # шаг нырка: за него камера приближается вдвое
ZOOM_STEP = 2.0          # во сколько раз за шаг
FADE = 0.30              # доля шага, на которой предыдущая сцена ещё видна
DROP = 0.035             # снос центра наезда вниз: падаем не только вперёд
GRAIN = 1.2
SUPERSAMPLE = 2          # запас разрешения под наезд

# Выдержка, как у build-video.py: усреднение трёх кадров весами 1-2-1 это
# 33 мс смаза, ровно как затвор камеры. На быстром наезде она нужнее, чем
# на медленном: без неё мелкая фактура воды стробит.
SHUTTER = ("tmix=frames=3:weights=1 2 1,"
           "trim=start_frame=2,setpts=PTS-STARTPTS")

TARGETS = [
    ("cyprus-descent.mp4", bf.OUT_W, bf.OUT_H, 25, "poster.avif"),
    # мобильный тяжелее по CRF: на телефонной сети вес важнее деталей
    ("cyprus-descent-m.mp4", bf.MOB_W, bf.MOB_H, 31, "poster-m.avif"),
]


def bases() -> list[Image.Image]:
    """Цветокоррекция и запас разрешения под наезд."""
    out = []
    for img in bf.load_sources():
        g = bf.grade(img)
        out.append(g.resize((g.width * SUPERSAMPLE, g.height * SUPERSAMPLE),
                            Image.LANCZOS))
    return out


def zoom(img: Image.Image, s: float, drop: float) -> Image.Image:
    """Центральный кроп с наездом s (всегда >= 1) и сносом центра вниз."""
    w, h = img.size
    cw, ch = w / s, h / s
    cx, cy = w / 2, h * (0.5 + drop)
    left = max(0.0, min(w - cw, cx - cw / 2))
    top = max(0.0, min(h - ch, cy - ch / 2))
    return img.resize((w, h), Image.LANCZOS,
                      box=(left, top, left + cw, top + ch))


def ease(x: float) -> float:
    """Плавное появление: на краях производная нулевая, стык не читается."""
    return x * x * (3.0 - 2.0 * x)


def compose(base: list[Image.Image], k: int, u: float) -> Image.Image:
    """Кадр внутри шага k при местном ходе u от 0 до 1.

    Приходящая сцена идёт от масштаба 1 к ZOOM_STEP. Пока u меньше FADE,
    сквозь неё видна предыдущая, и та продолжает свой наезд ЗА свой предел,
    от ZOOM_STEP до ZOOM_STEP**(1+FADE): камера не притормаживает на стыке.
    """
    s = ZOOM_STEP ** u
    cur = zoom(base[k], s, DROP * u)

    if u >= FADE or k == 0:
        return cur

    prev = zoom(base[k - 1], ZOOM_STEP ** (1.0 + u), DROP * (1.0 + u))
    a = ease(u / FADE)
    return Image.fromarray(
        (np.asarray(prev, dtype=np.float32) * (1.0 - a)
         + np.asarray(cur, dtype=np.float32) * a).astype(np.uint8))


def dress(frame: Image.Image, w: int, h: int) -> Image.Image:
    frame = bf.fit(frame, w, h)
    frame = bf.vignette(frame)
    frame = frame.filter(ImageFilter.UnsharpMask(radius=0.8, percent=30,
                                                 threshold=3))
    return bf.grain(frame, GRAIN)


def encode(name: str, w: int, h: int, crf: int, base: list[Image.Image],
           poster: str) -> None:
    if w % 2 or h % 2:
        sys.exit(f"{name}: нечётный размер {w}x{h}, libx264 такое не кодирует")

    per_step = int(round(FPS * STEP_SECONDS))
    total = per_step * len(base)
    out = pathlib.Path(tempfile.mkdtemp())
    try:
        # Кадры-обёртки по краям: окно выдержки отстаёт на кадр и первые два
        # выхода усредняет по обрезку. Дублируем края и режем лишнее, иначе
        # первый кадр видео отличается от постера зерном и резкостью.
        seq = [(0, 0.0)]
        for i in range(total):
            seq.append((i // per_step, (i % per_step) / per_step))
        seq.append(seq[-1])

        for pos, (k, u) in enumerate(seq, start=1):
            dress(compose(base, k, u), w, h).save(out / f"p_{pos:04d}.png")

        cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
               "-i", "p_%04d.png", "-vf", SHUTTER,
               "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-crf", str(crf), "-g", "120", "-movflags", "+faststart",
               "-an", name]
        r = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"{name}: ffmpeg упал\n{r.stderr[-600:]}")

        dst = ROOT / name
        shutil.move(str(out / name), str(dst))
        mb = dst.stat().st_size / 1024 / 1024
        print(f"{name}  {w}x{h}  {total} кадров  {total / FPS:.1f} сек  {mb:.2f} МБ")

        # постер обязан быть первым кадром ЭТОГО ролика, иначе на старте
        # видна подмена картинки ещё до того, как что-то поедет
        pdst = ROOT / poster
        dress(compose(base, 0, 0.0), w, h).save(pdst, "AVIF", quality=62)
        print(f"{poster}  {w}x{h}  {pdst.stat().st_size / 1024:.0f} КБ")
    finally:
        shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    base = bases()
    print(f"{len(base)} сцен по {STEP_SECONDS} сек, наезд x{ZOOM_STEP} за шаг, "
          f"итого {len(base) * STEP_SECONDS:.1f} сек")
    for name, w, h, crf, poster in TARGETS:
        encode(name, w, h, crf, base, poster)
    print("Готово")
