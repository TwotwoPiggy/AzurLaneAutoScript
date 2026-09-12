# Project Rules: AzurLaneAutoScript

## 自动推送到远端仓库 (Auto Push to Remote)

在本项目中，每次代码修改、功能调整或 Bug 修复完成并通过验证后，默认将改动提交并推送到远端仓库：
1. **提交规范**：使用规范的 Conventional Commits 格式编写提交信息（例如 `feat(webui): ...`, `fix(webui): ...`）。
2. **走本地代理**：推送与拉取操作遵循代理规则，使用本地代理 `http://127.0.0.1:10808` 进行 GitHub 推送（例如 `git -c http.proxy=http://127.0.0.1:10808 push origin <branch>` 或使用仓库配置的局部代理）。
3. **推送目标**：默认推送到当前追踪的远端分支（如 `origin/custom`）。
