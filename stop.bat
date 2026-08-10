@echo off
REM ATECH NOC Commander - Stop Script for Windows

echo ==========================================
echo   Stopping ATECH NOC Commander...
echo ==========================================

REM Kill backend process
echo Stopping backend...
taskkill /f /fi "WINDOWTITLE eq ATECH-Backend" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Backend stopped
) else (
    REM Try to kill python uvicorn
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":8001" ^| find "LISTENING"') do (
        taskkill /f /pid %%a >nul 2>&1
    )
    echo [OK] Backend process terminated
)

REM Kill frontend process
echo Stopping frontend...
taskkill /f /fi "WINDOWTITLE eq ATECH-Frontend" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Frontend stopped
) else (
    REM Try to kill python http.server on port 3000
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":3000" ^| find "LISTENING"') do (
        taskkill /f /pid %%a >nul 2>&1
    )
    echo [OK] Frontend process terminated
)

echo.
echo ATECH NOC Commander stopped.
echo.
echo Note: MongoDB service is still running.
echo To stop MongoDB: net stop MongoDB
echo.
pause
