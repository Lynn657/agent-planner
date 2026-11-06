@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ==========================================
echo   任务规划 Agent - Windows 一键启动
echo ==========================================
echo.

echo [1/4] 检查 Python 版本...
python --version >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 python 命令。
    echo 请安装 Python 3.9 及以上版本，安装时勾选 "Add Python to PATH"。
    pause
    exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
    echo [错误] Python 版本过低，需要 3.9 及以上。
    python --version
    pause
    exit /b 1
)

if not exist "backend\.venv" (
    echo [2/4] 首次运行，创建虚拟环境 backend\.venv ...
    python -m venv backend\.venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败。
        pause
        exit /b 1
    )
) else (
    echo [2/4] 已存在虚拟环境，跳过创建。
)

echo [3/4] 安装依赖（优先清华镜像，失败自动换官方源）...
call backend\.venv\Scripts\activate.bat
python -m pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -q -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [提示] 镜像源安装失败，改用官方源重试...
    pip install -q -r backend\requirements.txt
)
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络或代理设置后重试。
    pause
    exit /b 1
)

echo [4/4] 启动服务：http://127.0.0.1:8000
echo      按 Ctrl+C 停止服务
echo.
start "" /b cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000"
cd backend
python -m flask --app app run --host 127.0.0.1 --port 8000

pause
