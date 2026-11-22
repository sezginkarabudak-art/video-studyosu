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
echo Aranan yeni dosya: Video Studyosu.exe

if not defined SOURCE (
  echo HATA: Yeni program dosyasi bulunamadi.
  echo Guncelleme klasoru: %~dp0
  echo Beklenen dosya adi: Video Studyosu.exe
  pause
  exit /b 10
)

for %%I in ("%TARGET%") do set "TARGETDIR=%%~dpI"
if not exist "%TARGETDIR%" mkdir "%TARGETDIR%"

echo Yeni dosya: "%SOURCE%"
echo Kurulum yeri: "%TARGET%"
echo Programin kapanmasi bekleniyor...
timeout /t 3 /nobreak >nul

set "BACKUP=%TARGET%.backup"
set "VBS=%TEMP%\VideoStudyosuUpdate_%RANDOM%.vbs"
(
  echo Set sh = CreateObject("WScript.Shell")
  echo WScript.Sleep 1800
  echo Set fso = CreateObject("Scripting.FileSystemObject")
  echo If fso.FileExists("%TARGET%") Then fso.CopyFile "%TARGET%", "%BACKUP%", True
  echo fso.CopyFile "%SOURCE%", "%TARGET%", True
  echo sh.Run Chr(34) ^& "%TARGET%" ^& Chr(34), 1, False
  echo fso.DeleteFile WScript.ScriptFullName
) > "%VBS%"

start "" wscript.exe "%VBS%"
exit /b 0
