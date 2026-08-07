"""Собирает 17 исходников в непрерывный спуск с облаков к морю.

Иллюзия падения держится на:
  1. Движение ВСЕГДА только на приближение, никогда отъезд.
  2. Неравномерная раскадровка: равные планы дают метроном и читаются слайдшоу.
  3. Кроссфейд 3 кадра со smoothstep: фаза 50/50 сжимается до одного кадра.
  4. Смаз на стыковых кадрах: прячет склейку, мыло апскейла и стробинг зума.
  5. Единая цветокоррекция: без неё скачок экспозиции между планами виден
     сильнее, чем скачок содержания.

На выходе: десктопная секвенция WebP, облегчённая мобильная и mp4 предпросмотра.
"""
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = pathlib.Path(r"C:\Users\Сергей\Downloads\егор-сайт\content\assets\film")
SRC = ROOT / "src"
FRAMES = ROOT / "frames"
FRAMES_M = ROOT / "frames-m"

SRC_W, SRC_H = 1024, 576
CROP_H = 428                  # кроп 2.39:1: меньше площади мягкой картинки, кино-формат
# размеры строго чётные: при нечётной высоте libx264 отказывается кодировать
# в yuv420p, и любая сборка видео из кадров падает
# 960x400 растягивалось браузером в бокс героя 1440x774 ровно в 1.94 раза, и
# мыло было видно. 1280 снижает растяжение до 1.45. Выше не имеет смысла:
# исходники 1024px (потолок Pollinations), 1920 сменил бы апскейл браузера на
# апскейл кодировщика и учетверил вес файла, который и так грузится долго.
OUT_W, OUT_H = 1280, 534
# на телефоне широкий кроп вырождается в полоску 343x143, поэтому мобильные
# кадры режутся вертикально, а не масштабируются из горизонтальных
MOB_W, MOB_H = 600, 750
FPS = 12
BLEND = 3
# AVIF при том же визуальном качестве примерно вдвое легче WebP,
# а вес сцены был главным замечанием: 4.93 МБ на 4G это не скроллится
FMT, EXT = "AVIF", "avif"
Q_DESK, Q_MOB = 46, 44

# Неравномерно: сложным планам больше времени, плоской воде меньше.
# Кадры 13-15 почти одинаковая вода - на них лента встанет, если дать поровну.
PLAN_FRAMES = [11, 9, 9, 8, 9, 9, 8, 9, 8, 9, 8, 8, 5, 5, 5, 7, 7]

# Наезд за план. Больше кадров - можно больше наезда без стробинга:
# шаг масштаба выше 2% на кадр при 12 fps начинает рвать движение.
def zoom_end(n_frames: int) -> float:
    return min(1.0 + 0.016 * n_frames, 1.34)


def load_sources() -> list[Image.Image]:
    files = sorted(SRC.glob("src_*.jpg"))
    if len(files) != len(PLAN_FRAMES):
        sys.exit(f"Исходников {len(files)}, а раскадровка на {len(PLAN_FRAMES)}")
    return [Image.open(f).convert("RGB") for f in files]


def grade(img: Image.Image) -> Image.Image:
    """Единая кривая на все планы + сдвиг к палитре сайта (олива/кирпич).

    Без нормализации соседние планы прыгают по яркости, и это заметнее,
    чем смена содержания.
    """
    a = np.asarray(img).astype(np.float32)

    # нормализация экспозиции к общей точке
    mean = a.reshape(-1, 3).mean(axis=0)
    target = np.array([128.0, 132.0, 130.0])
    a = a + (target - mean) * 0.55

    # мягкий сдвиг: синеву в оливковый тил, света в тёплый
    a[..., 0] *= 1.02   # R
    a[..., 1] *= 1.01   # G
    a[..., 2] *= 0.955  # B гасим - уводит бирюзу от открыточной

    a = np.clip(a, 0, 255).astype(np.uint8)
    out = Image.fromarray(a)
    out = ImageEnhance.Color(out).enhance(0.92)     # десатурация: меньше буклета
    out = ImageEnhance.Contrast(out).enhance(1.04)
    return out


def vignette(img: Image.Image) -> Image.Image:
    """Артефакты зума максимальны на периферии - виньетка гасит ровно их."""
    w, h = img.size
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    r = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
    mask = np.clip(1.0 - 0.30 * np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6, 0, 1)
    a = np.asarray(img).astype(np.float32) * mask[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def grain(img: Image.Image, amount: float = 5.0) -> Image.Image:
    """Зерно ДО энкода: маскирует блуждание квантования между кадрами.

    Без него небо и вода 'дышат' полосами - главная причина дешёвого вида.
    """
    a = np.asarray(img).astype(np.float32)
    rng = np.random.default_rng(12345)  # фиксированный сид: зерно не мерцает
    a += rng.normal(0, amount, a.shape[:2])[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def ken_burns(img: Image.Image, t: float, zend: float) -> Image.Image:
    """t от 0 до 1 внутри плана. Наезд + центр к 0.62 высоты = идём к земле."""
    zoom = 1.0 + (zend - 1.0) * t
    cw, ch = SRC_W / zoom, SRC_H / zoom
    cx = SRC_W / 2
    cy = SRC_H * (0.50 + 0.12 * t)
    left = max(0.0, min(SRC_W - cw, cx - cw / 2))
    top = max(0.0, min(SRC_H - ch, cy - ch / 2))
    return img.resize((SRC_W, SRC_H), Image.LANCZOS,
                      box=(left, top, left + cw, top + ch))


def fit(frame: Image.Image, w: int, h: int) -> Image.Image:
    """Кроп по центру под целевое соотношение, затем ресайз. Без растяжения."""
    sw, sh = frame.size
    target = w / h
    if sw / sh > target:           # исходник шире цели: режем по бокам
        nw = int(round(sh * target))
        off = (sw - nw) // 2
        frame = frame.crop((off, 0, off + nw, sh))
    else:                          # исходник выше цели: режем сверху и снизу
        nh = int(round(sw / target))
        off = (sh - nh) // 2
        frame = frame.crop((0, off, sw, off + nh))
    return frame.resize((w, h), Image.LANCZOS)


def smoothstep(x: float) -> float:
    return x * x * (3 - 2 * x)


def build(out_dir: pathlib.Path, w: int, h: int, quality: int,
          step: int = 1) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("f_*.*"):
        old.unlink()

    sources = [grade(s) for s in load_sources()]
    zends = [zoom_end(n) for n in PLAN_FRAMES]

    timeline = []
    for i, n in enumerate(PLAN_FRAMES):
        for local in range(n):
            timeline.append((i, local, n))

    written = 0
    for idx in range(0, len(timeline), step):
        i, local, n = timeline[idx]
        t = local / max(1, n + BLEND - 1)
        frame = ken_burns(sources[i], t, zends[i])

        transition = local < BLEND and i > 0
        if transition:
            prev_n = PLAN_FRAMES[i - 1]
            t_prev = (prev_n + local) / max(1, prev_n + BLEND - 1)
            prev = ken_burns(sources[i - 1], min(t_prev, 1.0), zends[i - 1])
            alpha = smoothstep((local + 1) / (BLEND + 1))
            frame = Image.blend(prev, frame, alpha)
            # смаз на склейке: реальная камера смазывает, и это прячет стык
            frame = frame.filter(ImageFilter.GaussianBlur(1.6))

        frame = fit(frame, w, h)
        frame = vignette(frame)
        if not transition:
            # компенсация будущей билинейной интерполяции в браузере
            frame = frame.filter(ImageFilter.UnsharpMask(radius=0.8, percent=45,
                                                         threshold=3))
        # зерно стоит байтов в WebP, поэтому ровно столько, сколько нужно
        # чтобы сбить полосы на небе и воде, и ни единицей больше
        frame = grain(frame, 3.6 if step == 1 else 5.0)

        written += 1
        frame.save(out_dir / f"f_{written:03d}.{EXT}", FMT, quality=quality)

    return written


def encode_preview() -> None:
    """БОЛЬШЕ НЕ ВЫЗЫВАЕТСЯ. Писала предпросмотр при 12 fps в тот же файл,
    который сейчас играет на сайте при 30 fps: один запуск build-film.py
    вернул бы рывки. Оставлена как справка по обходу ffmpeg.

    ffmpeg этой сборки не читает AVIF как секвенцию, поэтому кладём
    временные PNG. Кириллица в пути тоже ломает ffmpeg, поэтому работаем
    из временной папки с относительными именами."""
    import shutil
    import tempfile

    mp4 = (ROOT / "cyprus-descent.mp4").resolve()
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        for i, f in enumerate(sorted(FRAMES.glob(f"f_*.{EXT}")), 1):
            Image.open(f).convert("RGB").save(tmp / f"p_{i:03d}.png")
        r = subprocess.run(
            ["ffmpeg", "-y", "-framerate", str(FPS), "-i", "p_%03d.png",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(mp4)],
            cwd=tmp, capture_output=True, text=True)
        print("Предпросмотр: " + (f"{mp4.name} {mp4.stat().st_size/1024/1024:.2f} МБ"
                                  if r.returncode == 0 else "ОШИБКА\n" + r.stderr[-400:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def folder_mb(p: pathlib.Path) -> float:
    return sum(f.stat().st_size for f in p.glob("f_*.*")) / 1024 / 1024


if __name__ == "__main__":
    for name, (w, h) in {"десктоп": (OUT_W, OUT_H), "мобилка": (MOB_W, MOB_H)}.items():
        if w % 2 or h % 2:
            sys.exit(f"{name}: размер {w}x{h} нечётный, видео из таких кадров не соберётся")
    print(f"Раскадровка: {len(PLAN_FRAMES)} планов, {sum(PLAN_FRAMES)} кадров, "
          f"{sum(PLAN_FRAMES)/FPS:.1f} сек")

    n = build(FRAMES, OUT_W, OUT_H, Q_DESK)
    print(f"Десктоп: {n} кадров, {folder_mb(FRAMES):.2f} МБ")

    nm = build(FRAMES_M, MOB_W, MOB_H, Q_MOB, step=3)
    print(f"Мобилка: {nm} кадров, {folder_mb(FRAMES_M):.2f} МБ")

    total = folder_mb(FRAMES) + folder_mb(FRAMES_M)
    print(f"Итого секвенций: {total:.2f} МБ" + ("  ПРЕВЫШЕН ЛИМИТ 7 МБ" if total > 7 else ""))
    print("\nВНИМАНИЕ: сцена на сайте больше НЕ собирается из этих кадров.\n"
          "Она играет видео, которое делает build-video.py при 30 fps.\n"
          "Отсюда сайту нужны только f_001 (постер) и кадры героев подстраниц\n"
          "f_060, f_100, f_120, f_130. Остальные можно удалить.\n"
          "Видео здесь НЕ пересобирается: encode_preview писал 12 fps и затёр бы\n"
          "рабочий файл. Собирать видео: python scripts/build-video.py")
