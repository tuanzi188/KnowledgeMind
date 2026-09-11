@echo off
echo ========================================
echo   KnowledgeMind Backend Server
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/2] Killing old processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 3 /nobreak >nul

echo [2/2] Starting backend on http://localhost:8002
echo (Keep this window open)
echo.
start "KnowledgeMind-Backend" /B python -m uvicorn app.main:app --host 0.0.0.0 --port 8002

timeout /t 5 /nobreak >nul
echo Server started!
echo.
echo Test: http://localhost:8002/api/v1/health
echo API:  http://localhost:8002/docs
echo.
echo Press any key to stop server...
pause >nul

taskkill /F /IM python.exe >nul 2>&1
echo Server stopped.