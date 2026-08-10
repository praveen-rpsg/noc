@echo off
REM ATECH NOC Commander - Start Script for Windows

echo ==========================================
echo   Starting ATECH NOC Commander...
echo ==========================================

set "SCRIPT_DIR=%~dp0"

REM Create directories if they don't exist
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"
if not exist "%SCRIPT_DIR%pids" mkdir "%SCRIPT_DIR%pids"

REM Check MongoDB service
echo Checking MongoDB...
sc query MongoDB | find "RUNNING" >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting MongoDB service...
    net start MongoDB >nul 2>&1
    if %errorlevel% neq 0 (
        echo [WARNING] Could not start MongoDB service.
        echo [WARNING] Please ensure MongoDB is installed and configured.
    ) else (
        echo [OK] MongoDB started
    )
) else (
    echo [OK] MongoDB is running
)

REM Start backend
echo Starting backend server...
cd /d "%SCRIPT_DIR%backend"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Kill existing backend if running
taskkill /f /fi "WINDOWTITLE eq ATECH-Backend" >nul 2>&1

start "ATECH-Backend" /min cmd /c "python -m uvicorn server:app --host 0.0.0.0 --port 8001 > ..\logs\backend.log 2>&1"
echo [OK] Backend started on port 8001

REM Start frontend
if exist "%SCRIPT_DIR%frontend\build" (
    echo Starting frontend server...
    cd /d "%SCRIPT_DIR%frontend\build"
    
    REM Kill existing frontend if running
    taskkill /f /fi "WINDOWTITLE eq ATECH-Frontend" >nul 2>&1
    
    start "ATECH-Frontend" /min cmd /c "python -m http.server 3000 > ..\..\logs\frontend.log 2>&1"
    echo [OK] Frontend started on port 3000
) else (
    echo [!] Frontend build not found. API available at http://localhost:8001
)

REM Wait for services
timeout /t 3 /nobreak >nul

echo.
echo ==========================================
echo   ATECH NOC Commander is running!
echo ==========================================
echo.
echo   Web Application: http://localhost:3000
echo   API Endpoint:    http://localhost:8001
echo   API Docs:        http://localhost:8001/docs
echo.
echo   Default credentials:
echo     Email:    admin@noc.com
echo     Password: admin123
echo.
echo   Logs: %SCRIPT_DIR%logs\
echo ==========================================
echo.
echo To stop: stop.bat
echo.
pause
