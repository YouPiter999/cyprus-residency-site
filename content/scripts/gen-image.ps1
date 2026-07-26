<#
.SYNOPSIS
  Генерация картинок для сайта: Pollinations (бесплатно, без ключа) + Google AI Studio (по ключу).

.DESCRIPTION
  Провайдеры:
    pollinations - без ключа, потолок 1024px по ширине, сильна в фонах/текстурах/абстракции.
    gemini       - нужен ключ в $env:GEMINI_API_KEY, качество выше, умеет людей/предметку.
    auto         - gemini если ключ есть, иначе pollinations.

.EXAMPLE
  .\gen-image.ps1 -Prompt "abstract dark gradient, amber light bleed, film grain, no people, no text" -Out ..\assets\hero-bg.jpg

.EXAMPLE
  .\gen-image.ps1 -Prompt "barista pouring latte, warm window light" -Out ..\assets\about.jpg -Provider gemini
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Prompt,
  [Parameter(Mandatory = $true)][string]$Out,
  [ValidateSet('auto', 'pollinations', 'gemini')][string]$Provider = 'auto',
  [int]$Width = 1024,
  [int]$Height = 576,
  [int]$Seed = 0,
  [string]$Model = '',
  [int]$Retries = 3
)

$ErrorActionPreference = 'Stop'

# --- Хвосты промпта: гасим типовые промахи генераторов на веб-графике ---
$NegativeTail = 'no text, no watermark, no logo, no ui elements, no captions'

function Resolve-OutPath {
  param([string]$Path)
  # Join-Path с уже абсолютным путём склеивает мусор - разбираем случаи явно
  $full = if ([System.IO.Path]::IsPathRooted($Path)) {
    [System.IO.Path]::GetFullPath($Path)
  } else {
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Path))
  }
  $dir = Split-Path $full -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  return $full
}

function Get-ImageSize {
  param([string]$Path)
  try {
    Add-Type -AssemblyName System.Drawing -ErrorAction Stop
    $img = [System.Drawing.Image]::FromFile($Path)
    $size = "$($img.Width)x$($img.Height)"
    $img.Dispose()
    return $size
  } catch { return 'unknown' }
}

function Invoke-Pollinations {
  param([string]$Prompt, [string]$OutFile, [int]$W, [int]$H, [int]$Seed, [string]$Model)

  $modelName = if ($Model) { $Model } else { 'flux' }
  $encoded = [uri]::EscapeDataString("$Prompt, $NegativeTail")
  $query = "width=$W&height=$H&nologo=true&model=$modelName"
  if ($Seed -gt 0) { $query += "&seed=$Seed" }
  $url = "https://image.pollinations.ai/prompt/$encoded" + "?" + $query

  # flux считает дольше дефолтной модели - таймаут с запасом
  Invoke-WebRequest -Uri $url -OutFile $OutFile -TimeoutSec 180 -UseBasicParsing -ErrorAction Stop

  if ((Get-Item $OutFile).Length -lt 5000) {
    throw "Ответ подозрительно мал ($((Get-Item $OutFile).Length) байт) - вероятно, заглушка вместо картинки"
  }
}

function Invoke-Gemini {
  param([string]$Prompt, [string]$OutFile, [string]$Model)

  $key = $env:GEMINI_API_KEY
  if (-not $key) { throw "Нет ключа: задай `$env:GEMINI_API_KEY (см. aistudio.google.com/apikey)" }

  $modelName = if ($Model) { $Model } else { 'gemini-2.5-flash-image' }
  $uri = "https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent"

  $body = @{
    contents = @(@{ parts = @(@{ text = "$Prompt. $NegativeTail" }) })
  } | ConvertTo-Json -Depth 10 -Compress

  $resp = Invoke-RestMethod -Uri $uri -Method Post -Body $body `
    -ContentType 'application/json' `
    -Headers @{ 'x-goog-api-key' = $key } `
    -TimeoutSec 180 -ErrorAction Stop

  $part = $resp.candidates[0].content.parts | Where-Object { $_.inlineData } | Select-Object -First 1
  if (-not $part) {
    $txt = ($resp.candidates[0].content.parts | ForEach-Object { $_.text }) -join ' '
    throw "Модель вернула текст вместо картинки: $txt"
  }

  [IO.File]::WriteAllBytes($OutFile, [Convert]::FromBase64String($part.inlineData.data))
}

# --- Выбор провайдера ---
$chosen = $Provider
if ($chosen -eq 'auto') {
  $chosen = if ($env:GEMINI_API_KEY) { 'gemini' } else { 'pollinations' }
}

$outFile = Resolve-OutPath -Path $Out
$attempt = 0
$lastError = $null

while ($attempt -lt $Retries) {
  $attempt++
  try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    switch ($chosen) {
      'gemini'       { Invoke-Gemini -Prompt $Prompt -OutFile $outFile -Model $Model }
      'pollinations' { Invoke-Pollinations -Prompt $Prompt -OutFile $outFile -W $Width -H $Height -Seed $Seed -Model $Model }
    }
    $sw.Stop()

    $size = Get-ImageSize -Path $outFile
    $bytes = (Get-Item $outFile).Length
    "OK [$chosen] $outFile  $size  $bytes bytes  $([math]::Round($sw.Elapsed.TotalSeconds,1))s"

    if ($chosen -eq 'pollinations' -and $Width -gt 1024) {
      Write-Warning "Просили ${Width}px, но Pollinations режет до 1024px. Фактический размер: $size"
    }
    exit 0
  }
  catch {
    $lastError = $_.Exception.Message
    Write-Warning "Попытка $attempt/$Retries [$chosen] не удалась: $lastError"

    # Ключ протух / модель недоступна - падаем на бесплатный провайдер, но только если выбирали автоматом
    if ($chosen -eq 'gemini' -and $Provider -eq 'auto' -and $attempt -eq 1) {
      Write-Warning "Переключаюсь на pollinations"
      $chosen = 'pollinations'
    }
  }
}

Write-Error "Не удалось сгенерировать за $Retries попыток. Последняя ошибка: $lastError"
exit 1
