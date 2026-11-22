param(
  [Parameter(Mandatory=$true)][string]$Target,
  [Parameter(Mandatory=$true)][string]$Package
)
$ErrorActionPreference = 'Stop'
$Target = ([string]$Target).Trim([char]34)
$Package = ([string]$Package).Trim([char]34).TrimEnd([char]92)
$targetDir = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($Target))
$logDir = Join-Path $env:LOCALAPPDATA 'VideoStudyosu'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'update.log'
function Log([string]$m) { Add-Content -LiteralPath $log -Encoding UTF8 -Value "[$(Get-Date -Format o)] $m" }
function Resolve-SafePath([string]$root, [string]$relative) {
  if ([string]::IsNullOrWhiteSpace($relative)) { throw 'Yama dosya yolu bos.' }
  $normalized = $relative.Replace('/', '\')
  if ([System.IO.Path]::IsPathRooted($normalized)) { throw "Mutlak yama yolu reddedildi: $relative" }
  foreach ($segment in $normalized.Split('\')) {
    if ([string]::IsNullOrWhiteSpace($segment) -or $segment -eq '.' -or $segment -eq '..') { throw "Gecersiz yama yolu parcasi: $relative" }
    if ($segment.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0) { throw "Dosya adinda Windows tarafindan kabul edilmeyen karakter var: $relative" }
  }
  $rootFull = [System.IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
  $full = [System.IO.Path]::GetFullPath((Join-Path $rootFull $normalized))
  if (-not $full.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Yama hedef klasorunun disina cikiyor: $relative" }
  return $full
}
$backup = Join-Path $logDir ('UpdateBackups\' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$changed = New-Object System.Collections.Generic.List[object]
try {
  Log "Patch start. Target=[$Target] Package=[$Package]"
  $manifest = Get-Content -LiteralPath (Join-Path $Package 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  if (-not $manifest.files -or $manifest.files.Count -lt 1) { throw 'Yama manifest dosyasi bos.' }
  $validated = New-Object System.Collections.Generic.List[object]
  foreach ($item in $manifest.files) {
    $rel = [string]$item.path
    try {
      $src = Resolve-SafePath (Join-Path $Package 'payload') $rel
      $dst = Resolve-SafePath $targetDir $rel
      if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw 'Paket icerisinde dosya bulunamadi.' }
      $actual = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLowerInvariant()
      if ($actual -ne ([string]$item.sha256).ToLowerInvariant()) { throw 'SHA256 dogrulamasi basarisiz.' }
      $validated.Add([pscustomobject]@{ Relative=$rel; Source=$src; Destination=$dst })
    } catch { throw "Yama dosyasi kontrol edilemedi [$rel]: $($_.Exception.Message)" }
  }
  $unlocked = $false
  for ($i=0; $i -lt 40; $i++) {
    try {
      if (Test-Path -LiteralPath $Target) {
        $stream = [System.IO.File]::Open($Target,[System.IO.FileMode]::Open,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None)
        $stream.Dispose()
      }
      $unlocked = $true
      break
    } catch { Start-Sleep -Milliseconds 750 }
  }
  if (-not $unlocked) { throw 'Program dosyasi hala kullanimda. Programi tamamen kapatip tekrar deneyin.' }
  New-Item -ItemType Directory -Force -Path $backup | Out-Null
  foreach ($entry in $validated) {
    $rel = $entry.Relative
    $dst = $entry.Destination
    $bak = Resolve-SafePath $backup $rel
    $existed = Test-Path -LiteralPath $dst -PathType Leaf
    if ($existed) {
      New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($bak)) | Out-Null
      [System.IO.File]::Copy($dst,$bak,$true)
    }
    $changed.Add([pscustomobject]@{ Destination=$dst; Backup=$bak; Existed=$existed; Relative=$rel })
    New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($dst)) | Out-Null
    [System.IO.File]::Copy($entry.Source,$dst,$true)
    $check = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()
    $expected = (Get-FileHash -LiteralPath $entry.Source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($check -ne $expected) { throw "Kurulum dogrulamasi basarisiz: $rel" }
    Log "Applied: $rel"
  }
  Log ("PATCH SUCCESS: " + $manifest.from_version + " -> " + $manifest.to_version + "; files=" + $changed.Count)
  if ($env:VIDEO_STUDYOSU_NO_LAUNCH -ne '1') { Start-Process -FilePath $Target }
  exit 0
} catch {
  $failure = $_.Exception.Message
  Log ("PATCH FAILED: " + $failure)
  $rollback = $changed.ToArray()
  [array]::Reverse($rollback)
  foreach ($entry in $rollback) {
    try {
      if ($entry.Existed -and (Test-Path -LiteralPath $entry.Backup -PathType Leaf)) {
        New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($entry.Destination)) | Out-Null
        [System.IO.File]::Copy($entry.Backup,$entry.Destination,$true)
      } elseif (Test-Path -LiteralPath $entry.Destination -PathType Leaf) { Remove-Item -LiteralPath $entry.Destination -Force }
      Log "Rollback: $($entry.Relative)"
    } catch { Log "ROLLBACK ERROR [$($entry.Relative)]: $($_.Exception.Message)" }
  }
  Log 'Rollback finished.'
  if ($env:VIDEO_STUDYOSU_NO_UI -ne '1') {
    try {
      Add-Type -AssemblyName System.Windows.Forms
      $nl = [Environment]::NewLine
      $message = 'Yama uygulanamadi; eski dosyalar geri yuklendi.' + $nl + $nl + 'Hata: ' + $failure + $nl + $nl + 'Ayrinti: ' + $log
      [System.Windows.Forms.MessageBox]::Show($message,'Video Studyosu guncelleme','OK','Error') | Out-Null
    } catch { }
  }
  exit 1
}
