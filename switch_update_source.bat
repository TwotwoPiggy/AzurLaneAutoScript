@echo off
chcp 65001 >nul
title Alas 更新源切换与同步工具

cd /d "%~dp0"

:MENU
cls
echo ========================================================
echo               Alas 双更新源管理与同步工具
echo ========================================================
echo.
echo   当前支持两个更新源：
echo     1. 官方原版源 (LmeSzinc/AzurLaneAutoScript)
echo     2. 个人定制源 (您的 GitHub 仓库)
echo.
echo   请选择操作：
echo     [1] 切换并更新到【个人定制版本】 (My GitHub Repo)
echo     [2] 切换并更新到【官方最新原版】 (Official Master)
echo     [3] 配置 / 修改个人 GitHub 仓库地址
echo     [4] 退出
echo.
set /p CHOICE=请输入选项编号 (1-4): 

if "%CHOICE%"=="1" goto SWITCH_CUSTOM
if "%CHOICE%"=="2" goto SWITCH_OFFICIAL
if "%CHOICE%"=="3" goto CONFIG_REPO
if "%CHOICE%"=="4" exit /b 0
goto MENU

:SWITCH_CUSTOM
echo.
echo 正在切换更新源为【个人定制源】...
python -c "from deploy.config import DeployConfig; d = DeployConfig(); d.switch_source('custom'); print('Active Repository:', d.Repository)"
echo.
echo 正在从个人仓库拉取最新更新...
git -c http.proxy=http://127.0.0.1:10808 pull origin master
if %errorlevel% neq 0 (
    git pull origin master
)
python -m module.config.config_updater
echo.
echo ========================================================
echo [完成] 已经同步为个人定制版本！
echo ========================================================
pause
goto MENU

:SWITCH_OFFICIAL
echo.
echo 正在切换更新源为【官方原版源】...
python -c "from deploy.config import DeployConfig; d = DeployConfig(); d.switch_source('official'); print('Active Repository:', d.Repository)"
echo.
echo 正在从官方仓库拉取最新更新...
git -c http.proxy=http://127.0.0.1:10808 pull origin master
if %errorlevel% neq 0 (
    git pull origin master
)
python -m module.config.config_updater
echo.
echo ========================================================
echo [完成] 已经同步为官方最新原版！
echo ========================================================
pause
goto MENU

:CONFIG_REPO
echo.
echo 请输入您的 GitHub 仓库地址 (例如 https://github.com/你的用户名/AzurLaneAutoScript):
set /p NEW_REPO=
if not "%NEW_REPO%"=="" (
    python -c "from deploy.config import DeployConfig; d = DeployConfig(); d.switch_source('custom', custom_repo='%NEW_REPO%'); print('Configured:', d.CustomRepository)"
    git remote set-url origin %NEW_REPO%
    echo.
    echo [成功] 个人仓库地址已更新为: %NEW_REPO%
)
pause
goto MENU
