# 每日 4 条视频批量生成编排脚本（v2）
# 用法: powershell -ExecutionPolicy Bypass -File daily_gen.ps1 -ManifestPath E:\...\manifest.json
# manifest.json 格式:
# {
#   "date": "2026-10-18",
#   "videos": [
#     {"category":"健康","title":"xxx","script_file":"E:\...\health.txt",
#      "materials_dir":"E:\...\mpt_materials\walk",
#      "materials":["E:\...\mpt_materials\walk\clip_03.mp4", ...]},   # materials 可选：按内容匹配指定的素材（绝对路径）
#     ...
#   ]
# }
# 素材选择逻辑：
#  1. 若 manifest 提供了 materials（worker 按 clip_tags.json 内容匹配选出），优先使用该顺序；
#  2. 12 天内用过的素材默认不再用（usage.json 记录），除非池子不够用；
#  3. 按上次使用时间（未用过优先）补足，直到覆盖 65 秒或选满 12 条；
#  4. 实际使用的素材记入 usage.json（日期）。
param([Parameter(Mandatory=$true)][string]$ManifestPath)

$ErrorActionPreference = "Continue"
$ProjectRoot = "E:\PerSourceCodeStore\github\chengjinxt\Dramora\MoneyPrinterTurbo\MoneyPrinterTurbo"
$MatRoot    = "E:\PerSourceCodeStore\github\chengjinxt\Dramora\MoneyPrinterTurbo\mpt_materials"
$OutRoot    = "E:\PerSourceCodeStore\github\chengjinxt\Dramora\MoneyPrinterTurbo\mpt_videos"
$Python     = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Ffprobe    = "D:\DevTools\FFmpeg\bin\ffprobe.exe"
$Ffmpeg     = "D:\DevTools\FFmpeg\bin\ffmpeg.exe"
$UsagePath  = Join-Path $MatRoot "usage.json"
$ClipDuration = 8     # 每个素材镜头最多用 8 秒（传给 cli.py 的 --video-clip-duration）
$NeedSeconds  = 65    # 目标覆盖 65 秒（应对最长 60 秒口播 + 余量）
$MaxClips     = 12
$ExcludeDays  = 12     # 12 天内用过的素材不再用

# ---- 用量记录 ----
$usage = @{}
if (Test-Path $UsagePath) {
  try {
    $j = Get-Content $UsagePath -Raw -Encoding utf8 | ConvertFrom-Json
    foreach ($p in $j.PSObject.Properties) {
      $h = @{}
      foreach ($c in $p.Value.PSObject.Properties) { $h[$c.Name] = [string]$c.Value }
      $usage[$p.Name] = $h
    }
  } catch { Write-Output "usage.json 解析失败，从空记录开始" }
}
$today  = (Get-Date).ToString("yyyy-MM-dd")
$cutoff = (Get-Date).AddDays(-$ExcludeDays).ToString("yyyy-MM-dd")

function Get-ClipDuration($fullPath) {
  $d = & $Ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $fullPath 2>$null
  if ($d -match '^[\d\.]+$') { return [double]$d } else { return 0 }
}

function Select-Materials($poolDir, $poolName, $preferredFiles) {
  $poolUsage = $usage[$poolName]
  if ($null -eq $poolUsage) { $poolUsage = @{}; $usage[$poolName] = $poolUsage }

  $allClips = Get-ChildItem $poolDir -Filter *.mp4 | Sort-Object Name
  if ($allClips.Count -eq 0) { return @() }
  $durMap = @{}
  foreach ($c in $allClips) { $durMap[$c.Name] = Get-ClipDuration $c.FullName }

  # 候选顺序：worker 指定的优先（保持其顺序），其余按上次使用日期排（未用过最优先）
  $ordered = @()
  if ($preferredFiles) {
    foreach ($p in $preferredFiles) {
      $name = [System.IO.Path]::GetFileName($p)
      if ($durMap.ContainsKey($name) -and $durMap[$name] -gt 0 -and $ordered -notcontains $name) {
        $ordered += $name
      }
    }
  }
  $rest = $allClips | Where-Object { $ordered -notcontains $_.Name } | Sort-Object {
    $u = $poolUsage[$_.Name]
    if ([string]::IsNullOrEmpty($u)) { "0000-00-00" } else { $u }
  }, Name
  foreach ($c in $rest) { $ordered += $c.Name }

  # 先取 12 天内没用过的
  $take = {
    param($names)
    $sel = @(); $covered = 0.0
    foreach ($name in $names) {
      $sel += $name
      $c = $durMap[$name]; if ($c -lt $ClipDuration) { $covered += $c } else { $covered += $ClipDuration }
      if ($covered -ge $NeedSeconds -or $sel.Count -ge $MaxClips) { break }
    }
    return @{ sel = $sel; covered = $covered }
  }
  $fresh = $ordered | Where-Object {
    $u = $poolUsage[$_]
    [string]::IsNullOrEmpty($u) -or ($u -lt $cutoff)
  }
  $r = & $take $fresh
  $selected = $r.sel; $covered = $r.covered
  if ($covered -lt $NeedSeconds) {
    # 不够用：放宽到全池按 LRU 补
    $r2 = & $take ($ordered | Where-Object { $selected -notcontains $_ })
    $selected = $selected + $r2.sel
  }
  foreach ($name in $selected) { $poolUsage[$name] = $today }
  $names = ($selected | ForEach-Object { $_ }) -join ","
  Write-Output ("选中素材(" + $poolName + "): " + $names)
  return @($selected | ForEach-Object { Join-Path $poolDir $_ })
}

# ---- 主流程 ----
$manifest = Get-Content $ManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$dateStr = $manifest.date
$outDir = Join-Path $OutRoot $dateStr
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$summary = @()
foreach ($v in $manifest.videos) {
  $cat = $v.category
  $title = $v.title
  $safeTitle = ($title -replace '[\\/:*?\"<>|]', '') -replace '\s+', ''
  if ($safeTitle.Length -gt 40) { $safeTitle = $safeTitle.Substring(0, 40) }
  Write-Output "===== 开始生成 [$cat] $title ====="

  $scriptText = Get-Content $v.script_file -Raw -Encoding utf8
  $poolName = Split-Path $v.materials_dir -Leaf
  $preferred = $null
  if ($v.PSObject.Properties.Name -contains "materials" -and $null -ne $v.materials) {
    $preferred = @($v.materials)
  }
  $matFiles = Select-Materials $v.materials_dir $poolName $preferred
  if ($matFiles.Count -eq 0) {
    $summary += "$cat|$title|失败|素材池为空"
    Write-Output "素材池为空，跳过"
    continue
  }
  $materials = $matFiles -join ","

  Set-Location $ProjectRoot
  $out = & $Python cli.py `
    --video-script $scriptText `
    --video-source local `
    --video-materials $materials `
    --video-aspect "9:16" `
    --video-clip-duration $ClipDuration `
    --voice-name "zh-CN-XiaoxiaoNeural" `
    --video-language "zh-CN" `
    --font-name "MicrosoftYaHeiBold.ttc" `
    --text-fore-color "#000000" `
    --subtitle-background-color "#FFE600" `
    --rounded-subtitle-background `
    --stroke-width 0 2>&1 | Out-String

  $m = [regex]::Match($out, '"task_id":\s*"([0-9a-f\-]{36})"')
  if (-not $m.Success) {
    $summary += "$cat|$title|失败|未解析到 task_id"
    Write-Output "未解析到 task_id，跳过"
    continue
  }
  $taskId = $m.Groups[1].Value
  $final = Join-Path $ProjectRoot "storage\tasks\$taskId\final-1.mp4"
  if (-not (Test-Path $final)) {
    $summary += "$cat|$title|失败|final-1.mp4 不存在"
    Write-Output "final-1.mp4 不存在，跳过"
    continue
  }
  $destName = "{0}_{1}.mp4" -f $cat, $safeTitle
  $dest = Join-Path $outDir $destName
  Copy-Item $final $dest -Force

  # ---- 片头标题卡：黄底黑字圆角条（频道风格），覆盖前 3 秒 ----
  $cardPng = Join-Path $outDir "title_card.png"
  & $Python (Join-Path $MatRoot "make_title_card.py") --title $title --output $cardPng 2>&1 | Out-Null
  if (Test-Path $cardPng) {
    $tmpTitled = $dest -replace '\.mp4$', '_titled.mp4'
    & $Ffmpeg -y -i $dest -i $cardPng -filter_complex "[0:v][1:v]overlay=(W-w)/2:(H-h)/2:enable='between(t,0,3)'[v]" -map "[v]" -map 0:a -c:v libx264 -crf 18 -preset veryfast -c:a copy $tmpTitled 2>&1 | Out-Null
    if (Test-Path $tmpTitled) {
      Move-Item $tmpTitled $dest -Force
      Write-Output "已加片头标题卡"
    } else {
      Write-Output "标题卡合成失败，保留原片"
    }
    Remove-Item $cardPng -Force -ErrorAction SilentlyContinue
  } else {
    Write-Output "标题卡生成失败，跳过"
  }
  $dur = & $Ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $dest
  $summary += "$cat|$title|成功|$([math]::Round([double]$dur))秒|$dest"
  Write-Output "完成: $dest"
}

# ---- 保存用量记录 ----
$usage | ConvertTo-Json -Depth 5 | Set-Content $UsagePath -Encoding utf8
Write-Output "用量记录已保存: $UsagePath"

Write-Output "===== DAILY_SUMMARY_BEGIN ====="
$summary | ForEach-Object { Write-Output $_ }
Write-Output "===== DAILY_SUMMARY_END ====="
