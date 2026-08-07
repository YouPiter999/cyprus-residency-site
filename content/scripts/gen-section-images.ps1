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

# «soft natural light» из первого захода работало против резкости. Свет теперь
# задаёт каждый промпт сам, здесь остаётся только палитра и настроение.
$common = 'muted warm palette, sand and olive and limestone tones, film photograph, fine grain, calm, deserted'

$jobs = @(
  # Жюри завернуло обе как «размытую ватную AI-графику». Три поправки разом.
  # Первая: размер. Pollinations режет по ПЛОЩАДИ около 590 тысяч пикселей, и
  # запрошенные 800x1000 вернулись как 686x858, а 1024x640 как 971x607. Просим
  # 1024x576 — это ровно у потолка, даёт максимум ширины, а кадрирование под
  # нужную пропорцию делает уже prep-section-images.py.
  # Вторая: слова. Мягкость идёт от глубины кадра, поэтому просим deep focus и
  # жёсткий свет, а не «soft natural light», как в первом заходе.
  # Третья: обработка, там поднят unsharp.
  # Глубокая перспектива коридора и была источником мыла: flux размывает даль,
  # и чем длиннее уходящий вдаль объём, тем ватнее кадр. Композиция сменена на
  # неглубокую — закрытая дверь в упор. По смыслу это даже сильнее коридора:
  # раздел про отказ, а закрытая дверь и есть отказ.
  @{ name = 'otkaz';    w = 1024; h = 576;  seed = 43
     p = 'closed wooden double door at the end of a Mediterranean government corridor, seen straight on from a few steps away, flat shallow composition, sharp architectural photograph, deep focus, hard bands of sunlight from window shutters falling across the door and the stone floor, pale limestone wall, brass handle, high detail, visible wood grain and stone texture' }

  @{ name = 'razbor';   w = 1024; h = 576;  seed = 42
     p = 'wooden desk against a window with open wooden shutters in a Mediterranean room, sharp interior photograph, deep focus, crisp edges, hard afternoon sunlight striping the plastered wall, closed notebook and a glass of water on the desk, terracotta floor tiles, high detail, visible wood grain and plaster texture' }

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
