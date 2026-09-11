@echo off
chcp 65001 >nul
title Alas 电脑B一键平滑变轨升级

echo ========================================================
echo        Alas 电脑B - 最小变更升级到个人定制版
echo ========================================================
echo.
echo 本脚本将电脑B的Alas升级为您GitHub上的个人定制版：
echo  1. 保留现有所有游戏配置 (config/*.json) 与账号数据
echo  2. 保留现有的 Python、toolkit 与运行环境 (不需重新下载)
echo  3. 仅替换核心代码并启用双更新源 (官方/私有自由切换)
echo.

cd /d "%~dp0"

:: 1. 检查是否在 Alas 目录下
if not exist "gui.py" (
    echo [错误] 未在当前目录下检测到 gui.py，请将本脚本放在 Alas 根目录下运行！
    pause
    exit /b 1
)

:: 2. 定位 Git 执行程序
set GIT_CMD=git
if exist "toolkit\Git\mingw64\bin\git.exe" (
    set "GIT_CMD=toolkit\Git\mingw64\bin\git.exe"
)

:: 3. 自动备份用户的游戏配置文件
echo [1/4] 正在备份现有游戏配置...
if not exist "config\backup_before_custom" mkdir "config\backup_before_custom"
copy /y config\*.json "config\backup_before_custom\" >nul 2>&1
echo       已备份 config 目录下的所有游戏配置文件。
echo.

:: 4. 配置远程仓库与代理
echo [2/4] 正在配置远程更新仓库...
set REPO_URL=https://github.com/TwotwoPiggy/AzurLaneAutoScript.git
set PROXY_ARG=

:: 测试是否能直接连通 GitHub，若超时则使用本地代理
echo 正在检测 GitHub 连接...
"%GIT_CMD%" ls-remote %REPO_URL% HEAD >nul 2>&1
if %errorlevel% neq 0 (
    echo 检测到直连 GitHub 超时，正在启用本地代理 (http://127.0.0.1:10808)...
    set "PROXY_ARG=-c http.proxy=http://127.0.0.1:10808"
)

:: 切换 origin 远程地址为个人仓库
"%GIT_CMD%" remote set-url origin %REPO_URL% >nul 2>&1
if %errorlevel% neq 0 (
    "%GIT_CMD%" remote add origin %REPO_URL% >nul 2>&1
)

:: 5. 拉取并切换到 custom 分支
echo.
echo [3/4] 正在拉取个人定制版 (custom 分支) 最新代码...
"%GIT_CMD%" %PROXY_ARG% fetch origin custom
if %errorlevel% neq 0 (
    echo.
    echo [错误] 拉取 custom 分支失败！
    echo 请检查网络连接或代理 (http://127.0.0.1:10808) 是否已开启。
    pause
    exit /b 1
)

echo 正在切换工作区分支为 custom...
"%GIT_CMD%" checkout -B custom origin/custom
"%GIT_CMD%" reset --hard origin/custom

:: 6. 恢复游戏配置
echo.
echo [4/4] 正在验证并恢复游戏配置...
copy /y "config\backup_before_custom\*.json" config\ >nul 2>&1

echo.
echo ========================================================
echo                  🎉 升级完成！
echo ========================================================
echo 1. 电脑B已成功变轨为个人定制版 (custom 分支)。
echo 2. 原有的游戏配置、账号、模拟器设置已全部完好保留。
echo 3. 现在启动 Alas，在【开发】->【更新】中即可看到
echo    「官方更新」与「私有更新」双通道！
echo ========================================================
echo.
pause
