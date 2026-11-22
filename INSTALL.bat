@echo off
setlocal
chcp 65001 >nul
set "APPDIR=%LOCALAPPDATA%\VideoStudyosu"
set "SOURCE=%~dp0Video Studyosu"
set "EXE=%APPDIR%\Video Studyosu.exe"
if not exist "%SOURCE%\Video Studyosu.exe" (
  echo Video Studyosu runtime folder is missing.
  pause
  exit /b 10
)
if not exist "%APPDIR%" mkdir "%APPDIR%"
robocopy "%SOURCE%" "%APPDIR%" /E /R:2 /W:1
if errorlevel 8 (
  echo Program files could not be copied.
  pause
  exit /b 11
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Video Studyosu.lnk'); $s.TargetPath='%EXE%'; $s.WorkingDirectory='%APPDIR%'; $s.Description='Video Studyosu'; $s.Save()"
if errorlevel 1 (
  echo Shortcut could not be created.
  pause
  exit /b 12
)
start "" "%EXE%"
echo Installation complete.
exit /b 0
