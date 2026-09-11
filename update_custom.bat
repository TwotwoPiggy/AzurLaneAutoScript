@echo off
chcp 65001 >nul
title Alas 自定义版本一键安全更新

echo ========================================================
echo       Alas 自定义版本 - 官方更新与自动变基同步工具
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/5] 检查当前工作区状态...
git status --porcelain > "%temp%\alas_git_status.txt"
set /p GIT_STATUS=<"%temp%\alas_git_status.txt"
del "%temp%\alas_git_status.txt" 2>nul

if not "%GIT_STATUS%"=="" (
    echo [提示] 检测到有未保存的改动，正在暂存 (git stash)...
    git stash
    set STASHED=1
) else (
    set STASHED=0
)

echo [2/5] 切换至 master 分支并拉取官方最新代码...
git checkout master
if %errorlevel% neq 0 (
    echo [错误] 切换至 master 分支失败，请检查本地环境！
    goto FAILED
)

git -c http.proxy=http://127.0.0.1:10808 pull origin master
if %errorlevel% neq 0 (
    echo [警告] 拉取官方更新失败，正在重试（无代理）...
    git pull origin master
    if %errorlevel% neq 0 (
        echo [错误] 无法连接到 GitHub，更新终止。请检查本地网络与代理 (127.0.0.1:10808)。
        goto FAILED
    )
)

echo [3/5] 切回 custom 分支并执行智能变基 (git rebase)...
git checkout custom
if %errorlevel% neq 0 (
    echo [错误] 切回 custom 分支失败！
    goto FAILED
)

git rebase master
if %errorlevel% neq 0 (
    echo.
    echo ========================================================
    echo [警告] 变基合并时检测到冲突！
    echo 请打开 VS Code 查看冲突文件并选择保留内容。
    echo 解决完冲突后，运行:  git rebase --continue
    echo 若想放弃本次合并还原，运行:  git rebase --abort
    echo ========================================================
    pause
    exit /b 1
)

if "%STASHED%"=="1" (
    echo [4/5] 恢复先前暂存的未保存改动...
    git stash pop
) else (
    echo [4/5] 无暂存内容，跳过。
)

echo [5/5] 自动同步与重新生成配置项 (config_updater)...
python -m module.config.config_updater

echo.
echo ========================================================
echo       恭喜！更新完成！
echo       您的本地定制功能已完美叠加在官方最新版本之上。
echo ========================================================
echo.
pause
exit /b 0

:FAILED
echo.
echo ========================================================
echo [失败] 更新未能完成，正在尝试切回 custom 分支...
echo ========================================================
git checkout custom 2>nul
if "%STASHED%"=="1" (
    git stash pop 2>nul
)
pause
exit /b 1
