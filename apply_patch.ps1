param(
  [Parameter(Mandatory=$true)][string]$Target,
  [Parameter(Mandatory=$true)][string]$Package
)
$ErrorActionPreference = 'Stop'
$targetDir = Split-Path -Parent $Target
$log = Join-Path $env:LOCALAPPDATA 'VideoStudyosu\update.log'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
function Log([string]$m) { Add-Content -LiteralPath $log -Value "[$(Get-Date -Format o)] $m" }
$backup = Join-Path $env:LOCALAPPDATA ('VideoStudyosu\UpdateBackups\' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$changed = New-Object System.Collections.Generic.List[string]
try {
  $manifestPath = Join-Path $Package 'manifest.json'
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if (-not $manifest.files -or $manifest.files.Count -lt 1) { throw 'Yama manifest dosyası boş.' }
  for ($i=0; $i -lt 40; $i++) {
    try {
      if (Test-Path -LiteralPath $Target) {
        $stream = [System.IO.File]::Open($Target,[System.IO.FileMode]::Open,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None)
        $stream.Dispose()
      }
      break
    } catch { Start-Sleep -Milliseconds 750 }
  }
  if (Test-Path -LiteralPath $Target) {
    try { $stream = [System.IO.File]::Open($Target,[System.IO.FileMode]::Open,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None); $stream.Dispose() }
    catch { throw 'Program dosyası kilitli. Program tamamen kapatılmadı.' }
  }
  foreach ($item in $manifest.files) {
    $rel = [string]$item.path
    if ([string]::IsNullOrWhiteSpace($rel) -or $rel.Contains('..') -or [System.IO.Path]::IsPathRooted($rel)) { throw "Geçersiz yama yolu: $rel" }
    $src = Join-Path (Join-Path $Package 'payload') $rel
    $dst = Join-Path $targetDir $rel
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "Yama dosyası eksik: $rel" }
    $actual = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne ([string]$item.sha256).ToLowerInvariant()) { throw "Yama dosyası doğrulanamadı: $rel" }
  }
  New-Item -ItemType Directory -Force -Path $backup | Out-Null
  foreach ($item in $manifest.files) {
    $rel = [string]$item.path
    $src = Join-Path (Join-Path $Package 'payload') $rel
    $dst = Join-Path $targetDir $rel
    $bak = Join-Path $backup $rel
    if (Test-Path -LiteralPath $dst -PathType Leaf) {
      New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bak) | Out-Null
      Copy-Item -LiteralPath $dst -Destination $bak -Force
    }
    $changed.Add($rel)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
    $check = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($check -ne ([string]$item.sha256).ToLowerInvariant()) { throw "Kurulum doğrulaması başarısız: $rel" }
  }
  Log ("Patch applied: " + $manifest.from_version + " -> " + $manifest.to_version + "; files=" + $changed.Count)
  Start-Process -FilePath $Target
  exit 0
} catch {
  $failure = $_.Exception.Message
  Log ("PATCH FAILED: " + $failure)
  $rollback = $changed.ToArray()
  [array]::Reverse($rollback)
  foreach ($rel in $rollback) {
    $dst = Join-Path $targetDir $rel
    $bak = Join-Path $backup $rel
    if (Test-Path -LiteralPath $bak -PathType Leaf) {
      New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
      Copy-Item -LiteralPath $bak -Destination $dst -Force
    } elseif (Test-Path -LiteralPath $dst -PathType Leaf) { Remove-Item -LiteralPath $dst -Force }
  }
  Log 'Rollback finished.'
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.MessageBox]::Show(("Yama uygulanamadı; eski dosyalar geri yüklendi." + [Environment]::NewLine + $failure),"Video Studyosu güncelleme",'OK','Error') | Out-Null
  exit 1
}