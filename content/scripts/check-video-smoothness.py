"""Меряет монтажную рваность готового видео сцены.

Появился после того, как «дёргается» чинили дважды не с той стороны: сперва
смешиванием кадров, потом переходом на видео. Оба раза причина была в другом,
и оба раза это выяснялось только со слов владельца.

Что меряем. Раскладываем видео на мелкие кадры и считаем среднюю разницу
между соседними. Внутри плана она держится ровной, на склейке подскакивает.
Отношение пика к медиане и есть числовая мера рваности: чем оно выше, тем
заметнее сцена «взрывается» переходами.

Пороги заданы по замеру первой версии, которую владелец назвал дёрганой:
план 0.65 сек, пик к медиане 2.8. Всё, что заметно лучше, считаем годным.
"""
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

FILM = pathlib.Path(__file__).parent.parent / "assets" / "film"

MAX_PEAK_RATIO = 2.2      # пик межкадровой разницы к медиане
MIN_SHOT_SEC = 1.2        # средняя длина плана
FPS = 30


def analyse(name: str) -> bool:
    src = FILM / name
    if not src.exists():
        sys.exit(f"{name}: файла нет")

    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src.resolve()),
                            "-vf", "scale=96:40", "q_%04d.png"],
                           cwd=tmp, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"{name}: ffmpeg не разобрал файл\n{r.stderr[-300:]}")

        files = sorted(tmp.glob("q_*.png"))
        a = [np.asarray(Image.open(f).convert("L"), dtype=np.float32) for f in files]
        d = np.array([float(np.abs(a[i] - a[i - 1]).mean()) for i in range(1, len(a))])

        med = float(np.median(d))
        peak = float(np.percentile(d, 99))
        ratio = peak / max(med, 0.01)

        # склейки: где разница выше полутора медиан
        cuts = [i for i, v in enumerate(d) if v > med * 1.5]
        groups = []
        for c in cuts:
            if not groups or c - groups[-1][-1] > 3:
                groups.append([c])
            else:
                groups[-1].append(c)
        shot = len(files) / FPS / max(1, len(groups))

        ok = ratio <= MAX_PEAK_RATIO and shot >= MIN_SHOT_SEC
        print(f"{name}: {len(files)} кадров, {len(files)/FPS:.1f} сек")
        print(f"  межкадровая разница: медиана {med:.2f}, пик {peak:.2f}, "
              f"пик к медиане {ratio:.2f} (порог {MAX_PEAK_RATIO})")
        print(f"  склеек {len(groups)}, план в среднем {shot:.2f} сек "
              f"(порог {MIN_SHOT_SEC})")
        print("  ВЕРДИКТ: " + ("ровно" if ok else "РВАНО"))
        return ok
    finally:
        for f in tmp.glob("*"):
            f.unlink()
        tmp.rmdir()


if __name__ == "__main__":
    good = all([analyse("cyprus-descent.mp4"), analyse("cyprus-descent-m.mp4")])
    sys.exit(0 if good else 1)
