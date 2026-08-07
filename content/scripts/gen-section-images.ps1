# Генерирует картинки для разделов сайта. По одной на раздел, сюжет привязан
# к смыслу раздела, а не «море для красоты».
#
# Почему такие сюжеты. Pollinations силён в архитектуре, свете, интерьерах и
# текстурах и слаб в людях, руках и тексте. Натюрморт с документами он нарисует
# с нечитаемыми каракулями вместо букв — это читается как подделка. Поэтому
# смысл несут МЕСТА: учреждение, стол у окна, терраса, улица.
#
# Запреты вида «no people» Pollinations слушает плохо, поэтому кадр описан
# предметно: что должно быть в кадре, а не чего быть не должно.

param([string[]]$Only = @())

$ErrorActionPreference = 'Stop'
$gen = Join-Path $PSScriptRoot 'gen-image.ps1'
$dst = Join-Path $PSScriptRoot '..\assets\img\src'

$common = 'muted warm palette, sand and olive and limestone tones, soft natural light, film photograph, fine grain, calm, deserted'

$jobs = @(
  @{ name = 'otkaz';    w = 800;  h = 1000; seed = 11
     p = 'empty waiting corridor inside a Mediterranean government building, pale limestone walls, tall window with wooden louvered shutters casting hard stripes of sunlight across a stone floor, a row of empty wooden chairs along the wall, deserted quiet interior' }

  @{ name = 'razbor';   w = 1024; h = 640;  seed = 12
     p = 'a plain wooden desk beside a tall window in a Mediterranean house, early morning light through half open wooden shutters, closed blank notebook and a glass of water on the desk, whitewashed wall, empty room' }

  @{ name = 'terrasa';  w = 1024; h = 430;  seed = 13
     p = 'quiet terrace of a Cypriot stone house in the morning, wicker chair and small table, potted olive tree, stone railing, distant sea on the horizon beyond the railing, warm haze' }

  # Первый заход дал светлую комнату с цветами, а ноутбук — синим
  # прямоугольником. Помогли ставни и терракотовый пол: они тянут кадр в
  # средиземноморский интерьер, а не в абстрактную светлую комнату.
  @{ name = 'stol-okno'; w = 1024; h = 430; seed = 24
     p = 'wooden writing desk against a window with open wooden shutters in an old Mediterranean apartment, open laptop on the desk, terracotta tiled floor, thick plastered stone wall, warm afternoon sun low across the room, deep shadows' }

  # Слово modern уводило в белую виллу с бассейном — рендер из объявления
  # о продаже. Убрано; вместо него выветренный известняк и вечернее солнце.
  @{ name = 'dom';      w = 1024; h = 430;  seed = 25
     p = 'facade of a weathered sandstone apartment building in Cyprus, warm ochre limestone blocks, deep balconies with wooden shutters, cypress trees along the wall, low golden evening sun raking across the stone' }

  # Раздел про семью, а людей генератор рисует плохо. Обжитость показывают
  # вещи: бельевая верёвка, горшки с геранью, велосипед у стены. Первый
  # заход вышел кислотно-жёлтым, второй — мыльным и пустым; помогли прямая
  # просьба о резкости и мелкие предметы, за которые цепляется глаз.
  @{ name = 'ulica';    w = 1024; h = 430;  seed = 36
     p = 'quiet residential lane in an old Cypriot town, low stone houses, a low garden wall with terracotta pots of geraniums, laundry line with white sheets between two walls, a bicycle leaning against the wall, soft diffused evening light, sharp focus, detailed weathered stonework, desaturated muted colours' }
)

foreach ($j in $jobs) {
  if ($Only.Count -gt 0 -and $Only -notcontains $j.name) { continue }
  $out = Join-Path $dst "$($j.name).jpg"
  Write-Host "--- $($j.name) $($j.w)x$($j.h)"
  & $gen -Prompt "$($j.p), $common" -Out $out -Width $j.w -Height $j.h -Seed $j.seed
}
Write-Host 'Готово'
