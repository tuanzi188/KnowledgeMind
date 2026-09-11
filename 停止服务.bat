@echo off
chcp 65001 >nul
title 停止 KnowledgeMind 服务

echo ============================================
echo   停止 KnowledgeMind 服务
echo ============================================
echo.

:: 检查 Python 进程
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [INFO] 正在停止后端服务...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
    echo ✅ 服务已停止
) else (
    echo ℹ️  未发现运行中的服务
)

echo.
pause
