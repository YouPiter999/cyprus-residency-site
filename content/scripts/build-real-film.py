"""Собирает первый экран из НАСТОЯЩЕГО видео вместо математики.

Чем это отличается от build-dive.py. Там движение подделано: нарисованные
кадры и наезд по показательной, потому что видеомодели не было. Здесь кадры
рождает видеомодель, и движение настоящее.

Устройство. Модель отдаёт 3-5 секунд за вызов, а первому экрану нужно около
получаса секунд, поэтому ролики СЦЕПЛЯЮТСЯ: последний кадр предыдущего идёт
входной картинкой следующего. Так полёт продолжается, а не начинается заново.
Первый вход — наш собственный цветокорректированный кадр, из-за чего вся
цепочка наследует палитру сайта без подгонки.

Где это ломается. Модель перечитывает входной кадр по-своему, и прямая
склейка даёт скачок: замер первой пробы показал 2.3 медианы межкадровой
разницы, ровно уровень забракованного морфа. Поэтому стыки не встык, а
растворением: короткое перекрытие глушит скачок, а содержание при этом
продолжается, в отличие от морфа между несвязанными сценами.

Сервис: Space `Lightricks/ltx-video-distilled` на ZeroGPU, зовётся анонимно,
без ключа и карты. Один вызов идёт 1-3 минуты, поэтому промежуточные ролики
складываются на диск: упавший вызов не должен обнулять всю цепочку.
"""
import pathlib
import shutil
import subprocess
import sys
import time

SPACE = "Lightricks/ltx-video-distilled"
ROOT = pathlib.Path(__file__).parent.parent / "assets" / "film"
RAW = ROOT / "real-src"
NEG = "worst quality, inconsistent motion, blurry, jittery, distorted, text, watermark"

# Шаги полёта. Каждому свой промпт: без него модель придумывает продолжение
# сама и уводит цепочку в сторону от нырка на Кипр.
STEPS = [
    "aerial view high above the sea, camera flying forward and slowly descending, "
    "thick cumulus clouds below lit by low sun, calm cinematic drone shot",
    "camera descends through gaps in the clouds, turquoise sea opening below, "
    "continuous forward motion, cinematic aerial",
    "flying lower over open turquoise sea toward a distant coastline, "
    "steady forward descent, cinematic aerial",
    "approaching the Cyprus coastline from the sea, rocky shore and pale cliffs "
    "ahead, continuous forward descent, cinematic aerial",
    "flying low over the rocky coast, stone houses with terracotta roofs and "
    "cypress trees below, continuous forward motion, cinematic aerial",
    "descending close to clear shallow water near the shore, sunlight on the "
    "seabed, slow forward motion, cinematic aerial",
]

W, H = 1280, 512
DUR = 5.0            # секунд за вызов
XF = 0.45            # растворение на стыке


def generate(start: pathlib.Path) -> list[pathlib.Path]:
    """Цепочка роликов. Возвращает то, что успело собраться."""
    from gradio_client import Client, handle_file

    RAW.mkdir(parents=True, exist_ok=True)
    client = Client(SPACE, verbose=False)
    cur = start
    out = []

    for i, prompt in enumerate(STEPS, start=1):
        dst = RAW / f"clip_{i:02d}.mp4"
        if dst.exists():
            print(f"{dst.name}: уже есть, пропускаю")
            out.append(dst)
            cur = last_frame(dst)
            continue

        for attempt in (1, 2):
            try:
                res = client.predict(
                    prompt=prompt, negative_prompt=NEG,
                    input_image_filepath=handle_file(str(cur)),
                    input_video_filepath=None,
                    height_ui=H, width_ui=W, mode="image-to-video",
                    duration_ui=DUR, ui_frames_to_use=9,
                    seed_ui=100 + i, randomize_seed=False,
                    ui_guidance_scale=1, improve_texture_flag=True,
                    api_name="/image_to_video")
                src = res[0]["video"] if isinstance(res[0], dict) else res[0]
                shutil.copy(src, dst)
                print(f"{dst.name}: готов")
                out.append(dst)
                cur = last_frame(dst)
                break
            except Exception as exc:                      # noqa: BLE001
                print(f"{dst.name}: попытка {attempt} не вышла: "
                      f"{type(exc).__name__} {str(exc)[:160]}")
                if attempt == 2:
                    print("дальше не идём, собираем из того, что есть")
                    return out
                time.sleep(20)
    return out


def last_frame(clip: pathlib.Path) -> pathlib.Path:
    """Последний кадр ролика: он же вход следующего."""
    dst = clip.with_suffix(".jpg")
    run(["ffmpeg", "-v", "error", "-sseof", "-0.1", "-i", str(clip),
         "-frames:v", "1", "-q:v", "2", "-y", str(dst)])
    return dst


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"упало: {' '.join(cmd[:6])}\n{r.stderr[-500:]}")


def stitch(clips: list[pathlib.Path], out: pathlib.Path) -> None:
    """Склейка растворением. Встык стык виден, это замерено."""
    if not clips:
        sys.exit("склеивать нечего")
    if len(clips) == 1:
        shutil.copy(clips[0], out)
        return

    # xfade отсчитывает offset по таймлайну ПЕРВОГО входа, то есть по уже
    # склеенному куску. После k растворений длина склейки равна сумме
    # длительностей минус k перекрытий, поэтому offset очередного стыка это
    # сумма предыдущих длительностей минус i перекрытий. Первая версия
    # вычитала перекрытие дважды, и каждый следующий стык уезжал на 0.45с
    # вперёд, отъедая содержание.
    parts, filt, prev = [], [], "0:v"
    total = 0.0
    for i, c in enumerate(clips):
        parts += ["-i", str(c)]
    for i in range(1, len(clips)):
        total += duration(clips[i - 1])
        offset = total - i * XF
        tag = f"v{i}"
        filt.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={XF}:"
                    f"offset={offset:.3f}[{tag}]")
        prev = tag
    run(["ffmpeg", "-v", "error", *parts, "-filter_complex", ";".join(filt),
         "-map", f"[{prev}]", "-c:v", "libx264", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-crf", "28", "-g", "120",
         "-movflags", "+faststart", "-an", "-y", str(out)])


def duration(path: pathlib.Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


if __name__ == "__main__":
    start = ROOT / "src" / "src_01.jpg"
    if not start.exists():
        sys.exit(f"нет стартового кадра {start}")
    clips = generate(start)
    print(f"роликов собрано: {len(clips)} из {len(STEPS)}")
    dst = ROOT / "cyprus-real.mp4"
    stitch(clips, dst)
    print(f"{dst.name}  {duration(dst):.1f} сек  "
          f"{dst.stat().st_size / 1024 / 1024:.2f} МБ")
