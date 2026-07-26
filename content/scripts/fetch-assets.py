"""Тянет шрифты и GSAP локально: прод не должен зависеть от чужих CDN."""
import pathlib
import re

import requests

ROOT = pathlib.Path(r"C:\Users\Сергей\Downloads\егор-сайт\content\assets")
FONTS = ROOT / "fonts"
JS = ROOT / "js"
FONTS.mkdir(parents=True, exist_ok=True)
JS.mkdir(parents=True, exist_ok=True)

# UA современного браузера, иначе Google отдаст ttf вместо woff2
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")}

FAMILIES = {
    "onest": "https://fonts.googleapis.com/css2?family=Onest:wght@600;700&display=swap",
    "manrope": "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600&display=swap",
}

face_css = []
for name, url in FAMILIES.items():
    css = requests.get(url, headers=UA, timeout=60).text
    blocks = re.findall(r"@font-face\s*\{[^}]+\}", css)
    kept = 0
    for b in blocks:
        # берём только кириллицу и латиницу, остальные подмножества не нужны
        rng = re.search(r"unicode-range:\s*([^;]+);", b)
        if rng and not re.search(r"U\+04|U\+0000|U\+0301", rng.group(1)):
            continue
        src = re.search(r"url\((https://[^)]+\.woff2)\)", b)
        wght = re.search(r"font-weight:\s*(\d+)", b)
        if not src or not wght:
            continue
        kept += 1
        fname = f"{name}-{wght.group(1)}-{kept}.woff2"
        (FONTS / fname).write_bytes(requests.get(src.group(1), headers=UA, timeout=60).content)
        face_css.append(
            "@font-face{font-family:'%s';font-style:normal;font-weight:%s;"
            "font-display:swap;src:url('assets/fonts/%s') format('woff2');"
            "unicode-range:%s}" % (name.capitalize(), wght.group(1), fname,
                                   rng.group(1).strip() if rng else "U+0000-00FF")
        )
    print(f"{name}: сохранено {kept} файлов")

(FONTS / "faces.css").write_text("\n".join(face_css), encoding="utf-8")
print(f"CSS @font-face: {FONTS / 'faces.css'}")

for fname, url in {
    "gsap.min.js": "https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js",
    "ScrollTrigger.min.js": "https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/ScrollTrigger.min.js",
}.items():
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    (JS / fname).write_bytes(r.content)
    print(f"{fname}: {len(r.content) // 1024} КБ")
