@echo off
REM ATECH NOC Commander - Windows Installation Script
REM This script installs all dependencies and sets up the application

setlocal enabledelayedexpansion

echo ==========================================
echo   ATECH NOC COMMANDER - INSTALLER
echo   AI-Powered Network Operation Center
echo ==========================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%..\.."

echo Installation directory: %APP_DIR%
echo.

REM Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] This installer requires Administrator privileges.
    echo [!] Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Check for Python
echo Step 1/7: Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python is not installed.
    echo [!] Please download and install Python 3.11+ from https://www.python.org/downloads/
    echo [!] Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo [OK] Python found
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo     Version: %PYTHON_VERSION%
echo.

REM Check for MongoDB
echo Step 2/7: Checking MongoDB installation...
where mongod >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] MongoDB is not installed.
    echo [!] Please download and install MongoDB Community Server from:
    echo [!] https://www.mongodb.com/try/download/community
    echo.
    echo [!] After installation, start MongoDB service:
    echo [!]   net start MongoDB
    echo.
    set /p CONTINUE="Continue without MongoDB? (y/n): "
    if /i "!CONTINUE!" neq "y" (
        exit /b 1
    )
) else (
    echo [OK] MongoDB found
)
echo.

REM Create directories
echo Step 3/7: Creating directories...
if not exist "%APP_DIR%\logs" mkdir "%APP_DIR%\logs"
if not exist "%APP_DIR%\pids" mkdir "%APP_DIR%\pids"
if not exist "%APP_DIR%\mongodb\data" mkdir "%APP_DIR%\mongodb\data"
echo [OK] Directories created
echo.

REM Setup Python virtual environment
echo Step 4/7: Setting up Python environment...
cd /d "%APP_DIR%\backend"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Python dependencies (this may take several minutes)...
pip install --upgrade pip
pip install -r requirements.txt

REM Install emergentintegrations
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>nul

echo [OK] Python dependencies installed
echo.

REM Setup environment files
echo Step 5/7: Setting up environment files...

if not exist "%APP_DIR%\backend\.env" (
    (
        echo # MongoDB Configuration
        echo MONGO_URL=mongodb://localhost:27017
        echo DB_NAME=atech_noc
        echo.
        echo # JWT Configuration
        echo JWT_SECRET_KEY=atech-noc-commander-secret-key-change-in-production
        echo JWT_ALGORITHM=HS256
        echo JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
        echo.
        echo # Server Configuration
        echo HOST=0.0.0.0
        echo PORT=8001
    ) > "%APP_DIR%\backend\.env"
    echo [OK] Created backend\.env
) else (
    echo [!] backend\.env already exists, skipping
)

if not exist "%APP_DIR%\frontend\.env" (
    echo REACT_APP_BACKEND_URL=http://localhost:8001> "%APP_DIR%\frontend\.env"
    echo [OK] Created frontend\.env
) else (
    echo [!] frontend\.env already exists, skipping
)
echo.

REM Create startup scripts
echo Step 6/7: Creating startup scripts...

REM Create start.bat
(
    echo @echo off
    echo echo Starting ATECH NOC Commander...
    echo.
    echo REM Start MongoDB if not running
    echo sc query MongoDB ^| find "RUNNING" ^>nul
    echo if %%errorlevel%% neq 0 ^(
    echo     echo Starting MongoDB...
    echo     net start MongoDB 2^>nul ^|^| mongod --dbpath "%%~dp0mongodb\data" --logpath "%%~dp0mongodb\mongod.log" --fork
    echo ^)
    echo.
    echo REM Start backend
    echo cd /d "%%~dp0backend"
    echo call venv\Scripts\activate.bat
    echo start /b python -m uvicorn server:app --host 0.0.0.0 --port 8001 ^> "..\logs\backend.log" 2^>^&1
    echo echo Backend started on port 8001
    echo.
    echo REM Serve frontend
    echo if exist "%%~dp0frontend\build" ^(
    echo     cd /d "%%~dp0frontend\build"
    echo     start /b python -m http.server 3000 ^> "..\..\logs\frontend.log" 2^>^&1
    echo     echo Frontend started on port 3000
    echo ^)
    echo.
    echo echo.
    echo echo ==========================================
    echo echo   ATECH NOC Commander is running!
    echo echo ==========================================
    echo echo   Web UI: http://localhost:3000
    echo echo   API: http://localhost:8001
    echo echo.
    echo echo   Default login:
    echo echo     Email: admin@noc.com
    echo echo     Password: admin123
    echo echo ==========================================
    echo pause
) > "%APP_DIR%\start.bat"

REM Create stop.bat
(
    echo @echo off
    echo echo Stopping ATECH NOC Commander...
    echo.
    echo REM Kill Python processes
    echo taskkill /f /im python.exe 2^>nul
    echo.
    echo echo ATECH NOC Commander stopped
    echo pause
) > "%APP_DIR%\stop.bat"

echo [OK] Startup scripts created
echo.

REM Create admin user
echo Step 7/7: Creating default admin user...
cd /d "%APP_DIR%\backend"
call venv\Scripts\activate.bat

python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from datetime import datetime, timezone
import uuid
import os

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def create_admin():
    mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.getenv('DB_NAME', 'atech_noc')
    
    try:
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        db = client[db_name]
        
        existing = await db.users.find_one({'email': 'admin@noc.com'})
        if existing:
            print('Admin user already exists')
            return
        
        admin = {
            'id': str(uuid.uuid4()),
            'email': 'admin@noc.com',
            'name': 'Admin User',
            'password_hash': pwd_context.hash('admin123'),
            'role': 'admin',
            'is_active': True,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        await db.users.insert_one(admin)
        print('Admin user created: admin@noc.com / admin123')
        
        client.close()
    except Exception as e:
        print(f'Could not connect to MongoDB: {e}')
        print('Admin user will be created when MongoDB is available')

asyncio.run(create_admin())
"

echo.
echo ==========================================
echo   INSTALLATION COMPLETE!
echo ==========================================
echo.
echo To start the application:
echo   start.bat
echo.
echo To stop the application:
echo   stop.bat
echo.
echo Access the application at:
echo   http://localhost:3000
echo.
echo Default credentials:
echo   Email: admin@noc.com
echo   Password: admin123
echo.
pause
