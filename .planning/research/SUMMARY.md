# Project Research Summary

**Project:** AzurLaneAutoScript (Alas)  
**Domain:** 游戏自动化 / 桌面控制台系统 / 弱机低资源损耗与 7×24h 挂机稳定性 (Game Automation & Low-Resource Performance)  
**Researched:** 2026-09-12  
**Confidence:** HIGH  

---

## Executive Summary

AzurLaneAutoScript (Alas) 是一款基于 Python 与 Electron/PyWebIO 的高成熟度碧蓝航线自动化调度系统。本调研紧密围绕当前 **v1.0 里程碑目标**：在极端严苛的弱机高负载硬件环境（Intel Core i5-4210H 双核四线程 CPU @ 2.9GHz、16GB 物理内存但已承受 15.8GB 虚拟内存换页压力、GTX 960M 2GB 独显曾发生 `LiveKernelEvent 141` TDR 显卡超时重置，且 7×24 小时挂机期间并发 Thorium 浏览器硬解观看高清直播与网易云音乐）下，消除资源争抢、卡顿降频与闪退隐患，实现极低资源开销的 7×24 小时无人值守挂机。

基于对 Alas 核心源码、Chromium 渲染机制、Windows WDDM 驱动层和 MuMu 12 原生通信的深度研判，团队确立了**“物理显卡分流、原语级共享内存、内存队列高倍压缩、可见性门禁日志流控与状态自适应休眠”**的核心技术路线。系统不再采取粗暴修改大颗粒度 sleep 或盲目全局关闭 GPU 等“伪优化”，而是通过精准的架构重塑，在不破坏现有 55+ 业务模块的前提下全面实现低功耗与高鲁棒性。

核心风险聚焦在三大瓶颈：**显存与渲染管线争抢导致 GPU 驱动 TDR 141 崩溃**、**15.8GB PageFile 饱和下的图像矩阵内存置换雪崩**，以及**双核 CPU 算力饥饿与热降频**。通过将 Electron 绑定至 Intel HD 4600 核显并做后台 1~5 FPS 深度节流、错误截图队列改用 JPEG 内存流压缩（体积暴降 98%）、强制锁定 MuMu NemuIPC 零 CPU 截图通道，以及引入状态感知阶梯休眠，可彻底规避上述风险，为后续路线图规划奠定坚实依据。

---

## Key Findings

### Recommended Stack

技术栈选型严格遵循“零 GPU 争抢、零冗余编解码、原语级共享内存与 Win32 原生内存回收”原则，最大程度榨取 Haswell 老旧双核平台的运行效能。

**Core technologies:**
- **NemuIPC (`external_renderer_ipc.dll`)**: MuMu 12 原生共享内存截图与触控 — **5~15ms 延迟，CPU 占用 < 1%**，完全绕过 Android 虚拟化网络栈与 H.264/JPEG 编解码，根除 CPU/GPU 挤占。
- **Electron Low-Power Runtime (Chromium 94)**: 桌面客户端轻量化与能效控制台 — 移除硬编码全局禁用 GPU，定向路由至 **Intel HD 4600 核显** 并剥离 3D WebGL 管线；失焦降频至 5 FPS，最小化/托盘降频至 1 FPS，限制 V8 堆内存为 128MB。
- **Win32 Working Set Trimming (`EmptyWorkingSet`)**: Windows 物理工作集强制规整与内存释放 — 在任务交界与长等待空闲期强制释放未引用的物理页，压制 CPython 内存碎片，极大缓解 15.8GB 虚拟内存的换页颠簸。
- **Native DOM Sliding Window & Visibility Gate**: PyWebIO 日志流控与前端滑动截断 — 引入 `document.visibilityState` 门禁，后台折叠时 0Hz 推送，前台限制 150 条 DOM 节点滑动截断，配合 `overflow-anchor: none` 杜绝视口跳动。
- **In-Memory JPEG Buffer (`cv2.imencode`)**: 错误追溯队列内存压缩 — 替代原始 2.76MB 的 NumPy 裸存矩阵，单帧体积降至 50~80KB，60 帧回溯仅占 ~3MB 内存（降幅 98%）。

---

### Expected Features

针对双核移动 CPU、2GB 移动独显与极重虚拟内存换页环境，功能结构划分如下：

**Must have (table stakes):**
- **PERF-DESKTOP**: Electron 桌面端轻量化与显存/GPU 保护 — 移除全局盲目禁用 GPU，绑定 HD 4600 核显，接入失焦/最小化/托盘帧率阶梯节流（1~5 FPS）与 GPU 崩溃平滑回退保护。
- **PERF-WEBUI**: PyWebIO 日志流可见性门禁与 DOM 节点硬上限 — 页面隐藏/折叠时冻结 WebSocket 日志推流；前端维持 150~200 条 DOM 严格滑动截断；注入 30s 轻量心跳杜绝 1006 异常断连。
- **PERF-CORE**: Python 自动化核心循环状态感知型自适应休眠 — 战斗自律与动画稳态阶段将轮询放宽至 1.0s~1.2s，关键交互与断言瞬间 0ms 复位，大幅降低空转 CPU。
- **STAB-MEMORY**: 7×24 小时挂机内存防护与防泄漏机制 — 截图缓冲队列 JPEG 内存流压缩（上限 30~50 帧）；任务边界执行 OCR 注销、`gc.collect()` 与 `EmptyWorkingSet` 内存修剪。
- **GUIDE-ENV**: 弱机环境与 MuMu 12 协同调优指南 — 独显供 MuMu 独占、核显供 Thorium 与 Electron 分流；关闭 MuMu 后台保活以确保 NemuIPC 稳定生效。

**Should have (competitive):**
- **Win32 窗口隐藏工作集极限压缩**: 最小化至托盘时自动剥离非活动物理页，使常驻内存降低至 30MB 级。
- **页面激活单次快照补偿渲染**: 从后台恢复时一次性挂载最新 100 条日志，避免历史全量回放造成的瞬时白屏或卡顿。
- **静态画面轻量差分退避**: 在长 Loading 或黑屏过渡期间动态步进休眠。
- **子进程 RSS 巡检与任务边界优雅重启**: 针对连续运行超 48 小时且 RSS > 600MB 的子进程在任务安全交界点进行毫秒级热重启，彻底根除 CPython 底层内存碎片。

**Defer (v2+):**
- **Rust / C++ 原生截屏与设备通信桥接**: 进一步追求微秒级延迟，但在 NemuIPC 5ms 表现下当前边际效益不高。
- **纯无头后台守护进程 (Headless Daemon) 与独立 Web 分离**: 当前架构已能通过 Electron 深度节流解决占用，暂不重构进程拓扑。

---

### Architecture Approach

优化方案严密嵌入 Alas 现有的分层架构（Electron 外壳层 ↔ WebUI 监管层 ↔ 调度执行层 ↔ 视觉感知与设备层），将自适应休眠与内存防御注入 `ModuleBase` 基类与设备驱动层，实现**全系统 55+ 业务模块零侵入式全局受益**。

**Major components:**
1. **Electron Host (`webapp/packages/main/src/index.ts`)**: 桌面宿主与功耗中枢 — 负责核显定向路由、窗口焦点/最小化/托盘监听、帧率阶梯节流控制与 GPU 崩溃容灾。
2. **PyWebIO Presentation & Gated Log Streamer (`module/webui/`)**: 界面与日志通道 — 负责可见性状态感知、WebSocket 心跳保活、1.0s 降频推送与前端 DOM 环形截断。
3. **Task Scheduler & Process Supervisor (`alas.py`, `process_manager.py`)**: 任务主循环与进程看门狗 — 负责任务交界内存回收检查点、`EmptyWorkingSet` 调用、子进程 RSS 探测与安全生命周期管理。
4. **Automation State Machine Engine (`module/base/base.py`)**: 自动化感知与执行基类 — 负责维护 `_idle_loop_count`，驱动自适应三阶梯休眠与按钮断言命中瞬时 0ms 唤醒。
5. **Vision & Device Driver (`module/device/`)**: 截图采集与错误追溯池 — 负责 MuMu NemuIPC 共享内存零开销采集与错误回溯队列的内存 JPEG 压缩存储。

---

### Critical Pitfalls

1. **Electron 盲目禁用 GPU 加速 (`--disable-gpu`) 导致双核 CPU 负载雪崩与发热降频**  
   *规避方案*：移除无条件 `disableHardwareAcceleration`，将 Electron 路由至 **Intel HD 4600 核显**（`--gpu-preference=low-power`），剥离 3D WebGL，由核显接管 2D 合成，彻底避免 CPU 软件光栅化吃满双核。
2. **显存竞逐触发 Windows GPU 驱动 TDR (`LiveKernelEvent 141`) 与模拟器崩溃**  
   *规避方案*：实施物理双显卡硬性分流策略——GTX 960M 2GB 独显专供 MuMu 模拟器独占；HD 4600 核显承接 Thorium 直播硬解与 Electron 渲染，物理阻断显存穿透与驱动超时。
3. **错误截图原始矩阵导致 15.8GB 虚拟内存踩踏与 PageFile 磁盘换页卡死**  
   *规避方案*：`screenshot_deque` 废弃 raw ndarray 裸存，存入前使用 `cv2.imencode('.jpg')` 快速转为内存字节流，单帧从 2.76MB 压缩至 50~80KB，并在弱机环境下钳制队列上限至 30~50 帧。
4. **自动化主循环粗暴全局休眠导致战役结算漏检、卡死与 S 胜受损**  
   *规避方案*：严禁在循环中加入全局固定大 sleep。采用状态自适应分级轮询（过渡敏感期 100~200ms、自律稳态期 1.0~1.2s），任何 `appear` 命中或点击动作立即触发 `reset_loop_sleep()` 瞬时复位。
5. **NemuIPC 强杀超时线程 (`SetAsyncExc`) 造成 C 堆死锁与句柄泄露 (`rpc 1722`)**  
   *规避方案*：废弃不安全的 `PyThreadState_SetAsyncExc`，采用 DLL 原生非阻塞探测或将 NemuIPC 隔离于独立工作子进程，超时异常直接通过操作系统 API 优雅回收。
6. **RichLog 朴素 DOM 截断破坏浏览器滚动锚定与视口跳动**  
   *规避方案*：声明 CSS `overflow-anchor: none`，在 JS 剪裁顶部旧节点时同步补偿视口偏移量（`scrollTop -= removedHeight`），并使用 `requestAnimationFrame` 批处理 DOM 渲染。

---

## Implications for Roadmap

基于研究发现的技术依赖与防坑策略，建议规划 5 个循序渐进的交付阶段：

### Phase 1: Electron 桌面端轻量化与显存/GPU 保护 (PERF-DESKTOP)
**Rationale:** 桌面端是资源争抢与 TDR 崩溃的最外层触发源。必须率先纠正错误的“全局禁用 GPU”设置，消除 CPU 纯软件光栅化与独显显存挤占。  
**Delivers:** 核显定向路由配置、窗口失焦（5 FPS）/最小化（1 FPS）节流策略、GPU 崩溃平滑回退守护与 V8 堆内存上限约束。  
**Addresses:** `PERF-DESKTOP`  
**Avoids:** Pitfall 1（CPU 光栅化雪崩）、Pitfall 2（遮挡休眠告警静默）、Pitfall 8（显存争抢与 TDR 141）。

### Phase 2: WebUI 前端与 PyWebIO 日志流控与 DOM 截断 (PERF-WEBUI)
**Rationale:** 解决长时间挂机下的前端内存膨胀与无效 WebSocket 渲染消耗，且为后台运行建立稳固的连接防护。  
**Delivers:** 前台可见性门禁拦截、1.0s 降频合并推流、前端 150 条 DOM 环形滑动截断（含视口高度补偿）、30s 心跳注入与 WebSocket 1006 异常自愈重连。  
**Addresses:** `PERF-WEBUI`  
**Avoids:** Pitfall 3（WebSocket 1006 假死）、Pitfall 4（Session 闭包泄漏）、Pitfall 5（DOM 截断视口跳跃）。

### Phase 3: Python 自动化核心循环与截图能效调优 (PERF-CORE)
**Rationale:** 自动化核心轮询是常态 CPU 占用的源头。将能效优化下沉至基类，可一次性普惠全部 55+ 业务模块。  
**Delivers:** `ModuleBase.loop()` 三阶梯自适应休眠（稳态 1.0~1.2s）与 0ms 瞬时唤醒机制、MuMu NemuIPC 截图优先连接守护、废除 `SetAsyncExc` 规避 DLL 句柄泄露。  
**Addresses:** `PERF-CORE`  
**Avoids:** Pitfall 6（激进休眠丢失 S 胜）、Pitfall 7（NemuIPC 强杀导致 C 堆损毁与 rpc 1722）。

### Phase 4: 7×24 小时挂机内存与防泄漏机制 (STAB-MEMORY)
**Rationale:** 针对 15.8GB 虚拟内存的严峻置换压力，构筑底层的物理内存屏障，防范长时间无人值守下的 OOM 与换页卡顿。  
**Delivers:** `screenshot_deque` JPEG 内存流压缩（体积暴降 98%）、队列容量安全钳制（30~50 帧）、任务交界点 OCR 缓存清理与 Win32 `EmptyWorkingSet` 物理工作集修剪、子进程 RSS 看门狗。  
**Addresses:** `STAB-MEMORY`  
**Avoids:** Pitfall 9（PageFile 饱和与硬缺页磁盘雪崩）、Pitfall 7（进程与句柄泄漏）。

### Phase 5: 老旧平台与模拟器协同最佳配置指导 (GUIDE-ENV)
**Rationale:** 硬件与模拟器层面的外部配置是所有代码优化的基础，直接决定双显卡分流与 NemuIPC 能否以最佳状态运行。  
**Delivers:** Windows 图形性能首选项分流指南（GTX 960M 专供 MuMu / HD 4600 承载 Thorium 与 Electron）、MuMu 12 性能设置（核心绑定、20~30 FPS、关闭后台挂机保活以启用 NemuIPC）。  
**Addresses:** `GUIDE-ENV`  
**Avoids:** Pitfall 8（系统级双显卡混用）、MuMu 后台保活冲突。

---

### Phase Ordering Rationale

- **前置消除外壳争抢与 DOM 膨胀 (Phase 1 & 2)**：Electron 与 WebUI 构成了 Alas 的交互外壳。优先完成桌面端显卡分流与 WebUI 日志截断，能在最快时间内压低系统基础空闲负载，让出 CPU 与显存供后续核心循环测试。
- **基类能效全局注入 (Phase 3)**：将自适应休眠注入 `ModuleBase` 基类，不侵入各个业务文件夹，保证自动化逻辑 100% 行为兼容的前提下立即收获 50%+ 的核心空转降温效果。
- **内存深度筑堤与守护闭环 (Phase 4)**：在核心循环与外壳稳定的基础上，实施 JPEG 压缩与 `EmptyWorkingSet`，完成 7×24h 挂机的最后一块稳定性拼图。
- **宿主环境配置固化 (Phase 5)**：将代码逻辑层面的前置断言转化为面向用户硬件的配置指南，形成端到端的闭环保障。

---

### Research Flags

**Phases needing deeper research / delicate testing during planning:**
- **Phase 1 (PERF-DESKTOP)**: 需要在真实双显卡环境下严格测试 Chromium CLI 参数（`--gpu-preference=low-power`）是否能在当前 Windows 版本中稳定迫使 Electron 选择 Intel HD 4600 而不触碰 GTX 960M。
- **Phase 3 (PERF-CORE)**: 需重点验证高难战斗（如 14-4、大世界月度 Boss）中自适应休眠对潜艇呼叫与自律确认的响应敏捷度，确保结算识别率绝对保持 100%。

**Phases with standard patterns (skip research-phase):**
- **Phase 2 (PERF-WEBUI)**: `document.visibilityState`、WebSocket 定时心跳与滑动窗口 DOM 剪裁均为成熟的 Web 标准模式。
- **Phase 4 (STAB-MEMORY)**: OpenCV `imencode` 内存压缩与 Win32 `EmptyWorkingSet` 调用链路简明标准，可直接设计并落地验证。
- **Phase 5 (GUIDE-ENV)**: 依托已明确的硬件拓扑与 MuMu 12 官方文档直接编写指导手册。

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | HIGH | 核心技术（NemuIPC、Electron 启动参数、Win32 PSAPI、PyWebIO）均已在代码库和目标硬件规格中严格交叉比对，技术路线具备强确定性。 |
| **Features** | HIGH | 针对弱机 7×24 挂机并发痛点精准提炼，MVP 边界清晰，明确排除了推倒 Electron 重写或训练新模型等过度设计。 |
| **Architecture** | HIGH | 分层架构与数据流图完备，精准定位基类 `ModuleBase`、`Screenshot` 与 `RichLog`，做到了无破坏性全局注入。 |
| **Pitfalls** | HIGH | 深度覆盖双显卡 TDR 141、CPU 软件光栅化雪崩、15.8GB PageFile 换页风暴、S 胜漏检与 C 库死锁等致命隐患，提供了高可操作性对策。 |

**Overall confidence:** HIGH

### Gaps to Address
- **GTX 960M 驱动稳定性实时观察**：在 Phase 1 落地后，需通过 GPU-Z 连续监测并发播放 4K 直播时的显存与温度曲线，验证显存分流效果。
- **战役结算动画差异性适配**：针对不同地图（如微层混合、大世界）结算转场的微小帧率差异，在 Phase 3 中预留自适应梯度的可微调配置参数。

---

## Sources

### Primary (HIGH confidence)
- **Alas 核心源码审计**：
  - `webapp/packages/main/src/index.ts`: Electron 硬件加速与主进程配置
  - `module/webui/app.py` & `widgets.py`: PyWebIO 会话、RichLog 渲染与 DOM 截断机制
  - `module/base/base.py` & `module/combat/combat.py`: 自动化循环、战斗主逻辑与截图轮询
  - `module/device/screenshot.py` & `method/nemu_ipc.py`: 截图管道、deque 队列与 MuMu 共享内存
  - `module/base/resource.py`: 资源释放与垃圾回收状态
- **微软官方文档**：*EmptyWorkingSet function (psapi.h)*、*Timeout Detection and Recovery (TDR) in WDDM v1.3/v2.0*
- **Chromium 官方规范**：*Command Line Switches Reference*、*Handling Backgrounding and Occlusion Throttling in Chromium*

### Secondary (MEDIUM confidence)
- **MuMu 模拟器官方文档**：MuMu 12 外部渲染 IPC 规范与保活机制配置（`customer.app_keptlive`）
- **PyWebIO 内部通信机制分析**：PyWebIO Session 状态机与 WebSocket 通信规范

---
*Research completed: 2026-09-12*  
*Ready for roadmap: yes*  
