@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0backend"

if not exist ".venv" (
    echo [提示] 未找到虚拟环境，先运行 start.bat 完成初始化。
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo 正在运行测试...
python -m pytest -v
echo.
pause
