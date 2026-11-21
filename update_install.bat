@echo off
chcp 65001 >nul
setlocal
set "SOURCE=%~dp0Video Studyosu.exe"
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%USERPROFILE%\Desktop\Video Studyosu.exe"
echo Video Studyosu guncelleniyor...
timeout /t 3 /nobreak >nul
if not exist "%SOURCE%" exit /b 1
if exist "%TARGET%" copy /Y "%TARGET%" "%TARGET%.backup" >nul
copy /Y "%SOURCE%" "%TARGET%" >nul
if errorlevel 1 exit /b 1
start "" "%TARGET%"
exit /b 0
