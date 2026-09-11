@echo off
chcp 65001 >nul
title Alas 临时新活动一键快速周回工具

cd /d "%~dp0"

python dev_tools/quick_event_generator.py %*

if %errorlevel% neq 0 (
    echo.
    echo ========================================================
    echo [提示] 脚本执行遇到问题，请检查上方日志。
    echo ========================================================
)

echo.
pause
