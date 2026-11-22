@echo off
setlocal
chcp 65001 >nul
set "APPDIR=%LOCALAPPDATA%\VideoStudyosu"
set "EXE=%APPDIR%\Video Studyosu.exe"
if not exist "%~dp0Video Studyosu.exe" (
  echo Video Studyosu.exe bulunamadi. Kurulum paketi eksik.
  pause
  exit /b 10
)
if not exist "%APPDIR%" mkdir "%APPDIR%"
copy /Y "%~dp0Video Studyosu.exe" "%EXE%" >nul
if errorlevel 1 (
  echo Program dosyasi kopyalanamadi.
  pause
  exit /b 11
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Video Studyosu.lnk'); $s.TargetPath='%EXE%'; $s.WorkingDirectory='%APPDIR%'; $s.Description='Video Studyosu'; $s.Save()"
if errorlevel 1 (
  echo Kisayol olusturulamadi.
  pause
  exit /b 12
)
start "" "%EXE%"
echo Kurulum tamamlandi.
exit /b 0
