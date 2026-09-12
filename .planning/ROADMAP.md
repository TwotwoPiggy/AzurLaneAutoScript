# Roadmap: AzurLaneAutoScript (Alas)

## Overview

本项目聚焦在双核/移动端老旧硬件（i5-4210H、GTX 960M、HD 4600、15.8GB 虚拟内存换页压力）与并发 Thorium 浏览器直播硬解的高压场景下，对 Alas 展开全方位的轻量化与稳定性重塑。通过外壳渲染分流、前端日志截断、核心循环能效自适应、挂机内存守护与系统协同配置 5 个阶段，彻底实现 7×24 小时低资源顺畅挂机。

## Phases

- [ ] **Phase 1: Electron 桌面端轻量化与 GPU 保护** - 绑定核显，阶梯降频失焦帧率，增加 GPU 崩溃与 TDR 容灾
- [ ] **Phase 2: WebUI 前端与日志流控** - 可见性门禁，150条 DOM 滑动截断与心跳防假死
- [ ] **Phase 3: Python 自动化核心能效与通讯调优** - 状态感知自适应休眠与 NemuIPC 零 CPU 截屏守护
- [ ] **Phase 4: 7×24 小时挂机内存守护与防泄漏** - JPEG 内存流压缩截图队列，空闲边界 EmptyWorkingSet 物理工作集修剪与看门狗
- [ ] **Phase 5: 弱机与模拟器协同最佳配置** - 双显卡硬分流与 MuMu 12 性能及无缝连接调优指南

## Phase Details

### Phase 1: Electron 桌面端轻量化与 GPU 保护

**Goal**: 消除 CPU 软件光栅化，将渲染路由至 HD 4600 核显，失焦/最小化阶梯降频至 1~5 FPS 并增加 GPU 崩溃容灾
**Depends on**: Nothing (first phase)
**Requirements**: DESK-01, DESK-02, DESK-03, DESK-04
**Success Criteria**:

  1. Electron 桌面端在双显卡环境下稳定运行在 Intel HD 4600 核显上，独显 GTX 960M 零渲染占用
  2. 窗口失焦时渲染帧率降至 5 FPS，最小化/托盘时降至 1 FPS，后台 CPU 占用趋近 0%
  3. 发生显卡 TDR 或 GPU 进程崩溃时，Electron 能够捕获异常并平滑重试/降级，Alas 后台调度不中断
  4. Electron V8 堆内存被限制在安全上限内（128MB），避免前端常驻内存无节制上涨

**Plans**: TBD

### Phase 2: WebUI 前端与日志流控

**Goal**: 解决长时间挂机下的前端内存暴增与无效 WebSocket 渲染开销
**Depends on**: Phase 1
**Requirements**: WEB-01, WEB-02, WEB-03, WEB-04
**Success Criteria**:

  1. 页面隐藏/切后台时停止向 DOM 追加日志，消除后台无效计算
  2. WebUI 挂载的 DOM 节点被滑动截断在 150 条以内，滚动锚定稳定不跳动
  3. 后台恢复激活时秒级单次快照补偿最新日志
  4. 30s 轻量心跳保障长连接，彻底解决 WebSocket 1006 异常断开

**Plans**: TBD

### Phase 3: Python 自动化核心能效与通讯调优

**Goal**: 将能效优化注入自动化基类与截图管道，消除常态 CPU 空转
**Depends on**: Phase 2
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04
**Success Criteria**:

  1. 战役自律稳态阶段主循环休眠放宽至 1.0~1.2s，按钮断言命中或关键转场 0ms 瞬间唤醒
  2. MuMu 12 环境下锁死 NemuIPC 共享内存通道（延迟 <10ms，CPU <1%）
  3. 废除 PyThreadState_SetAsyncExc 截屏强杀，根除 C 堆损毁与 rpc 1722 报错
  4. 静态转场画面自适应退避降频，CPU 总体空转降低 40%+

**Plans**: TBD

### Phase 4: 7×24 小时挂机内存守护与防泄漏

**Goal**: 构筑底层的物理内存屏障，防范长时间无人值守下的 OOM 与换页卡顿
**Depends on**: Phase 3
**Requirements**: MEM-01, MEM-02, MEM-03, MEM-04
**Success Criteria**:

  1. screenshot_deque 采用 JPEG 内存流压缩存储，单帧内存从 2.8MB 降至 60KB，60 帧错误回溯仅占 ~3MB
  2. 任务交接与出击结算处执行模版/OCR 缓存清理与软 gc.collect()
  3. 引入 Win32 EmptyWorkingSet 接口在空闲时主动修剪未引用物理工作集，缓解 15.8GB 虚拟内存换页压力
  4. 多进程调度器对子进程 RSS 实施巡检看门狗，在任务安全点自愈异常泄漏进程

**Plans**:
**Wave 1**

  - [ ] 04-01-PLAN.md — 错误截图队列 JPEG 内存流高倍压缩与回溯容量控制 (MEM-01)

**Wave 2** *(blocked on Wave 1 completion)*

  - [ ] 04-02-PLAN.md — Win32 物理工作集修剪工具封装与任务边界 GC 闭环 (MEM-02, MEM-03)

**Wave 3** *(blocked on Wave 2 completion)*

  - [ ] 04-03-PLAN.md — 多进程调度器子进程 RSS 巡检看门狗与安全自愈 (MEM-04)

### Phase 5: 弱机与模拟器协同最佳配置

**Goal**: 输出软硬件协同最佳配置指南，确保系统级调优落地
**Depends on**: Phase 4
**Requirements**: ENV-01, ENV-02, ENV-03
**Success Criteria**:

  1. 提供清晰的 Windows 图形性能首选项硬分流配置步骤
  2. 提供 MuMu 12 性能（核数、帧率、关闭后台保活）调优参数指导
  3. 提供低配平台虚拟内存与 TDR 防护调优建议

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Electron 桌面端轻量化与 GPU 保护 | 0/0 | Not started | - |
| 2. WebUI 前端与日志流控 | 0/0 | Not started | - |
| 3. Python 自动化核心能效与通讯调优 | 0/0 | Not started | - |
| 4. 7×24 小时挂机内存守护与防泄漏 | 0/3 | In progress | - |
| 5. 弱机与模拟器协同最佳配置 | 0/0 | Not started | - |
