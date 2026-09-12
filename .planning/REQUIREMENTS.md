# Requirements: AzurLaneAutoScript (Alas)

**Defined:** 2026-09-12
**Core Value:** 在保障自动化识别极高准确率与稳定容错的同时，实现低资源损耗、静默流畅的 7×24 小时无人值守挂机。

## v1 Requirements

### Electron 桌面端轻量化与 GPU 保护 (PERF-DESKTOP)

- [ ] **DESK-01**: Electron 桌面端移除硬编码的全局禁用 GPU，定向路由至 Intel HD 4600 核显，避免 CPU 软件光栅化吃满双核
- [ ] **DESK-02**: 窗口失去焦点、最小化或收起至系统托盘时，阶梯式降频帧率（失焦 5 FPS，最小化/托盘 1 FPS），降低渲染能耗
- [ ] **DESK-03**: 建立 Electron GPU 进程崩溃与 TDR 141 容灾捕获机制，GPU 崩溃时平滑降级或重启渲染，不造成 Alas 退出
- [ ] **DESK-04**: 限制 Electron V8 堆内存上限与后台空闲工作集占用

### WebUI 前端与日志流控 (PERF-WEBUI)

- [ ] **WEB-01**: 基于 `document.visibilityState` 建立可见性门禁，网页隐藏或折叠时不向前端追加渲染日志
- [ ] **WEB-02**: 实施前端 DOM 节点上限滑动截断（100~200 条），配合 `overflow-anchor: none` 杜绝 7×24h DOM 膨胀与视口跳动
- [ ] **WEB-03**: 页面从后台重新激活时执行单次快照补偿渲染（Catch-Up），秒级呈现最新状态
- [ ] **WEB-04**: 注入定时轻量心跳机制，防范长连接静默超时导致的 WebSocket 1006 异常断开

### Python 自动化核心能效与通讯调优 (PERF-CORE)

- [ ] **CORE-01**: 自动化核心基类引入状态自适应分级轮询（稳态自律 1.0~1.2s 休眠，关键交互 0ms 瞬时唤醒）
- [ ] **CORE-02**: 优先强制守护 MuMu 12 NemuIPC 原生共享内存截屏通道，实现 <10ms 延迟与 <1% CPU 损耗
- [ ] **CORE-03**: 废除使用 `PyThreadState_SetAsyncExc` 强杀超时截屏线程的不安全做法，避免 C 堆损毁与句柄泄露
- [ ] **CORE-04**: 画面静态阶段（长 Loading、黑屏转场）引入轻量特征退避检测，进一步降低空转开销

### 7×24 小时挂机内存守护与防泄漏 (STAB-MEMORY)

- [ ] **MEM-01**: 错误截图队列 `screenshot_deque` 废除 raw ndarray 裸存，改用 JPEG 内存流高倍压缩（体积降幅 98%）并钳制容量上限
- [ ] **MEM-02**: 任务交接与调度空闲边界执行非必要模版/OCR 缓存注销与适度垃圾回收 (`gc.collect`)
- [ ] **MEM-03**: 引入 Win32 `EmptyWorkingSet` 内存规整机制，主动修剪无用物理工作集，缓解 15.8GB 虚拟内存换页压力
- [ ] **MEM-04**: 完善多进程调度器健康看门狗，定期巡检子进程 RSS 内存与活跃状态，在安全间隙自愈异常进程

### 弱机与模拟器协同最佳配置 (GUIDE-ENV)

- [ ] **ENV-01**: 提供双显卡（HD 4600 + GTX 960M）在 Windows 图形首选项中的硬分流配置指南，独显专供 MuMu，核显承载 Thorium 与 Electron
- [ ] **ENV-02**: 提供 MuMu 12 性能设置（核心分配、帧率限制、关闭后台挂机保活以启用 NemuIPC）的调优指南
- [ ] **ENV-03**: 提供系统级虚拟内存优化与防 TDR 驱动超时参数建议

## v2 Requirements

### 进阶原生加速与架构拆分

- **NTV-01**: Rust / C++ 编写的原生无头截屏与设备输入桥接
- **DAEM-01**: 纯无头后台守护服务与前端彻底进程隔离解耦

## Out of Scope

| Feature | Reason |
|---------|--------|
| 全局无条件禁用 GPU (`disableHardwareAcceleration`) | 会迫使双核 CPU 承担纯软件光栅化，与 Thorium 直播争抢算力，极度易卡顿 |
| 战役战斗中无脑长休眠 (>2.5s) | 会严重拖慢战斗结算与出击效率，无法及时响应剧情弹窗与潜艇呼叫 |
| 强制降低游戏内画面分辨率至 720p 以下 | Alas 全套 assets 模版与坐标体系基于 1280×720，降低分辨率将导致全面识别失败 |
| 频繁在每帧截图循环中调用 `gc.collect()` | 垃圾回收 Stop-The-World 耗时 20~50ms，频繁调用反而造成 CPU 暴涨 30% |
| 定时盲目无差别重启模拟器与系统 | 冷启动耗时长达 30~60s，会造成 CPU 满载与严重磁盘 IO 冲击，劣化并发看直播体验 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DESK-01 | Phase 1 | Pending |
| DESK-02 | Phase 1 | Pending |
| DESK-03 | Phase 1 | Pending |
| DESK-04 | Phase 1 | Pending |
| WEB-01 | Phase 2 | Pending |
| WEB-02 | Phase 2 | Pending |
| WEB-03 | Phase 2 | Pending |
| WEB-04 | Phase 2 | Pending |
| CORE-01 | Phase 3 | Pending |
| CORE-02 | Phase 3 | Pending |
| CORE-03 | Phase 3 | Pending |
| CORE-04 | Phase 3 | Pending |
| MEM-01 | Phase 4 | Pending |
| MEM-02 | Phase 4 | Pending |
| MEM-03 | Phase 4 | Pending |
| MEM-04 | Phase 4 | Pending |
| ENV-01 | Phase 5 | Pending |
| ENV-02 | Phase 5 | Pending |
| ENV-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-12*
