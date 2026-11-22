param(
  [Parameter(Mandatory=$true)][string]$Target,
  [Parameter(Mandatory=$true)][string]$Package
)
$ErrorActionPreference = 'Stop'
$Target = ([string]$Target).Trim([char]34)
$Package = ([string]$Package).Trim([char]34)
$Target = [System.IO.Path]::GetFullPath($Target)
$targetDir = [System.IO.Path]::GetDirectoryName($Target)
$logDir = Join-Path $env:LOCALAPPDATA 'VideoStudyosu'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'update.log'
function Write-Log([string]$Message) {
  Add-Content -LiteralPath $log -Encoding UTF8 -Value "[$(Get-Date -Format o)] $Message"
}
function Get-Sha256Hex([string]$Path) {
  $algorithm = [System.Security.Cryptography.SHA256]::Create()
  $stream = [System.IO.File]::OpenRead($Path)
  try {
    return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
  } finally {
    $stream.Dispose()
    $algorithm.Dispose()
  }
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$backupRoot = Join-Path $logDir ("FullUpdateBackups\" + $stamp)
$backupExe = Join-Path $backupRoot 'Video Studyosu.exe'
$backupRuntime = Join-Path $backupRoot '_internal'
$runtimeTarget = Join-Path $targetDir '_internal'
$stageRoot = Join-Path $env:TEMP ("VideoStudyosuStage_" + [guid]::NewGuid().ToString('N'))
$hadExe = Test-Path -LiteralPath $Target -PathType Leaf
$hadRuntime = Test-Path -LiteralPath $runtimeTarget -PathType Container
$exitCode = 0
try {
  Write-Log "Full update start. Target=[$Target] Package=[$Package]"
  $sourceFile = Get-ChildItem -LiteralPath $Package -Filter 'Video Studyosu.exe' -File -Recurse |
    Where-Object { $_.Directory.Name -eq 'Video Studyosu' } |
    Select-Object -First 1
  if (-not $sourceFile) { throw 'Update EXE not found in extracted package.' }
  $sourceExe = $sourceFile.FullName
  $sourceRuntime = Join-Path $sourceFile.Directory.FullName '_internal'
  if (-not (Test-Path -LiteralPath $sourceRuntime -PathType Container)) { throw 'New runtime folder _internal is missing from package.' }

  New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
  $stagedExe = Join-Path $stageRoot 'Video Studyosu.exe'
  $stagedRuntime = Join-Path $stageRoot '_internal'
  Copy-Item -LiteralPath $sourceExe -Destination $stagedExe -Force
  Copy-Item -LiteralPath $sourceRuntime -Destination $stagedRuntime -Recurse -Force
  if (-not (Test-Path -LiteralPath $stagedExe -PathType Leaf)) { throw 'Staged update EXE is missing.' }
  if (-not (Test-Path -LiteralPath $stagedRuntime -PathType Container)) { throw 'Staged runtime folder is missing.' }

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
  if (-not $unlocked) { throw 'Old application is still running or the target file is locked.' }

  New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
  if ($hadExe) { Copy-Item -LiteralPath $Target -Destination $backupExe -Force }
  if ($hadRuntime) { Copy-Item -LiteralPath $runtimeTarget -Destination $backupRuntime -Recurse -Force }

  Copy-Item -LiteralPath $stagedExe -Destination $Target -Force
  if (Test-Path -LiteralPath $runtimeTarget) { Remove-Item -LiteralPath $runtimeTarget -Recurse -Force }
  Copy-Item -LiteralPath $stagedRuntime -Destination $runtimeTarget -Recurse -Force

  $actualExeHash = Get-Sha256Hex $Target
  $expectedExeHash = Get-Sha256Hex $stagedExe
  if ($actualExeHash -ne $expectedExeHash) { throw 'Full update EXE hash verification failed.' }
  if (-not (Test-Path -LiteralPath $runtimeTarget -PathType Container)) { throw 'Updated runtime folder was not copied.' }
  Write-Log 'FULL UPDATE SUCCESS: executable and runtime copied and verified.'
  if ($env:VIDEO_STUDYOSU_NO_LAUNCH -ne '1') { Start-Process -FilePath $Target }
} catch {
  $failure = $_.Exception.Message
  Write-Log "FULL UPDATE FAILED: $failure"
  try {
    if ($hadExe -and (Test-Path -LiteralPath $backupExe -PathType Leaf)) {
      Copy-Item -LiteralPath $backupExe -Destination $Target -Force
      Write-Log 'Full update executable rollback completed.'
    } elseif (-not $hadExe -and (Test-Path -LiteralPath $Target -PathType Leaf)) {
      Remove-Item -LiteralPath $Target -Force
      Write-Log 'New executable removed during rollback.'
    }
    if ($hadRuntime -and (Test-Path -LiteralPath $backupRuntime -PathType Container)) {
      if (Test-Path -LiteralPath $runtimeTarget) { Remove-Item -LiteralPath $runtimeTarget -Recurse -Force }
      Copy-Item -LiteralPath $backupRuntime -Destination $runtimeTarget -Recurse -Force
      Write-Log 'Full update runtime rollback completed.'
    } elseif (-not $hadRuntime -and (Test-Path -LiteralPath $runtimeTarget)) {
      Remove-Item -LiteralPath $runtimeTarget -Recurse -Force
    }
  } catch { Write-Log "FULL UPDATE ROLLBACK ERROR: $($_.Exception.Message)" }
  if ($env:VIDEO_STUDYOSU_NO_UI -ne '1') {
    try {
      Add-Type -AssemblyName System.Windows.Forms
      [System.Windows.Forms.MessageBox]::Show("Update failed: $failure. Old files were restored where possible. Log: $log",'Video Studyosu updater','OK','Error') | Out-Null
    } catch { }
  }
  $exitCode = 1
} finally {
  if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
exit $exitCode
