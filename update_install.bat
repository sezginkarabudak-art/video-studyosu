@echo off
setlocal
chcp 65001 >nul
set "SOURCE=%~dp0Video Studyosu.exe"
set "TARGET=%~1"
if not defined TARGET set "TARGET=%LOCALAPPDATA%\VideoStudyosu\Video Studyosu.exe"
if not exist "%SOURCE%" exit /b 10
for %%I in ("%TARGET%") do set "TARGETDIR=%%~dpI"
if not exist "%TARGETDIR%" mkdir "%TARGETDIR%"
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
