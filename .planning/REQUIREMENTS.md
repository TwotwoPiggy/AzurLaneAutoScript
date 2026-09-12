# Requirements: AzurLaneAutoScript (Alas)

**Defined:** 2026-09-12  
**Core Value:** 在保障自动化识别极高准确率与稳定容错的同时，实现低资源损耗、静默流畅的 7×24 小时无人值守挂机。

## v1 Requirements

Requirements for initial release (v1.0 弱机性能轻量化与 7×24h 挂机稳定性). Each maps to roadmap phases.

### Electron 客户端轻量化与显存保护 (DESK)

- [ ] **DESK-01**: 系统启动 Electron 时自动绑定 Intel HD 4600 核显，移除全局 `--disable-gpu` 导致的 CPU 软件光栅化过载，释放 GTX 960M 2GB 独显给模拟器
- [ ] **DESK-02**: Electron 窗口处于失去焦点 (blur) 状态时，自动降低渲染帧率至 5 FPS，减少非激活状态下的 CPU/GPU 占用
- [ ] **DESK-03**: Electron 窗口处于最小化 (minimize) 或缩入托盘状态时，自动限制渲染帧率至 1 FPS 并挂起重绘管线，大幅降低挂机功耗
- [ ] **DESK-04**: Electron 主进程监听 GPU 进程崩溃 (`child-process-gone`)，在发生显卡 TDR 或显存耗尽时自动降级或平滑重载渲染视图，不造成桌面客户端闪退及后台 Python 任务中断
- [ ] **DESK-05**: Electron 窗口隐藏/最小化期间，主动调用 Win32 工作集修剪规整物理内存 (`EmptyWorkingSet`)，使常驻内存降低至 30MB 级别

### WebUI 日志流控与 DOM 截断 (WEBUI)

- [ ] **WEBUI-01**: 当 WebUI 标签页不可见 (`document.visibilityState === "hidden"`) 或日志折叠时，前端自动暂停日志 DOM 渲染与 WebSocket 高频推流（降为 0Hz）
- [ ] **WEBUI-02**: WebUI 日志容器实施严格的环形滑动截断 (FIFO)，前台挂载 DOM 行数硬性限制在 150 条以内，杜绝 7×24 小时运行下的 Chromium 内存泄漏与卡顿
- [ ] **WEBUI-03**: 引入视口高度补偿与 `overflow-anchor: none` 样式，确保日志自动截断时滚动条平滑不闪烁、不发生异常跳动
- [ ] **WEBUI-04**: 页面重新唤醒切回前台时，执行单次最新快照批量补偿渲染，快速呈现最新 100 行日志，避免历史全量重放造成的浏览器卡死
- [ ] **WEBUI-05**: WebUI 后台提供轻量应用层心跳机制（30s 周期），防止长空闲无日志期间 WebSocket 连接被超时掐断 (Code 1006)

### 自动化循环自适应能效提升 (CORE)

- [ ] **CORE-01**: `ModuleBase.loop()` 实施状态感知型三阶梯自适应休眠：稳态自律战斗与长动画等待阶段，截图检测间隔放宽至 1.0s~1.2s，大幅削减空转 CPU 占用
- [ ] **CORE-02**: 交互敏感期与画面状态改变瞬间（`appear()` 命中或触发 `click()`），自适应休眠计时器立即 0ms 唤醒复位，保证 S 胜结算与关键弹窗响应时间 <1.5s
- [ ] **CORE-03**: 自动化初始化检测到运行于 MuMu 模拟器时，强制锁死并自适应守护 NemuIPC 共享内存截图通道（5~15ms 延迟，CPU 占用 < 1%），杜绝意外回退到低效 ADB 截图
- [ ] **CORE-04**: 调度器在长时脱机/等待下一任务期间 (`wait_until`)，轮询间隔由 5s 动态放宽至 15s，并完全断开设备截图连接释放句柄

### 7×24h 挂机内存守护与防泄漏 (MEM)

- [ ] **MEM-01**: 错误排查截图缓冲队列 (`screenshot_deque`) 改用 JPEG 内存字节流压缩编码（单帧从 2.76MB 压缩至 50~80KB，内存占用削减 98%）
- [ ] **MEM-02**: 弱机环境下错误截图队列容量硬性钳制为 30~50 帧，将 60 帧错误回溯全量内存锁定在 5MB 以内
- [ ] **MEM-03**: 战役出击结算与任务交界点 (`TaskEnd`) 触发软资源清理 (`release_resources`)，注销非活动 OCR 实例并触发代际垃圾回收
- [ ] **MEM-04**: 任务交界长等待期间调用 Win32 `EmptyWorkingSet`，将闲置 Alas 进程未引用的物理工作集主动归还 Windows 操作系统，缓解 15.8GB PageFile 换页压力
- [ ] **MEM-05**: 调度器引入子进程常驻内存 (RSS) 与存活健康巡检看门狗，并在任务空闲安全期执行无感优雅回收 (Graceful Recycling)

### 弱机环境与 MuMu 12 协同调优指南 (ENV)

- [ ] **ENV-01**: 提供《双显卡硬件分流与 Windows 图形首选项设置指南》，引导将 MuMu 绑定至独显 Nvidia GTX 960M，Thorium 浏览器与 Alas Electron 绑定至核显 Intel HD 4600
- [ ] **ENV-02**: 提供《Haswell i5 双核移动平台 MuMu 12 最佳协同配置指南》，明确推荐分配 2 核/3GB 内存、渲染帧率锁定 20~30 FPS、关闭“后台挂机时保活运行”以确保 NemuIPC 稳定生效

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### 极限性能探针与原生绑定 (EXTREME)

- **EXTREME-01**: 基于 C++/Rust 的轻量级原生桌面管理窗口替代 Electron
- **EXTREME-02**: 纯无头守护进程模式 (Headless Daemon) 与命令行轻量状态看板

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| 全局无条件禁用硬件加速 (`disableHardwareAcceleration`) | 会迫使双核 Haswell CPU 运行软件光栅化，反向拉满 CPU 导致视频直播卡顿 |
| 战斗中过激休眠 (>2.5s) | 会严重拖慢结算效率、错过潜艇呼叫或剧情跳过，甚至导致超时沉船 |
| 窗口隐藏时完全销毁 WebContents | 导致用户配置表单数据丢失，且唤醒需耗时 2~4 秒白屏重建会话 |
| 引入庞大的第三方虚拟长列表库 | 破坏 PyWebIO 基于 jQuery 的服务端注入契约，增加通信开销 |
| 降低游戏内画面基准分辨率至 720p 以下 | Alas 全模块坐标体系与 assets 资产强绑定 1280×720，下调会导致图像匹配全面失效 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DESK-01 | Phase 1 | Pending |
| DESK-02 | Phase 1 | Pending |
| DESK-03 | Phase 1 | Pending |
| DESK-04 | Phase 1 | Pending |
| DESK-05 | Phase 1 | Pending |
| WEBUI-01 | Phase 2 | Pending |
| WEBUI-02 | Phase 2 | Pending |
| WEBUI-03 | Phase 2 | Pending |
| WEBUI-04 | Phase 2 | Pending |
| WEBUI-05 | Phase 2 | Pending |
| CORE-01 | Phase 3 | Pending |
| CORE-02 | Phase 3 | Pending |
| CORE-03 | Phase 3 | Pending |
| CORE-04 | Phase 3 | Pending |
| MEM-01 | Phase 4 | Pending |
| MEM-02 | Phase 4 | Pending |
| MEM-03 | Phase 4 | Pending |
| MEM-04 | Phase 4 | Pending |
| MEM-05 | Phase 4 | Pending |
| ENV-01 | Phase 5 | Pending |
| ENV-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-12*
*Ready for roadmap: yes*
