# Phase 4: 7×24 小时挂机内存守护与防泄漏 - Context

**Gathered:** 2026-09-12
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段专注为 Alas 构筑面向 7×24 小时无人值守挂机的底层物理内存屏障与防泄漏机制，切实缓解弱机双核 i5-4210H、16GB 物理内存但承受高达 15.8GB 虚拟内存（PageFile）换页压力下的磁盘颠簸与 OOM 风险。交付物包括：
1. 错误截图队列 `screenshot_deque` 改用 JPEG 内存流高倍压缩（体积降幅 98%）与安全容量上限（默认 60 帧，钳制 100 帧）。
2. 任务交接边界与调度空闲长等待期执行「模版/OCR缓存注销 → 全代际 gc.collect() → Win32 EmptyWorkingSet() 物理页修剪」三部曲闭环。
3. 平台内存抽象工具库封装（Windows 下调用 PSAPI，非 Windows 静默降级）。
4. 多进程调度器对子进程 RSS 实施巡检看门狗（600MB 警戒阈值、任务边界安全热重启、僵死 180s 强杀与 48h 低峰期主动换茬）。

不包含：重写底层 OCR 模型、全局定时硬重启模拟器或更改游戏 720p 基准分辨率。
</domain>

<decisions>
## Implementation Decisions

### 错误截图队列压缩与存储 (Error Screenshot Compression & Retention)
- **D-01: JPEG 质量 80 编码**：在 `module/device/screenshot.py` 的 `screenshot_deque.append` 时，使用 `cv2.imencode('.jpg', self.image, [cv2.IMWRITE_JPEG_QUALITY, 80])` 存入内存字节流。单帧由裸存 2.76MB 暴降至 50~70KB（压缩率 98%），文字与 UI 边缘无明显伪影，兼顾排查还原度与内存压制。
- **D-02: 默认 60 帧，上限钳制 100 帧**：`Error_ScreenshotLength` 默认采用 60 帧，最高允许配置 100 帧（总内存稳定在 3.6MB~6MB）。可完整回溯报错前 6~10 秒的所有操作上下文。
- **D-03: 直接直写 .jpg + 按需惰性解码**：系统捕获异常触发落盘时，直接以二进制流 `f.write(compressed_bytes)` 写入 `.jpg`，零二次编解码 CPU 损耗；对访问 `frame['image']` 的历史调用提供按需惰性解码（`cv2.imdecode`），保持 100% 接口兼容。
- **D-04: 天然滑动队列生命周期**：任务交接时不主动清空队列，保持滑动窗口滚动，保留跨任务边界最近的 60 帧排查现场。

### Win32 工作集修剪与 GC 触发策略 (Working Set Trimming & GC Cadence)
- **D-05: 触发时机**：在「任务交接边界（完成大任务进入下一个任务前）」与「调度器长等待空闲期（`device.release_during_wait` / `wait_until`）」触发修剪，绝不侵入战斗自律或寻路高频截图循环。
- **D-06: 三部曲标准闭环**：严格遵循「模版/OCR 缓存注销 → `gc.collect()` 循环垃圾回收 → `EmptyWorkingSet()` 物理工作集归还」标准顺序，确保死对象彻底解引用后再释放物理页。
- **D-07: 进程职责分工**：任务工作子进程在任务边界使用 `GetCurrentProcess()` 自管修剪（零跨进程权限隐患）；主进程/调度服务在后台空闲或长等待期独立低频修剪自身。
- **D-08: 跨平台抽象适配库**：封装为 `module/base/memory_utils.py`，检测 `sys.platform == 'win32'` 时动态加载 `ctypes.windll.psapi.EmptyWorkingSet`，非 Windows 或调用失败时平滑降级（仅执行缓存注销与 `gc.collect()`），零崩溃风险。

### 子进程 RSS 看门狗与安全重启 (Subprocess RSS Watchdog & Safe Recycle)
- **D-09: 600MB 两阶段泄漏判定**：正常 Alas 子进程约 200~300MB；看门狗巡检发现 RSS > 600MB 时，首先在任务边界触发深度修剪，若修剪后仍 > 500MB，确认为顽固底质泄漏，标记为待重启。
- **D-10: 任务边界平滑热重启**：子进程被标记为待重启后，必须等待当前出击/任务执行完毕、安全返回游戏主界面或进入任务调度队列待机点时，由 `ProcessManager` 触发毫秒级热重启，无缝衔接下一个任务，保证 0 石油损耗与 0 扣分。
- **D-11: 僵死超时保底强杀**：若子进程超过 180 秒完全无日志输出且无截图活动，判定为底层 C 扩展死锁或模拟器 IPC 假死，看门狗强制终止并拉起新子进程恢复。
- **D-12: 48 小时夜间主动换茬**：即使内存未超标，子进程连续运行满 48 小时且处于凌晨 4:00~5:00 低峰空闲时，主动执行一次安全热重启，彻底铲除 CPython 底层碎片。

### Agent's Discretion (裁量权落实)
- 用户在 Area 3（子进程 RSS 看门狗）全权委托由构建者决定，上述 D-09 ~ D-12 的阈值设定（600MB/500MB）、任务边界安全点热重启、180s 僵死保底及 48h 夜间主动换茬均已作为核心工程决策固化。
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 内存管理与错误截图核心源码
- `module/device/screenshot.py` — 截图队列 `screenshot_deque` 定义、`save_screenshot` 存储逻辑与容量限制
- `module/base/resource.py` — `release_resources()`、模板与 OCR 缓存释放、垃圾回收入口
- `alas.py` — 任务调度主循环、任务交接点与长等待空闲调用
- `module/webui/process_manager.py` — 子进程生命周期、启动与重启接口

### 调研成果与反模式防坑指南
- `.planning/research/ARCHITECTURE.md` §2.3, §4.4 — 内存屏障与 Win32 Working Set 机制设计
- `.planning/research/PITFALLS.md` Pitfall 7, Pitfall 9 — C 堆句柄损毁规避与 15.8GB PageFile 换页雪崩防护
- `.planning/research/SUMMARY.md` Phase 4 — Phase 4 目标与交付清单
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `module.base.decorator.cached_property` & `del_cached_property`: `Resource` 类已使用该机制管理缓存，可直接复用进行模板注销。
- `module.device.screenshot.Screenshot.screenshot_deque`: 原生 `collections.deque`，支持 `maxlen`，改造时仅需改变追加元素的数据结构并包装访问器。
- `module.webui.process_manager.ProcessManager`: 已具备 `restart_processes(instances)` 和 `kill()` 逻辑，可扩展 RSS 监控线程与状态标记。

### Established Patterns
- `release_resources(next_task)` 已经作为任务交接的标准钩子存在于 `alas.py`，在此处接入三部曲是最少侵入且能覆盖所有自动化场景的设计。
- 图像数据一律由 `cv2` (OpenCV) 矩阵承载，利用 `cv2.imencode` / `cv2.imdecode` 零额外依赖。

### Integration Points
- `module/base/memory_utils.py` (新建): 封装 `empty_working_set()`、`get_process_rss()`、`trim_memory()` 跨平台接口。
- `module/device/screenshot.py`: 在 `self.screenshot_deque.append(...)` 处集成 JPEG 压缩，提供兼容解包。
- `module/base/resource.py`: 激活 `gc.collect()` 并调用 `trim_memory()`。
- `alas.py`: 在任务开始前和结束后触发内存检查。
- `module/webui/process_manager.py`: 增加看门狗轮询逻辑。
</code_context>

<specifics>
## Specific Ideas

- JPEG 压缩品质定为 80，兼顾高压缩比与 OCR/排查可读性。
- 存盘时以二进制流直接写入 `.jpg`，避免二次 decode + encode 的 CPU 开销。
- 严格杜绝在每帧截图轮询中执行 `gc.collect()` 或 `EmptyWorkingSet()`，避免高频 CPU 尖峰。
</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed strictly within Phase 4 scope.
</deferred>

---
*Phase: 4-7×24 小时挂机内存守护与防泄漏*
*Context gathered: 2026-09-12*
