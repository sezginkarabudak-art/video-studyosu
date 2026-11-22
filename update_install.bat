@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Video Studyosu - Guncelleme
set "TARGET=%~1"
if exist "%~dp0manifest.json" goto :PATCH_INSTALL
if not defined TARGET set "TARGET=%LOCALAPPDATA%\VideoStudyosu\Video Studyosu.exe"
for %%I in ("%TARGET%") do set "TARGETDIR=%%~dpI"
if not exist "%TARGETDIR%" mkdir "%TARGETDIR%"
set "UPDATE_TARGET=%TARGET%"
set "UPDATE_PACKAGE=%~dp0"
set "PS1=%TEMP%\VideoStudyosuUpdate_%RANDOM%.ps1"
(
  echo $ErrorActionPreference = 'Stop'
  echo $logDir = Join-Path $env:LOCALAPPDATA 'VideoStudyosu'
  echo New-Item -ItemType Directory -Force -Path $logDir ^| Out-Null
  echo $log = Join-Path $logDir 'update.log'
  echo function Write-Log^($m^) { Add-Content -LiteralPath $log -Encoding UTF8 -Value ^("[$(Get-Date -Format o)] $m"^) }
  echo try {
  echo   $src = Get-ChildItem -LiteralPath $env:UPDATE_PACKAGE -Filter 'Video Studyosu.exe' -File -Recurse ^| Where-Object { $_.Directory.Name -eq 'Video Studyosu' } ^| Select-Object -First 1 -ExpandProperty FullName
  echo   $dst = $env:UPDATE_TARGET
  echo   Write-Log "Updater started. Source=[$src] Target=[$dst]"
  echo   if ^(-not $src^) { throw 'Update EXE not found in extracted package.' }
  echo   $src = ([string]$src).Trim([char]34)
  echo   $dst = ([string]$dst).Trim([char]34)
  echo   if ^(-not ^(Test-Path -LiteralPath $src -PathType Leaf^)^) { throw "Update EXE not found: $src" }
  echo   $dstDir = Split-Path -Parent $dst
  echo   New-Item -ItemType Directory -Force -Path $dstDir ^| Out-Null
  echo   $srcDir = Split-Path -Parent $src
  echo   $internal = Join-Path $srcDir '_internal'
  echo   if ^(-not ^(Test-Path -LiteralPath $internal -PathType Container^)^) { throw 'New runtime folder _internal is missing from package.' }
  echo   $unlocked = $false
  echo   for ^($i=0; $i -lt 40; $i++^) {
  echo     try {
  echo       if ^(Test-Path -LiteralPath $dst^) {
  echo         $fs = [System.IO.File]::Open^($dst, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None^)
  echo         $fs.Dispose^(^)
  echo       }
  echo       $unlocked = $true
  echo       break
  echo     } catch { Start-Sleep -Milliseconds 750 }
  echo   }
  echo   if ^(-not $unlocked^) { throw 'Old application is still running or the target file is locked.' }
  echo   Copy-Item -Path (Join-Path $srcDir '*') -Destination $dstDir -Recurse -Force
  echo   if ^(-not ^(Test-Path -LiteralPath $dst -PathType Leaf^)^) { throw 'Updated application EXE was not copied.' }
  echo   if ^(-not ^(Test-Path -LiteralPath (Join-Path $dstDir '_internal') -PathType Container^)^) { throw 'Updated runtime folder was not copied.' }
  echo   Write-Log "EXE replaced successfully. Bytes=$((Get-Item -LiteralPath $dst).Length)"
  echo   if ^($env:VIDEO_STUDYOSU_NO_LAUNCH -ne '1'^) { Start-Process -FilePath $dst }
  echo   Write-Log 'New application copied and verified.'
  echo } catch {
  echo   $msg = $_.Exception.Message
  echo   Write-Log "FAILED: $msg"
  echo   if ^($env:VIDEO_STUDYOSU_NO_UI -ne '1'^) {
  echo     Add-Type -AssemblyName System.Windows.Forms
  echo     [System.Windows.Forms.MessageBox]::Show^("Update failed: $msg. Log: $log", 'Video Studyosu updater', 'OK', 'Error'^) ^| Out-Null
  echo   }
  echo }
  echo Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
) > "%PS1%"
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
exit /b 0

:PATCH_INSTALL
if not defined TARGET set "TARGET=%LOCALAPPDATA%\VideoStudyosu\Video Studyosu.exe"
rem IMPORTANT: use %~dp0. so the argument does not end in a backslash before
rem the closing quote; Windows command-line parsing can otherwise retain the quote.
set "PACKAGE_DIR=%~dp0."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply_patch.ps1" -Target "%TARGET%" -Package "%PACKAGE_DIR%"
exit /b %errorlevel%
