@echo off
chcp 65001 >nul
title 推送定制代码到个人 GitHub 仓库

echo ========================================================
echo         Alas 定制版本 - 一键推送至个人 GitHub 仓库
echo ========================================================
echo.

cd /d "%~dp0"

:: 检查是否配置了 myrepo 远程仓库
git remote get-url myrepo >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 尚未检测到已配置的个人远程仓库 (myrepo)。
    echo.
    echo 请输入您的 GitHub 仓库地址 (例如 https://github.com/你的用户名/AzurLaneAutoScript.git):
    set /p REPO_URL=
    if "%REPO_URL%"=="" (
        echo [错误] 输入为空，操作取消。
        pause
        exit /b 1
    )
    git remote add myrepo %REPO_URL%
    echo 已成功绑定个人远程仓库: %REPO_URL%
    echo.
)

for /f "delims=" %%u in ('git remote get-url myrepo') do set CURRENT_MYREPO=%%u
echo 当前目标仓库: %CURRENT_MYREPO%
echo 正在将 custom 分支推送到 GitHub 的 master 分支...
echo.

git -c http.proxy=http://127.0.0.1:10808 push myrepo custom:master
if %errorlevel% neq 0 (
    echo.
    echo [警告] 推送失败，正在尝试无代理重试...
    git push myrepo custom:master
    if %errorlevel% neq 0 (
        echo.
        echo [错误] 推送失败！请检查：
        echo  1. 网络连接与代理 (127.0.0.1:10808) 是否正常
        echo  2. 是否已在 GitHub 上创建该仓库并拥有写入权限
        pause
        exit /b 1
    )
)

echo.
echo ========================================================
echo       推送成功！
echo       电脑 B 现在可以从您的 GitHub 仓库直接接收更新了！
echo ========================================================
echo.
pause
