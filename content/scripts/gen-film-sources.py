"""17 исходных кадров Кипра по дуге света: предрассветный холод -> полдень -> золотой час."""
import pathlib
import time
import urllib.parse

import requests

OUT = pathlib.Path(r"C:\Users\Сергей\Downloads\егор-сайт\content\assets\film\src")
OUT.mkdir(parents=True, exist_ok=True)

# Единый фотографический язык: без него 17 кадров не склеятся в один фильм.
# Стабильные якоря: тёплый средиземноморский свет, бирюза, отсутствие людей и текста.
STYLE = (
    "Cyprus Mediterranean, cinematic aerial photography, warm natural daylight, "
    "turquoise sea, clear atmosphere, photorealistic, cinematic color grading, "
    "no people, no text, no watermark, no logo, no borders"
)

# ОДИН непрерывный спуск с высоты к воде. Каждый кадр = следующая ступень высоты.
# Кадры идут строго по убыванию высоты, чтобы зум + кроссфейд читались как падение.
SHOTS = [
    # 1-4: над облаками и сквозь них
    "view from very high altitude above a thick white cloud layer, bright sun above, deep blue sky",
    "descending toward a break in the clouds, gap opening, blue sea barely visible far below",
    "falling through wispy cloud edges, sunlight scattering, hazy blue below",
    "below the clouds now, vast open sea far beneath, faint island silhouette on the horizon",
    # 5-8: остров проявляется
    "aerial view of an island coastline from very high altitude, sea and land meeting, soft haze",
    "high aerial view of a Mediterranean island, mountains and dry green valleys, coastline curving",
    "aerial view of a rocky coastline with bays and capes, deep blue water meeting pale cliffs",
    "aerial view of a coastal town along the shore, dense white buildings, harbour, turquoise shallows",
    # 9-12: снижение к городу
    "lower aerial view over a marina, white yachts in neat rows, clear turquoise water",
    "low aerial view over terracotta rooftops and palm-lined streets near the sea",
    "low aerial view along a seafront promenade, palms, stone walkway, beach beside it",
    "very low aerial view over a sandy beach, sun loungers, gentle surf line, pale sand",
    # 13-17: у самой воды и в воде
    "very low over shallow turquoise water near the shore, sunlight patterns on the sandy bottom",
    "skimming just above the sea surface, small waves, sunlight glitter, shore blurred behind",
    "at water level, clear turquoise water surface filling the frame, gentle ripples",
    "half underwater view at the shoreline, sunlight rays through clear water, sandy bottom",
    "calm sea surface at eye level looking toward the sunlit coast, peaceful horizon",
]


def fetch(idx, prompt):
    """Последовательно, с backoff: у Pollinations жёсткий рейт-лимит на параллель."""
    path = OUT / f"src_{idx:02d}.jpg"
    if path.exists() and path.stat().st_size > 8000:
        return f"  {idx:02d} уже есть, пропускаю"

    full = f"{prompt}, {STYLE}"
    enc = urllib.parse.quote(full, safe="")
    url = (f"https://image.pollinations.ai/prompt/{enc}"
           f"?width=1024&height=576&nologo=true&model=flux&seed={1000 + idx * 7}")

    delay = 8
    for attempt in range(6):
        try:
            r = requests.get(url, timeout=240)
            if r.status_code == 429:
                raise RuntimeError("429 rate limit")
            r.raise_for_status()
            if len(r.content) < 8000:
                raise ValueError(f"слишком мало байт: {len(r.content)}")
            path.write_bytes(r.content)
            return f"  {idx:02d} OK  {len(r.content):>7} bytes"
        except Exception as exc:
            if attempt == 5:
                return f"  {idx:02d} FAIL {exc}"
            time.sleep(delay)
            delay = min(delay * 2, 90)
    return f"  {idx:02d} FAIL"


print(f"Генерирую {len(SHOTS)} кадров в {OUT} ...", flush=True)
for i, shot in enumerate(SHOTS, start=1):
    print(fetch(i, shot), flush=True)
    time.sleep(3)  # межкадровая пауза, чтобы не влетать в лимит

got = sorted(OUT.glob("src_*.jpg"))
print(f"\nГотово: {len(got)}/{len(SHOTS)} файлов, суммарно "
      f"{sum(p.stat().st_size for p in got) / 1024:.0f} КБ")
