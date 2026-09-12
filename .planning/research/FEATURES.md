# Feature Research

**Domain:** Game Automation System Optimization & Low-Resource 24/7 Stability
**Researched:** 2026-09-12
**Confidence:** HIGH

---

## Feature Landscape

针对双核低配移动平台（Intel i5-4210H @ 2C4T、16GB 物理内存但虚拟内存 PageFile 高达 15.8GB、HD 4600 核显 + GTX 960M 2GB 独显易发 TDR 重置），且在 7×24 小时挂机期间高频并发 **MuMu 模拟器 + Thorium 浏览器（高清直播解码）+ 网易云音乐 + Alas 桌面端** 的极端资源争抢场景，梳理以下功能架构特征。

### Table Stakes (用户预期的基本盘能力)

缺失这些功能，系统在弱机长时间挂机时将发生卡顿、掉帧、内存泄漏或崩溃，属于不可妥协的基础需求。

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Electron 后台失焦帧率节流 (Background Frame Throttling)** | 当用户最小化或切到 Thorium 看直播时，Electron 无需维持 60 FPS 渲染，避免与浏览器直播争抢 CPU 调度周期。 | LOW | 在 `webapp/packages/main/src/index.ts` 中配置 `backgroundThrottling: true`，并在 `blur` / `minimize` / `window-tray` 时调用 `webContents.setFrameRate(1~5)`。 |
| **Electron 最小化/托盘静默 (Window Minimize/Tray Rendering Pause)** | 挂机 99% 的时间窗口处于后台或托盘，持续绘制 DOM/Canvas 会白白浪费 CPU 与 GPU 显存。 | MEDIUM | 监听 `window-min` 与 `window-tray` 事件，停止渲染树绘制管线；恢复前台（`show` / `focus`）时复原渲染。 |
| **Electron GPU 崩溃平滑回退 (GPU Crash & TDR 141 Fallback)** | GTX 960M 2GB 显存极小且曾触发 `LiveKernelEvent 141`（TDR 显卡驱动超时重置）。若渲染进程遇 GPU 崩溃直接退出，会导致 Alas 桌面端闪退。 | MEDIUM | 监听 `app.on('child-process-gone')` 与 `webContents.on('render-process-gone')`，过滤 `details.type === 'GPU'`，重试并平滑降级或重启渲染，不终止后台 Python 调度。 |
| **PyWebIO 页面失焦/隐藏时日志推送冻结 (Log Stream Pause on Tab Hidden)** | `module/webui/app.py` 目前以 0.25s (4Hz) 无条件调用 `log.put_log()`。用户隐藏窗口时后台持续执行 WebSocket 序列化与 jQuery DOM 操作是纯粹的 CPU 浪费。 | LOW | 基于 `document.visibilityState === 'hidden'` 与 `alas_logs_collapsed`，冻结前端 DOM `append()`，日志仅保留在 Python 内存队列中。 |
| **PyWebIO 日志 DOM 节点上限硬截断 (Strict DOM Log Window Capping)** | 浏览器持续追加 DOM 节点会导致 Chromium 内存暴增和渲染卡顿；目前 `counter` 达 800 节点才重置，且无视页面可见性。 | MEDIUM | 将前端真实挂载的 HTML 行数硬性限制在 100~200 条；超出采用滑动窗口硬剪裁，杜绝 7×24 小时运行下的 DOM 爆炸。 |
| **战斗中自适应轮询降频 (State-Adaptive Combat Polling)** | `module/combat/combat.py` 的 `combat_execute` 在自动战斗时仍以 ~0.1s 极高频疯狂截图并遍历 12+ 个 PAUSE 模版匹配，极度消耗双核 CPU。 | MEDIUM | 识别到处于自律战斗（`combat_auto`）且已锁定战斗状态后，将截图与检测间隔自适应放宽至 1.0s~1.5s，离开战斗状态时毫秒级恢复。 |
| **MuMu IPC 截屏通道强制/优先调度 (MuMu IPC Protocol Prioritization)** | ADB 截屏（screencap / PNG 解码）单次需 50~150ms 且极度消耗 CPU；MuMu IPC 通过共享内存与 C 动态库直读帧缓冲，延迟 <10ms 且几乎 0 CPU 损耗。 | LOW | 检测到运行于 MuMu 模拟器环境时，强制锁死并自适应守护 `nemu_ipc`，避免退化到低效的 ADB 或网络管道。 |
| **错误截图队列内存硬上限 (Bounded Error Screenshot Deque)** | `module/device/screenshot.py` 中未压缩的 720p 图像每帧占用 2.76MB 内存；若用户配置较大，数十帧即吃掉数百 MB 内存，加剧 15.8GB PageFile 换页。 | LOW | 强制约束 `screenshot_deque` 容量（生产环境默认 5~10 帧），杜绝无节制的反查队列膨胀。 |
| **任务交接点软资源清理 (Periodic Soft Cleanup at Task Boundaries)** | `module/base/resource.py` 的 `release_resources()` 原先仅在任务队列为空时执行，且 `gc.collect()` 被注释。连续刷图任务队列永不为空，缓存越积越多。 | LOW | 在每场战役出击结算或大型任务完成点触发清理，释放非必要模版缓存，适度激活垃圾回收。 |
| **子进程心跳守护与僵死回收 (Subprocess Health Watchdog)** | 多进程调度器（`ProcessManager`）在 7×24 挂机下可能因模拟器断开或驱动重置出现挂死子进程。 | MEDIUM | 定期校验子进程状态与日志产出时间戳，异常卡死超阈值时执行安全重启序列，防范静默停摆。 |

---

### Differentiators (差异化优势与核心竞争力)

针对 Haswell 双核移动平台 + 双显卡特定硬件拓扑打造的深度优化，在极限低配下兼顾多任务流畅运行。

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Electron 集显定向绑定 (Intel HD 4600 Low-Power Binding)** | 将 Electron 桌面端锁死在 Intel HD 4600 核显，将 GTX 960M 2GB 的宝贵显存和渲染管线完全腾给 MuMu 与 3D 游戏，杜绝 Electron 抢占独显引发 TDR 141。 | LOW | 启动参数注入 `--force_low_power_gpu` 与相关 Chromium GPU 特性开关，并在指南中引导 Windows 图形性能首选项设置。 |
| **窗口最小化 Working Set 物理内存压缩 (Win32 Working Set Trimming)** | 用户最小化挂机时，主动将 Electron 及 Python 闲置进程的 Working Set 释放归还给系统，直接缓解 15.8GB 虚拟内存的换页压力。 | MEDIUM | 在 Electron 主进程通过 FFI 或脚本调用 Windows API `SetProcessWorkingSetSize(-1, -1)` / `EmptyWorkingSet`，将冷数据页面规整。 |
| **页面唤醒时单次全量快照补偿 (Single-Shot Catch-Up Rendering)** | 页面隐藏期间完全不渲染，用户重新点开窗口时，仅将最新的 100 条日志通过单次 HTML 注入快速刷出，避免数万条历史 DOM 累加回放。 | MEDIUM | 在 PyWebIO `put_log` 改造中引入 `catch_up` 机制，激活瞬间重置容器并单次渲染最新切片。 |
| **画面静态特征自适应退避 (Frame Invariance Dynamic Backoff)** | 战役过图、游戏加载条（Loading）、结算黑屏等静态阶段，连续截图相似度 >99% 时递增轮询休眠（0.2s -> 0.5s -> 1.0s），进一步削减空转开销。 | HIGH | 在 `ModuleBase.loop` 或 `screenshot` 层注入轻量级哈希或差分检测，动态拉长休眠周期，有变动时瞬时归零。 |
| **错误截图流内存压缩存储 (Compressed In-Memory Error Buffer)** | 错误回溯缓冲队列中不存原始 2.76MB 的 uint8 NumPy 数组，而是存 JPEG/WebP 内存字节流，单帧内存从 2.8MB 暴降至 60KB（压缩率 98%）。 | MEDIUM | 在 `screenshot_deque.append` 时以极低开销进行简单压缩编码，既保留完整 60 帧错误排查现场，又将总内存压在 5MB 以内。 |
| **多级渐进式自愈容错升级 (Multi-Tier Self-Healing Escalation)** | 遇到异常时按照 \"重置循环 -> 重连 NemuIPC -> 重启 Python 子进程 -> 重启模拟器游戏\" 4 级梯次自愈，不轻易弹窗请求人工介入。 | HIGH | 针对夜间 24 小时无人值守，大幅降低因临时显卡 TDR 或模拟器短暂无响应导致的挂机中断。 |

---

### Anti-Features (看似美好实则破坏性能/稳定性的负面特性)

经过严谨推导和代码排查，必须坚决避免的技术路线与伪需求。

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **全局无条件禁用硬件加速 (`disableHardwareAcceleration`)** | 开发者以为禁用 GPU 就能彻底防止显卡崩溃或省显存。现行代码（`index.ts:15`）正是如此配置。 | 在 i5-4210H 双核 CPU 上，禁用 GPU 会迫使 Chromium 使用 CPU 软件光栅化（SwiftShader），在渲染复杂 DOM 或图表时吃满 CPU，导致并发的 Thorium 直播卡顿跳帧。 | 启用 GPU 加速，但限制帧率并绑定至 Intel HD 4600 核显，同时配备 GPU Crash 监听与平滑回退机制。 |
| **战斗阶段过度拉长轮询休眠 (>2.5s)** | 试图在战斗中最大化降低 CPU 占用，认为战斗时间长，睡 5~10 秒检测一次即可。 | 碧蓝航线战役结算（S胜界面、掉落确认、自律确认）若响应过慢，会严重拖慢单位时间出击收益；且无法及时处理突发的潜艇呼叫、紧急维修或剧情弹窗，甚至导致战斗超时。 | 战斗主循环采用自适应 1.0s~1.2s 采样，既大幅压低 80% 空转计算，又保证结算与关键弹窗响应时间 <1.5s。 |
| **窗口隐藏时直接销毁渲染器 WebContents** | 认为完全销毁前端页面能将内存与渲染降到绝对 0。 | 重建 WebContents 需重新加载 PyWebIO 并建立 WebSocket 会话，耗时 2~4 秒且伴随白屏；用户未保存的配置表单数据将全部丢失。 | 维持页面进程，但冻结渲染管线（`setFrameRate(0)` / 停止 DOM 更新 / 释放 Working Set），恢复时秒级展现。 |
| **引入庞大的第三方虚拟列表 JS 库** | 想在 WebUI 里做无限滚动的极致虚拟长列表（如 Clusterize.js / vue-virtual-scroller）。 | PyWebIO 架构基于服务端 Python 脚本驱动的 jQuery 注入，强行嵌入复杂前端框架极易破坏其内部响应逻辑，增加前后端通信负担和技术债。 | 采用服务端/轻量级固定窗口截断（Strict DOM Truncation），始终只保留最新的 100~200 个 `<div>` 节点。 |
| **定时无差别硬重启 Alas 或模拟器** | 以为 \"每过 6 小时重启一次进程和模拟器\" 就能粗暴解决所有内存泄漏和稳定性问题。 | 模拟器冷启动在双核低配机上需要 30~60 秒，产生剧烈的 CPU 满载与高磁盘 I/O，会严重卡死正在播放的高清视频直播；且极易打断正在进行的出击造成体力浪费。 | 采用常驻软清理（Soft Cleanup）与事件驱动的渐进式自愈，仅在真正判定任务挂死或连接中断时按需重启。 |
| **在每帧截图循环中同步执行 `gc.collect()`** | 以为只要随时触发 Python 垃圾回收，内存就不会上升。 | Python 全量垃圾回收（三代代际回收）是 Stop-The-World 的 CPU 密集型操作，单次耗时 20~50ms；若在 100ms 的轮询中频繁调用，CPU 占用率将不降反升 30% 以上。 | 仅在任务交接、战役出击结算或内存监测越界时低频触发软回收。 |
| **强制降低游戏内画面分辨率至 720p 以下** | 试图通过 540p 或 480p 进一步削减图像比对开销。 | Alas 整个代码库（`module/base/button.py`, `module/device/screenshot.py:94-96`）与所有 assets 模版严格耦合 1280x720 坐标体系，非 720p 将全面导致识别错位。 | 严格保持 1280x720 基准分辨率，从截图传输链路（NemuIPC）与比对范围裁剪（Bounding Box Area）入手做优化。 |

---

## Feature Dependencies

各优化特性之间的前后依赖与协作关系拓扑：

```
[Electron 集显绑定 (HD 4600)]
    └──requires──> [移除无条件 disableHardwareAcceleration]
                       └──requires──> [Electron GPU 崩溃平滑回退]

[窗口最小化/托盘静默]
    ├──requires──> [后台失焦帧率节流 (backgroundThrottling)]
    └──enhances──> [Win32 Working Set 内存规整压缩]

[PyWebIO 页面失焦日志冻结]
    ├──requires──> [document.visibilityState 状态拦截感知]
    └──enhances──> [DOM 节点上限硬截断]
                       └──enhances──> [页面唤醒单次快照补偿]

[MuMu IPC 优先调度]
    └──enhances──> [战斗阶段自适应轮询降频]
                       └──enhances──> [画面静态特征自适应退避]

[任务交接点软资源清理]
    ├──enhances──> [压缩型内存错误缓冲队列]
    └──conflicts──> [每帧同步频繁触发 gc.collect()]
```

### Dependency Notes

- **移除无条件 `disableHardwareAcceleration` requires [Electron GPU 崩溃平滑回退]:** 开启硬件加速后，为防范 GTX 960M 潜在的 TDR 141 事件，主进程必须具备捕获 GPU 进程崩溃并不退出的容灾能力。
- **[Electron 集显绑定] requires [移除无条件 disableHardwareAcceleration]:** 必须先恢复 GPU 加速架构，才能通过 Chromium 命令行将渲染负荷精准导向核显。
- **[Win32 Working Set 内存规整压缩] enhances [窗口最小化/托盘静默]:** 当窗口已经停止重绘后，调用 `EmptyWorkingSet` 效果最显著，操作系统不会因为立刻有下一帧绘制而反复把内存召回。
- **[页面唤醒单次快照补偿] enhances [DOM 节点上限硬截断]:** 在隐藏期间累积的成百上千条日志无需逐条追加，唤醒时单次写入最新的定额节点，既保证信息完整又杜绝前端渲染卡顿。
- **[任务交接点软资源清理] conflicts with [每帧同步频繁触发 `gc.collect`]:** 内存回收必须控制在低频且关键的调度间隙，绝不能侵入到核心视觉感知的高频闭环内。

---

## MVP Definition

### Launch With (v1) — 核心可用性与基础轻量化 (当前里程碑必达)

消除严重的资源浪费点，保障弱机 7×24 挂机时不发生死机或重大掉驱动。

- [ ] **移除 Electron 硬编码 `disableHardwareAcceleration` 并引入集显指定** — 消除 Electron 抢占双核 CPU 纯软件光栅化的瓶颈。
- [ ] **Electron 后台与最小化自动节流 (`backgroundThrottling` + 帧率降至 1~5)** — 解决后台空耗问题。
- [ ] **Electron GPU 进程崩溃侦测与防闪退守护** — 抵御 GTX 960M TDR 141 冲击，保护 Alas 桌面端常驻。
- [ ] **PyWebIO 页面隐藏/折叠时冻结 `put_log` DOM 注入** — 斩断后台 4Hz 高频 DOM 累积与 WebSocket 空转。
- [ ] **PyWebIO 日志容器 DOM 硬上限约束 (100~200 条)** — 避免持续挂机导致 Chromium 内存膨胀。
- [ ] **战斗主循环 (`combat_execute`) 状态自适应降频 (1.0s~1.2s)** — 将核心挂机场景的空转 CPU 占用骤降 50% 以上。
- [ ] **MuMu 模拟器环境强校验与 NemuIPC 连接保障** — 确保低延迟零开销截图通道常态生效。
- [ ] **错误截图队列容量收紧至 5~10 帧** — 瞬间回收数百 MB 未压缩图像所占用的物理内存。
- [ ] **战役交接点与任务空闲软资源释放** — 补全 `release_resources` 触发点，释放过期模版与无用缓存。

### Add After Validation (v1.x) — 深度体验与资源极致压缩

在基础架构稳定后进一步压榨系统开销，强化无人值守鲁棒性。

- [ ] **最小化时 Windows Working Set 物理内存强制压缩** — 用户隐藏到托盘后，将内存占用进一步压缩到极致，削减 PageFile 压力。
- [ ] **错误缓冲队列采用 JPEG 内存压缩存储** — 在极低内存占用下恢复支持 30~60 帧回溯能力。
- [ ] **静态画面自适应退避算法** — 在加载界面与静止界面根据前后帧相似度动态降低轮询率。
- [ ] **PyWebIO 状态轮询按页面活动性差异化降频** — 当用户未停留在 Overview 页面时，停止轮询战役概览数据。

### Future Consideration (v2+) — 远期架构演进

- [ ] **Rust / C++ 原生轻量截屏与设备抽象桥接** — 完全绕开 Python 截屏开销。
- [ ] **无头模式 (Headless Daemon) 与轻量 Web 分离** — 允许仅运行无图形守护进程，仅在需要时通过任意浏览器甚至移动端查看。

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| **Electron GPU 策略优化与集显绑定** | HIGH | LOW | **P1** |
| **Electron GPU 崩溃平滑回退保护** | HIGH | MEDIUM | **P1** |
| **Electron 后台与最小化自动节流** | HIGH | LOW | **P1** |
| **PyWebIO 页面隐藏/折叠时日志冻结** | HIGH | LOW | **P1** |
| **PyWebIO 日志 DOM 容器硬上限截断** | HIGH | LOW | **P1** |
| **战斗循环自适应降频 (Combat Throttling)** | HIGH | MEDIUM | **P1** |
| **MuMu IPC 截图管道保障与状态确认** | HIGH | LOW | **P1** |
| **错误截图队列容量收敛至安全阈值** | HIGH | LOW | **P1** |
| **任务交接点周期性软清理与垃圾回收** | MEDIUM | LOW | **P1** |
| **窗口隐藏时 Win32 Working Set 压缩** | MEDIUM | LOW | **P2** |
| **唤醒时单次快照补偿渲染** | MEDIUM | MEDIUM | **P2** |
| **错误截图 JPEG 内存流压缩** | MEDIUM | MEDIUM | **P2** |
| **静态画面自适应休眠退避** | MEDIUM | HIGH | **P2** |
| **多级渐进式无人值守自愈升级** | HIGH | HIGH | **P2** |
| **多实例独立 OCR 服务进程复用调优** | MEDIUM | MEDIUM | **P3** |

---

## Competitor Feature Analysis

| Feature | MaaFramework (MAA) | Alas 现有默认实现 | 本方案 (Alas 弱机低功耗 7×24) |
|---------|---------------------|-------------------|---------------------------------|
| **UI 渲染架构** | C++ 驱动的轻量原生 GUI (Qt / WPF / Electron 可选) | Electron 包装 PyWebIO 网页 (强制禁用 GPU 加速) | Electron 启用硬件加速并绑定集显，失焦/最小化深度降频 |
| **日志与状态流** | C++ 环形缓冲区 + 前端虚拟滚动渲染 | PyWebIO 4Hz 轮询无脑 append，800 节点粗暴重置 | 隐藏时完全冻结 DOM，唤醒单次快照补齐，DOM 严格截断 |
| **感知轮询机制** | 任务驱动事件流，根据状态由 C++ 引擎精确睡眠控制 | `loop()` 0.1s 极速循环，战斗内每轮匹配 10+ 个 PAUSE | 状态感知自适应分级：战斗中 1.0~1.2s，静态画面退避，过图毫秒级 |
| **设备截屏管道** | 原生注入 MiniCap / DroidCast / 模拟器直连共享内存 | 多管道支持，但默认配置松散，易回退至高耗 CPU 的 ADB | 针对 MuMu 强约束直通 NemuIPC，绕过网络与编解码栈 |
| **7×24 内存防护** | C++ 原生 RAII 内存管理，极低开销 (<100MB) | 原始 NumPy 阵列入队列，极易飙升到数百 MB | 约束缓冲队列 + JPEG 内存压缩 + 任务点软清理 + Win32 Working Set 回收 |
| **GPU 容灾设计** | 界面崩溃不影响核心引擎，独立分离 | GPU 崩溃或 TDR 导致渲染白屏或闪退 | 监听 `child-process-gone`，隔离 GTX 960M，集显运行，自动恢复 |

---

## Sources

- **本地代码库深度研判**：
  - `webapp/packages/main/src/index.ts`：Electron 启动参数、GPU 加速设置及窗口事件监听。
  - `module/webui/app.py` & `module/webui/widgets.py`：PyWebIO `put_log` 轮询机制、DOM 渲染逻辑与 `document.visibilityState`。
  - `module/combat/combat.py`：战斗主循环 `combat_execute`、PAUSE 模板多重比对与结算判定。
  - `module/device/screenshot.py`：截屏定时器、`screenshot_deque` 内存分配与格式处理。
  - `module/base/resource.py`：资源缓存机制、OCR 模型释放与垃圾回收状态。
  - `module/device/method/nemu_ipc.py`：MuMu 共享内存动态库捕获实现。
- **目标硬件与系统事件**：
  - CPU: Intel Core i5-4210H (2C4T Haswell), RAM: 16GB (PageFile 15.8GB used), GPU: HD 4600 + GTX 960M 2GB (LiveKernelEvent 141 TDR).
- **Chromium / Electron 官方工程规范**：
  - [Electron Performance & Resource Management Best Practices](https://www.electronjs.org/docs/latest/tutorial/performance)
  - [Chromium GPU Process Crash Handling & Feature Flags](https://chromium.googlesource.com/chromium/src/+/master/docs/design/gpu_architecture.md)
  - [Win32 Memory Management - EmptyWorkingSet API](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-emptyworkingset)

---
*Feature research for: Alas low-resource & 7*24h stability optimization*
*Researched: 2026-09-12*
