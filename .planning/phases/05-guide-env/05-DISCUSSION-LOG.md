# Phase 5: 弱机与模拟器协同最佳配置 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-12
**Phase:** 5-弱机与模拟器协同最佳配置
**Areas discussed:** 双显卡分流与 TDR 容灾配置, MuMu 12 性能参数与 NemuIPC 协同, 系统级虚拟内存优化与环境体检脚本, 指南交付载体与运行时集成

---

## 双显卡分流与 TDR 容灾配置

| Option | Description | Selected |
|--------|-------------|----------|
| 提供「Windows 图形首选项 + Nvidia 控制面板」双重指引 | 主推 Windows 图形设置（Win10/11 权威生效），辅以 Nvidia 驱动面板校验，确保双显卡切换无死角 | ✓ (Recommended) |
| 仅提供「Windows 图形性能首选项」极简指引 | 仅聚焦 Windows 10 2004+/Win11 原生设置界面，减少老旧版本驱动面板的干扰步骤 | |
| 由你决定 | 自动选用推荐实践 | |

**User's choice:** "所有question都用推荐项"（自动选用推荐项，全面落实双重校验与 8s TdrDelay 防护）  
**Notes:** 用户指示所有问题直接采用推荐方案。主推 Windows 图形首选项硬分流，辅以 Nvidia 面板；TdrDelay 设定为 8 秒并提供一键 `.reg` 导入/回退脚本；Thorium 与 Electron 强制路由至 HD 4600 核显，独显 GTX 960M 专供 MuMu 12。

---

## MuMu 12 性能参数与 NemuIPC 协同

| Option | Description | Selected |
|--------|-------------|----------|
| 推荐「2 核 CPU + 3GB 内存 + 30 FPS 锁定 + DirectX 11 引擎 + 关闭后台保活」 | 专为双核四线程老旧平台定制，兼顾碧蓝航线流畅度与宿主机直播资源，确保 NemuIPC 共享内存零 CPU 截图生效 | ✓ (Recommended) |
| 分配 1 核 CPU + 2GB 内存 + 20 FPS 极度压制 | 极度节能，但容易导致转场识别丢帧与游戏偶发卡顿 | |
| 由你决定 | 自动选用推荐实践 | |

**User's choice:** 推荐项  
**Notes:** 锁定 2 核 3GB 与 30 FPS，DirectX 11 驱动更稳定规避 Maxwell 架构 TDR 141，关闭后台挂机保活确保 NemuIPC 正常运作。

---

## 系统级虚拟内存优化与环境体检脚本

| Option | Description | Selected |
|--------|-------------|----------|
| SSD 固定 PageFile (16GB~20GB) + 配套只读/可选 `-Fix` PowerShell 体检脚本 | 消除 15.8GB 虚拟内存动态扩展引发的磁盘饱和假死，提供透明安全的一键体检诊断工具 | ✓ (Recommended) |
| 仅文字建议虚拟内存，不提供自动化脚本 | 交付轻量，但用户排查双显卡注册表与 DLL 门槛较高 | |
| 由你决定 | 自动选用推荐实践 | |

**User's choice:** 推荐项  
**Notes:** 明确 PageFile 设置在固态硬盘且固定大小，配套 `deploy/optimize/check_env.ps1` 实现只读体检与安全管理员 `-Fix` 写入。

---

## 指南交付载体与运行时集成

| Option | Description | Selected |
|--------|-------------|----------|
| `doc/low_spec_tuning_guide.md` + README 导航 + 运行时非阻断诊断提示 + `deploy/optimize/` 打包 | 模块化交付，文档结构包含 3 分钟速查与深度 FAQ，Alas 探测到 MuMu 未走 NemuIPC 时日志友好指引 | ✓ (Recommended) |
| 仅作为静态 Markdown 文档存放于 doc，不修改任何运行时检测代码 | 纯静态文档，缺少运行时自动感知引导 | |
| 由你决定 | 自动选用推荐实践 | |

**User's choice:** 推荐项  
**Notes:** 文档放在 `doc/low_spec_tuning_guide.md`，资源集中于 `deploy/optimize/`，在 `module/device/connection.py` 注入温和的诊断提示。

---

## the agent's Discretion

用户指示“所有question都用推荐项”，因此所有领域的决策均由 Agent 依据既往架构深度调研与双核 Haswell / Maxwell 平台硬件特性直接裁定推荐方案。

## Deferred Ideas

None — 讨论严格聚焦于 Phase 5。
