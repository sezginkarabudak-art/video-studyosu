@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Video Studyosu - Guncelleme
set "TARGET=%~1"
if exist "%~dp0manifest.json" goto :PATCH_INSTALL
if not defined TARGET set "TARGET=%LOCALAPPDATA%\VideoStudyosu\Video Studyosu.exe"
set "PACKAGE_DIR=%~dp0."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_full.ps1" -Target "%TARGET%" -Package "%PACKAGE_DIR%"
exit /b %errorlevel%

:PATCH_INSTALL
if not defined TARGET set "TARGET=%LOCALAPPDATA%\VideoStudyosu\Video Studyosu.exe"
rem IMPORTANT: use %~dp0. so the argument does not end in a backslash before
rem the closing quote; Windows command-line parsing can otherwise retain the quote.
set "PACKAGE_DIR=%~dp0."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply_patch.ps1" -Target "%TARGET%" -Package "%PACKAGE_DIR%"
exit /b %errorlevel%
