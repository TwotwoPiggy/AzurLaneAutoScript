# AzurLaneAutoScript (Alas)

## What This Is

AzurLaneAutoScript (Alas) 是一款功能完备的碧蓝航线（Azur Lane）日常自动化与任务调度系统。支持战役出击、大型作战、日常任务、后宅委托等全流程自动化，具备完善的有向图页面导航、多实例管理与基于 PyWebIO / Electron 的桌面控制台。

## Core Value

在保障自动化识别极高准确率与稳定容错的同时，实现低资源损耗、静默流畅的 7×24 小时无人值守挂机。

## Current Milestone: v1.0 弱机性能轻量化与 7×24h 挂机稳定性 (Performance & Low-Resource 24/7 Stability)

**Goal:** 为双核/老旧移动平台硬件量身打造极低资源占用的 Alas 运行体验，大幅削减 Electron 桌面端与 Python 后台自动化运行时的 CPU、内存与 GPU 开销，保障 7×24 小时挂机兼顾流畅看直播与听歌。

**Target features:**
- **Electron 桌面端轻量化与显存/GPU保护**：优化 Chromium 渲染进程及主进程开销，失焦/最小化时降低帧率与渲染负荷，防范核显/老旧独显 TDR 超时与掉驱动问题。
- **PyWebIO 页面与日志流前端节流**：优化 WebUI 日志实时输出与 DOM 渲染节点，避免长时间挂机导致前端内存暴涨或网页卡死。
- **Python 后端自动化循环能效优化**：优化截图传输链路（优先推荐并调优低 CPU 损耗的通讯管道），细化等待轮询自适应休眠，降低常态 CPU 占用。
- **7×24 小时挂机内存与防泄漏机制**：严格管理错误截图缓冲队列（deque）、日志句柄与后台子进程生命周期，杜绝长期运行下的内存积压与句柄泄漏。
- **老旧平台与模拟器协同最佳配置指导**：针对双核四线程 CPU 与 Haswell 平台的 MuMu 核心分配、帧率限制与硬件加速协同配置。

## Requirements

### Validated

<!-- 现有代码库已实现且成熟的能力 -->

- ✓ 战役主线与活动关卡自动寻路与作战自动化 (`module/campaign/`, `module/combat/`) — v0.x
- ✓ 大型作战 (Operation Siren) 全自动日常与塞壬海域探索 (`module/os/`) — v0.x
- ✓ 委托、后宅、科研、每日任务及演习自动化 (`module/daily/`, `module/dorm/`, `module/reward/`) — v0.x
- ✓ 基于有向图 BFS/A* 的游戏内页面路由引擎 (`module/ui/ui.py`, `module/ui/page.py`) — v0.x
- ✓ 多截图管道（ADB, DroidCast, Scrcpy, NemuIPC, LDOpenGL）与输入驱动适配 (`module/device/`) — v0.x
- ✓ 基于 PyWebIO 的多配置实例任务调度器与 Web 控制台 (`gui.py`, `module/webui/`) — v0.x
- ✓ 基于 Electron 的跨平台桌面客户端外壳 (`webapp/packages/`) — v0.x

### Active

<!-- 本里程碑专注攻克的改进项 -->

- [ ] **PERF-DESKTOP**: Electron 桌面客户端轻量化优化（降低常驻内存、后台/失焦节流渲染、优化 GPU 加速策略）
- [ ] **PERF-WEBUI**: WebUI 前端与 PyWebIO 日志流渲染节流（DOM 截断/虚拟滚动、减少长连接无效推送）
- [ ] **PERF-CORE**: Python 自动化核心循环与截图能效调优（循环等待自适应睡眠节流、低 CPU 损耗管道增强）
- [ ] **STAB-MEMORY**: 7×24 小时挂机内存守护与防泄漏（截图缓冲容量约束、进程生命周期健康检测）
- [ ] **GUIDE-ENV**: 弱机环境（Haswell i5 双核）与 MuMu 模拟器协同低功耗调优指南

### Out of Scope

- 碧蓝航线全新玩法关卡的大型功能重构（如完全重写大世界逻辑） — 本里程碑专注已有运行时的性能与稳定性
- 彻底移除 Electron 并自研原生桌面 GUI（如 C++/Qt/Rust） — 改动成本过高，优先在现有 Electron 架构内做极度优化与防沉降
- 修改底层的图像特征模型（不重新训练 CNOCR 权重） — 保持现有模型，仅从推理时机和调用频次做节流

## Context

- **硬件运行环境**：
  - CPU: Intel Core i5-4210H @ 2.9GHz（2 核 4 线程，移动标压 Haswell 平台，多任务计算资源紧张）
  - RAM: 16GB 物理内存，但 PageFile（虚拟内存）已高达 15.8GB used，说明整机面临明显的内存置换压力
  - GPU: 双显卡环境（Intel HD Graphics 4600 核显 + Nvidia GTX 960M 2GB 独显），系统曾触发 `LiveKernelEvent 141`（显卡引擎超时/TDR 重置），需防止 Electron/渲染占用过度吃满显存与渲染管线
- **典型高负载并发场景**：
  - 7×24 小时后台运行 MuMu 模拟器挂机碧蓝航线
  - 晚间并发运行 Thorium 浏览器观看高清视频直播（高 CPU/GPU 解码开销）与网易云音乐播放
  - 用户习惯通过 Electron 桌面客户端常驻观察与操作 Alas
- **当前瓶颈分析**：
  - Alas 长时间运行后，Python 子进程 + PyWebIO 渲染 + Electron Chromium 渲染进程三者叠加，对老旧双核 CPU 造成较重的调度压力与内存消耗
  - WebUI 长时间日志输出若无限制滚动将造成 DOM 节点暴增
  - 图像识别轮询若休眠时间过短会空转消耗 CPU

## Constraints

- **Compatibility**: 必须兼容现有 Alas 配置结构与任务调度逻辑，不破坏已有的自动化行为
- **Architecture**: 保持 Python 后端进程与 Electron 桌面端的主体通讯架构，优化以非破坏性参数注入、节流策略与内存管理为主
- **Resolution**: 仍维持 1280×720 基准分辨率与图像比对算法准确度

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 优先对现有 Electron 与 WebUI 架构进行轻量化剪枝与节流，而非推倒重做 | 保护现有庞大逻辑与多配置适配，以最高性价比解决卡顿问题 | — Pending |
| 引入后台/失焦节能策略 (Low Power Mode) | 当桌面端未处于前台交互时，降低界面渲染与数据轮询频率，将资源留给模拟器与直播 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-12 after milestone v1.0 initialization*
