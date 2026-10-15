# 每日 3 条视频批量生成编排脚本
# 用法: powershell -ExecutionPolicy Bypass -File daily_gen.ps1 -ManifestPath E:\...\manifest.json
# manifest.json 格式:
# {
#   "date": "2026-10-16",
#   "videos": [
#     {"category":"健康","title":"每天散步30分钟","script_file":"E:\...\health.txt","materials_dir":"E:\...\mpt_materials\walk"},
#     {"category":"科技","title":"xxx","script_file":"E:\...\tech.txt","materials_dir":"E:\...\mpt_materials\tech"},
#     {"category":"情感","title":"xxx","script_file":"E:\...\emotion.txt","materials_dir":"E:\...\mpt_materials\emotion"}
#   ]
# }
param([Parameter(Mandatory=$true)][string]$ManifestPath)

$ErrorActionPreference = "Continue"
$ProjectRoot = "E:\PerSourceCodeStore\github\chengjinxt\Dramora\MoneyPrinterTurbo\MoneyPrinterTurbo"
$OutRoot = "E:\PerSourceCodeStore\github\chengjinxt\Dramora\MoneyPrinterTurbo\mpt_videos"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$manifest = Get-Content $ManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$dateStr = $manifest.date
$outDir = Join-Path $OutRoot $dateStr
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$summary = @()
foreach ($v in $manifest.videos) {
  $cat = $v.category
  $title = $v.title
  $safeTitle = ($title -replace '[\/:*?"<>|]', '') -replace '\s+', ''
  if ($safeTitle.Length -gt 40) { $safeTitle = $safeTitle.Substring(0, 40) }
  Write-Output "===== 开始生成 [$cat] $title ====="

  $scriptText = Get-Content $v.script_file -Raw -Encoding utf8
  $matFiles = Get-ChildItem $v.materials_dir -Filter *.mp4 | Sort-Object Name | ForEach-Object { $_.FullName }
  if ($matFiles.Count -eq 0) {
    $summary += "$cat|$title|失败|素材目录为空"
    Write-Output "素材目录为空，跳过"
    continue
  }
  $materials = $matFiles -join ","

  Set-Location $ProjectRoot
  $out = & $Python cli.py `
    --video-script $scriptText `
    --video-source local `
    --video-materials $materials `
    --video-aspect "9:16" `
    --voice-name "zh-CN-XiaoxiaoNeural" `
    --video-language "zh-CN" 2>&1 | Out-String

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
  $dur = & D:\DevTools\FFmpeg\bin\ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $dest
  $summary += "$cat|$title|成功|$([math]::Round([double]$dur))秒|$dest"
  Write-Output "完成: $dest"
}

Write-Output "===== DAILY_SUMMARY_BEGIN ====="
$summary | ForEach-Object { Write-Output $_ }
Write-Output "===== DAILY_SUMMARY_END ====="
