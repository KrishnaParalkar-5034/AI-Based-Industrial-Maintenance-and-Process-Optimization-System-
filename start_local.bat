@echo off
title Tennessee Eastman Process (TEP) - Local Services Launcher
color 0B

echo ===============================================================================
echo   Tennessee Eastman Process (TEP) Industrial AI Platform
echo   Launching Decoupled Backend & Frontend Services in Native Windows Mode
echo ===============================================================================
echo.

:: 1. Verify Python availability
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not on PATH. Please install Python 3.11+.
    pause
    exit /b 1
)

:: 2. Verify Node / npm availability
npm --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js / npm is not installed or not on PATH. Please install Node.js 20+.
    pause
    exit /b 1
)

:: 3. Launch Backend FastAPI server in a dedicated window
echo [1/3] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "TEP Backend (FastAPI :8000)" cmd /k "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

:: 4. Launch Frontend Vite development server in a dedicated window
echo [2/3] Starting Vite Frontend on http://localhost:3000 ...
start "TEP Frontend (Vite :3000)" cmd /k "npm --prefix frontend run dev"

:: 5. Brief pause to allow listeners to bind
echo [3/3] Waiting for services to initialize...
timeout /t 3 /nobreak >nul

:: 6. Launch browser
echo Opening Control-Room Web Console at http://localhost:3000 ...
start http://localhost:3000

echo.
echo ===============================================================================
echo   TEP AI Industrial Platform Running Successfully!
echo   - Frontend: http://localhost:3000
echo   - Backend API Docs: http://127.0.0.1:8000/docs
echo   - Prometheus Metrics: http://127.0.0.1:8000/metrics
echo   Close the respective terminal windows to terminate each service.
echo ===============================================================================
echo.
pause
