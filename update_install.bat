@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Video Studyosu - Guncelleme

set "SOURCE="
for /r "%~dp0" %%F in ("Video Studyosu.exe") do (
  if not defined SOURCE set "SOURCE=%%~fF"
)

set "TARGET=%~1"
if not defined TARGET set "TARGET=%LOCALAPPDATA%\VideoStudyosu\Video Studyosu.exe"

echo Video Studyosu guncelleniyor...
if not defined SOURCE (
  echo HATA: Yeni program dosyasi bulunamadi.
  echo Guncelleme klasoru: %~dp0
  pause
  exit /b 10
)

for %%I in ("%TARGET%") do set "TARGETDIR=%%~dpI"
if not exist "%TARGETDIR%" mkdir "%TARGETDIR%"

set "UPDATE_SOURCE=%SOURCE%"
set "UPDATE_TARGET=%TARGET%"
set "UPDATE_BACKUP=%TARGET%.backup"
set "PS1=%TEMP%\VideoStudyosuUpdate_%RANDOM%.ps1"

(
  echo $ErrorActionPreference = 'Stop'
  echo $src = $env:UPDATE_SOURCE
  echo $dst = $env:UPDATE_TARGET
  echo $bak = $env:UPDATE_BACKUP
  echo Start-Sleep -Seconds 3
  echo $copied = $false
  echo for ^($i = 0; $i -lt 25; $i++^) {
  echo   try {
  echo     if ^(Test-Path -LiteralPath $dst^) { Copy-Item -LiteralPath $dst -Destination $bak -Force }
  echo     Copy-Item -LiteralPath $src -Destination $dst -Force
  echo     $copied = $true
  echo     break
  echo   } catch { Start-Sleep -Milliseconds 800 }
  echo }
  echo if ^(-not $copied^) { throw 'Yeni EXE hedefe kopyalanamadi. Program tamamen kapali mi kontrol edin.' }
  echo Start-Process -FilePath $dst
  echo Start-Sleep -Seconds 2
  echo Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
) > "%PS1%"

echo Guncelleme uygulanacak:
echo "%SOURCE%"
echo "%TARGET%"
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
exit /b 0
