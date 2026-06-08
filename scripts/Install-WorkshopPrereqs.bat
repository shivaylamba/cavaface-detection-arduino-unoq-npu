@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Install-WorkshopPrereqs.ps1" %*
if errorlevel 1 (
  echo.
  echo Workshop prerequisite install failed. Review the error above.
  pause
  exit /b %errorlevel%
)
echo.
echo Workshop prerequisite install completed.
pause
