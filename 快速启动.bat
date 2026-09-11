@echo off
chcp 65001 >nul
title KnowledgeMind - 企业智能知识库

echo ============================================
echo   KnowledgeMind - 快速启动脚本
echo ============================================
echo.

:: 检查是否已在运行
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [INFO] 检测到 Python 进程正在运行，尝试停止...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
)

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Python，请安装 Python 3.11+
    pause
    exit /b 1
)

:: 检查 .env 文件
if not exist backend\.env (
    echo [INFO] 未检测到 .env 文件，正在从模板创建...
    copy backend\.env.example backend\.env
    echo [WARN] 请编辑 backend\.env 填入你的 DeepSeek API Key
)

:: 启动后端（最小化窗口）
echo [1/3] 正在启动后端服务...
start /min "KnowledgeMind-Backend" cmd /c "cd /d %~dp0backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8002"

:: 等待启动
echo [2/3] 等待服务就绪...
set /a max_attempts=20
set /a attempt=0

:check_loop
set /a attempt+=1
if %attempt% gtr %max_attempts% (
    echo [ERROR] 启动超时，请检查端口 8002 是否被占用
    pause
    exit /b 1
)

:: 健康检查
curl -s -o nul -w "%%{http_code}" http://localhost:8002/ >nul 2>&1
if %errorlevel% neq 0 (
    echo 等待中... (%attempt%/%max_attempts%)
    timeout /t 1 /nobreak >nul
    goto check_loop
)

echo [3/3] 服务启动成功！
echo.
echo ============================================
echo   🎉 启动完成！
echo.
echo   🌐 访问地址: http://localhost:8002
echo   📚 API 文档: http://localhost:8002/docs
echo ============================================
echo.
echo 正在自动打开浏览器...
timeout /t 1 /nobreak >nul

:: 自动打开浏览器
start http://localhost:8002

echo.
echo 提示：后端服务正在后台运行（最小化窗口）
echo 如需停止，请关闭后端窗口或运行"停止服务.bat"
echo.
timeout /t 3 /nobreak >nul
exit
