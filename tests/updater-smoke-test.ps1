$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$tempRoot = Join-Path $env:TEMP ("Video Studyosu Updater Smoke " + [guid]::NewGuid().ToString("N"))
$originalNoLaunch = $env:VIDEO_STUDYOSU_NO_LAUNCH
$originalNoUi = $env:VIDEO_STUDYOSU_NO_UI
$env:VIDEO_STUDYOSU_NO_LAUNCH = '1'
$env:VIDEO_STUDYOSU_NO_UI = '1'

function Assert-True([bool]$condition, [string]$message) {
  if (-not $condition) { throw $message }
}
function Write-Manifest([string]$path, [object[]]$files) {
  $manifest = [ordered]@{
    from_version = '1.0.0'
    to_version = '1.0.1'
    files = $files
  }
  $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8
}
function Invoke-UpdaterBatch([string]$batchPath, [string]$targetPath) {
  & $batchPath $targetPath
  return $LASTEXITCODE
}
try {
  $whereExe = Join-Path $env:WINDIR 'System32\where.exe'
  $whoamiExe = Join-Path $env:WINDIR 'System32\whoami.exe'
  Assert-True (Test-Path -LiteralPath $whereExe) 'Windows test utility where.exe is missing.'
  Assert-True (Test-Path -LiteralPath $whoamiExe) 'Windows test utility whoami.exe is missing.'

  # 1) Patch success: exercise the actual BAT -> PowerShell path with spaces.
  $patchPackage = Join-Path $tempRoot 'Patch Package With Spaces'
  $patchTargetDir = Join-Path $tempRoot 'Installed App With Spaces'
  $patchPayload = Join-Path $patchPackage 'payload'
  New-Item -ItemType Directory -Force -Path $patchPayload, $patchTargetDir | Out-Null
  Copy-Item -LiteralPath (Join-Path $repoRoot 'update_install.bat') -Destination $patchPackage
  Copy-Item -LiteralPath (Join-Path $repoRoot 'apply_patch.ps1') -Destination $patchPackage
  $patchTarget = Join-Path $patchTargetDir 'Video Studyosu.exe'
  Copy-Item -LiteralPath $whoamiExe -Destination $patchTarget
  $patchSource = Join-Path $patchPayload 'Video Studyosu.exe'
  Copy-Item -LiteralPath $whereExe -Destination $patchSource
  $patchHash = (Get-FileHash -LiteralPath $patchSource -Algorithm SHA256).Hash.ToLowerInvariant()
  Write-Manifest (Join-Path $patchPackage 'manifest.json') @(
    @{ path = 'Video Studyosu.exe'; sha256 = $patchHash }
  )
  $patchExit = Invoke-UpdaterBatch (Join-Path $patchPackage 'update_install.bat') $patchTarget
  Assert-True ($patchExit -eq 0) "Patch success scenario returned exit code $patchExit."
  $installedHash = (Get-FileHash -LiteralPath $patchTarget -Algorithm SHA256).Hash.ToLowerInvariant()
  Assert-True ($installedHash -eq $patchHash) 'Patch success scenario did not install the expected file hash.'
  Write-Host 'PASS: patch installer handles package/target paths with spaces and verifies the copied hash.'

  # 2) Patch rollback: force a destination-directory conflict after the first file was copied.
  $rollbackTargetHashBefore = (Get-FileHash -LiteralPath $patchTarget -Algorithm SHA256).Hash.ToLowerInvariant()
  $rollbackSource = Join-Path $patchPayload 'Video Studyosu.exe'
  Copy-Item -LiteralPath $whoamiExe -Destination $rollbackSource -Force
  $rollbackHash = (Get-FileHash -LiteralPath $rollbackSource -Algorithm SHA256).Hash.ToLowerInvariant()
  $blockedSourceDir = Join-Path $patchPayload 'blocked'
  New-Item -ItemType Directory -Force -Path $blockedSourceDir | Out-Null
  $blockedSource = Join-Path $blockedSourceDir 'second.txt'
  Set-Content -LiteralPath $blockedSource -Value 'forces rollback' -Encoding UTF8
  $blockedHash = (Get-FileHash -LiteralPath $blockedSource -Algorithm SHA256).Hash.ToLowerInvariant()
  $blockedTarget = Join-Path $patchTargetDir 'blocked'
  Set-Content -LiteralPath $blockedTarget -Value 'this is a file, not a directory' -Encoding UTF8
  Write-Manifest (Join-Path $patchPackage 'manifest.json') @(
    @{ path = 'Video Studyosu.exe'; sha256 = $rollbackHash },
    @{ path = 'blocked/second.txt'; sha256 = $blockedHash }
  )
  $rollbackExit = Invoke-UpdaterBatch (Join-Path $patchPackage 'update_install.bat') $patchTarget
  Assert-True ($rollbackExit -ne 0) 'Rollback scenario unexpectedly returned success.'
  $rollbackTargetHashAfter = (Get-FileHash -LiteralPath $patchTarget -Algorithm SHA256).Hash.ToLowerInvariant()
  Assert-True ($rollbackTargetHashAfter -eq $rollbackTargetHashBefore) 'Rollback did not restore the original executable.'
  Write-Host 'PASS: patch failure rolls back the previously replaced file.'

  # 3) Full installer: verify package discovery works when the batch and package path contain spaces.
  $fullPackage = Join-Path $tempRoot 'Full Update Package With Spaces'
  $fullAppDir = Join-Path $fullPackage 'Video Studyosu'
  $fullRuntime = Join-Path $fullAppDir '_internal'
  $fullTargetDir = Join-Path $tempRoot 'Full Install Target With Spaces'
  New-Item -ItemType Directory -Force -Path $fullRuntime, $fullTargetDir | Out-Null
  Copy-Item -LiteralPath (Join-Path $repoRoot 'update_install.bat') -Destination $fullPackage
  Copy-Item -LiteralPath $whereExe -Destination (Join-Path $fullAppDir 'Video Studyosu.exe')
  Set-Content -LiteralPath (Join-Path $fullRuntime 'smoke-marker.txt') -Value 'full-update-ok' -Encoding UTF8
  $fullTarget = Join-Path $fullTargetDir 'Video Studyosu.exe'
  Copy-Item -LiteralPath $whoamiExe -Destination $fullTarget
  $fullExit = Invoke-UpdaterBatch (Join-Path $fullPackage 'update_install.bat') $fullTarget
  Assert-True ($fullExit -eq 0) "Full installer batch returned exit code $fullExit."
  $expectedFullHash = (Get-FileHash -LiteralPath (Join-Path $fullAppDir 'Video Studyosu.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
  $deadline = (Get-Date).AddSeconds(60)
  $fullReady = $false
  while ((Get-Date) -lt $deadline) {
    if ((Test-Path -LiteralPath $fullTarget) -and
        (Test-Path -LiteralPath (Join-Path $fullTargetDir '_internal\smoke-marker.txt'))) {
      $actualFullHash = (Get-FileHash -LiteralPath $fullTarget -Algorithm SHA256).Hash.ToLowerInvariant()
      if ($actualFullHash -eq $expectedFullHash) { $fullReady = $true; break }
    }
    Start-Sleep -Milliseconds 500
  }
  Assert-True $fullReady 'Full installer did not copy the executable and runtime files within 60 seconds.'
  Write-Host 'PASS: full installer finds its extracted package and copies EXE/runtime to a path containing spaces.'
  Write-Host 'ALL WINDOWS UPDATER SMOKE TESTS PASSED.'
}
finally {
  if ($null -eq $originalNoLaunch) { Remove-Item Env:VIDEO_STUDYOSU_NO_LAUNCH -ErrorAction SilentlyContinue } else { $env:VIDEO_STUDYOSU_NO_LAUNCH = $originalNoLaunch }
  if ($null -eq $originalNoUi) { Remove-Item Env:VIDEO_STUDYOSU_NO_UI -ErrorAction SilentlyContinue } else { $env:VIDEO_STUDYOSU_NO_UI = $originalNoUi }
  if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
