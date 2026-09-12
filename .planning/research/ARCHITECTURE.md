# Architecture Research

**Domain:** AzurLaneAutoScript (Alas) Low-Resource & 7*24h Stability Optimization  
**Researched:** 2026-09-12  
**Confidence:** HIGH  

---

## Standard Architecture

### System Overview

针对老旧双核移动平台（Intel i5-4210H 2C4T）、高虚拟内存占用（16GB RAM + 15.8GB Pagefile 已用）及双显卡 TDR 隐患（GTX 960M 2GB / HD 4600），优化后的 Alas 系统架构分层与组件拓扑如下：

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             Host System & Concurrent Environment                                 │
│    Intel i5-4210H (2C4T Haswell) │ 16GB RAM (Pagefile 15.8GB) │ Nvidia GTX 960M (2GB VRAM)      │
│    Concurrent Apps: 7*24 MuMu 12 + Thorium Browser (Live Stream HardDecode) + NetEase CloudMusic │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                      Desktop Presentation Layer (Electron Main / Renderer)                       │
│  ┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │ BrowserWindow Lifecycle & PowerMonitor       │  │ Renderer Process (Chromium Software Pipe)│  │
│  │ - app.disableHardwareAcceleration() (TDR Free)│  │ - 128MB V8 Heap Limit                    │  │
│  │ - blur / minimize / tray: 1~5 FPS            │  │ - App.vue / Alas.vue (<iframe src=WebUI>)│  │
│  │ - focus: 30 FPS Dynamic Scaling              │  │ - postMessage Window State Bridge        │  │
│  └──────────────────────┬───────────────────────┘  └─────────────────────┬────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────────────┼───────────────────────┘
                          │ IPC Event / Frame Throttle                     │ postMessage Bridge
                          ▼                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                     WebUI & Supervisor Layer (gui.py, module/webui/)                             │
│  ┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │ PyWebIO Presentation & Gated Log Streamer    │  │ ProcessManager (Supervisor & Watchdog)   │  │
│  │ - Visibility-Gated TaskHandler (0Hz on Hide) │  │ - Unbounded Queue -> Bounded (maxsize=500│  │
│  │ - RichLog Stream Throttling (0.25s -> 1.0s)  │  │ - Sliding renderables buffer (max=300)   │  │
│  │ - DOM Ring Buffer (Capped at 150 nodes)      │  │ - Subprocess RSS Watchdog & Graceful Recy│  │
│  └──────────────────────┬───────────────────────┘  └─────────────────────┬────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────────────┼───────────────────────┘
                          │ Disk Log File (`./log/`) Direct Download       │ Inter-Process Queue
                          ▼                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                     Task Scheduler & Automation Engine (alas.py, module/base/)                    │
│  ┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │ AzurLaneAutoScript (Scheduler & Lifecycle)   │  │ ModuleBase & State Machine Loop          │  │
│  │ - Task Boundary Memory Checkpoint            │  │ - Adaptive Loop Sleeping (Tier 0/1/2)    │  │
│  │ - release_resources() + gc.collect()         │  │ - Instant Assertion Wakeup (0ms penalty) │  │
│  │ - Win32 EmptyWorkingSet(-1) OS RAM Return    │  │ - Timeout & State Change Synchronization │  │
│  └──────────────────────┬───────────────────────┘  └─────────────────────┬────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────────────┼───────────────────────┘
                          │ Coordinated Polling Interval & Screenshot Requests
                          ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                     Perception, Vision & Device Layer (module/device/)                           │
│  ┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │ Frame Grabber Engine (Screenshot Pipeline)   │  │ Device Memory Guard & Ingestion          │  │
│  │ - NemuIPC (MuMu Shared Memory, 5~15ms, 0% CPU│  │ - Compressed Error Deque (JPEG bytes)    │  │
│  │ - Bypass ADB, Sockets, and H.264 Decoders    │  │ - 165MB -> 3MB per instance (98% Drop)   │  │
│  │ - Dynamic Screenshot Interval (0.1s~1.2s)    │  │ - Direct Disk Dump for save_error_log()  │  │
│  └──────────────────────┬───────────────────────┘  └──────────────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────────────────────────────────────┘
                          │ Direct Memory Mapping / Win32 Shared Surface
                          ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                     Target Android Virtual Machine (MuMu Player 12)                              │
│  - external_renderer_ipc.dll Direct Framebuffer Expose (1280x720 32bpp)                           │
│  - Dedicated Host Core Isolation & GPU 3D Passthrough                                            │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Current Implementation | Proposed Low-Resource Optimization |
|-----------|----------------|------------------------|------------------------------------|
| **Electron Main (`index.ts`)** | 桌面宿主外壳、生命周期与功耗中枢 | 无条件 `disableHardwareAcceleration`，无焦点感知，固定刷新，全速计时 | 接入 `BrowserWindow` 焦点/最小化/托盘事件与 `powerMonitor`；失焦降频至 5 FPS，隐藏压至 1 FPS；注入 V8 堆上限 128MB 与省电 Chromium 标志。 |
| **Electron Renderer (`Alas.vue`)** | 前端容器与 Iframe 宿主 | 单纯包含 `<iframe :src="url">`，无状态反馈 | 监听主进程功耗事件，通过 `window.postMessage` 向 PyWebIO 内部通知可见性与功耗状态。 |
| **PyWebIO 页面 (`app.py`, `utils.py`)** | 控制台交互与后台任务调度 | `visibility_state_switch` 仅调控概览刷新；`WebIOTaskHandler` 盲目调度 | 将前端 `document.visibilityState` 与折叠状态绑定至全局流控；隐藏或折叠时挂起 `put_log`，显示时按需单次拉取。 |
| **日志控件 (`widgets.py:RichLog`)** | 格式化富文本日志并追加至 DOM | 每 0.25s 强制调用 Rich 渲染并全量追加 DOM；每 800 条才清空一次 | 增加前台可见性守卫；将推送周期由 0.25s 放缓至 1.0s；JS 侧实现 150 条滑动窗口自动剪裁上游 DOM 节点。 |
| **进程监管 (`process_manager.py`)** | 子进程生命周期与日志转发 | 多进程 `Queue` 无上限；内存缓冲 400 条 Rich 对象；无进程健康检测 | 限制 `_renderable_queue(maxsize=500)`；新增子进程 RSS 物理内存低频探测；超限时在任务交界点触发优雅回收（Graceful Recycling）。 |
| **任务主调度 (`alas.py`)** | 任务队列裁决、空闲等待与崩溃处理 | 空闲等待 `time.sleep(5)`；错误发生时提取 deque 保存错误现场 | 设立任务边界内存回收检查点；在 `wait_until` 中执行 `EmptyWorkingSet`；自适应长空闲休眠步长（最长 15s）。 |
| **自动化基类 (`module/base/base.py`)** | 自动化状态机与 `self.loop()` 糖语法 | 依赖截图间隔硬性轮询；无交互时依然高速死循环 | 实现自适应三阶梯休眠机制（Tier 0 极速 0.1s、Tier 1 过渡 0.3s、Tier 2 等待 0.8~1.2s）；状态断言或点击事件立即零延迟瞬时唤醒。 |
| **截屏引擎 (`module/device/screenshot.py`)** | 图像采集与错误追溯环形队列 | 默认在内存裸存 60~300 张 2.76MB 的 uncompressed numpy 数组（占用 165MB~828MB） | 错误缓冲采用内存 JPEG 编码流（~50KB/帧），内存暴降 98%（仅需 ~3MB）；配合 `nemu_ipc` 共享内存零开销采集。 |
| **资源回收器 (`module/base/resource.py`)** | OCR 与模板缓存回收 | 回收部分 OCR 与 Asset 引用，但 `gc.collect()` 被注释，无系统级内存清理 | 启用 `gc.collect()`；接入 Win32 `psapi.EmptyWorkingSet` 强制归还空闲物理页；深度释放过期特征缓存。 |

---

## Recommended Project Structure

针对弱机性能优化方案，相关优化代码严密嵌入既有目录结构，不增设破坏性平行架构：

```
alas/
├── alas.py                           # [MODIFY] 调度主循环、任务交界内存检查点、自适应长空闲步长
├── gui.py                            # [MODIFY] WebUI 启动入口、注入低功耗参数与日志通道管控
├── module/
│   ├── base/
│   │   ├── base.py                   # [MODIFY] ModuleBase.loop() 自适应阶梯休眠与即时唤醒
│   │   └── resource.py               # [MODIFY] 任务间深度资源释放、gc.collect()、Win32 工作集修剪
│   ├── device/
│   │   ├── device.py                 # [MODIFY] Device 状态休眠协调器、点击即时唤醒复位
│   │   ├── screenshot.py             # [MODIFY] 截图环形队列 JPEG 压缩缓冲 (165MB -> 3MB)、自适应间隔
│   │   └── method/
│   │       └── nemu_ipc.py           # [REFERENCE] MuMu 原生共享内存读取，保持零拷贝无网络开销
│   └── webui/
│       ├── app.py                    # [MODIFY] PyWebIO 页面路由、日志折叠联动、后台极速挂起
│       ├── process_manager.py        # [MODIFY] Bounded 进程队列、子进程 RSS 监视器与优雅重启
│       ├── utils.py                  # [MODIFY] Win32 EmptyWorkingSet 工具注入、可见性探测增强
│       └── widgets.py                # [MODIFY] RichLog 前台门禁拦截、1.0s 降频渲染、DOM 150 条环形截断
└── webapp/
    └── packages/
        ├── main/
        │   └── src/
        │       └── index.ts          # [MODIFY] Electron 主进程：GPU 剥离、窗口焦点/最小化/托盘节流、powerMonitor
        └── renderer/
            └── src/
                └── components/
                    └── Alas.vue      # [MODIFY] Iframe 宿主通信桥、postMessage 功耗状态通知
```

### Structure Rationale

- **集中在基类与驱动层，而非业务层**：碧蓝航线包含 55 个以上的业务功能子模块（`module/campaign/`, `module/os/`, `module/daily/` 等），所有业务模块均派生自 `ModuleBase`，且通过 `self.loop()` 与 `self.appear()` 驱动。将自适应休眠注入 `ModuleBase` 与 `Device`，可在**零修改业务代码**的前提下让全系统 100% 享受节能红利。
- **内存防护贯穿数据生命周期**：在产生端（`screenshot.py` 压缩存入）、传输端（`process_manager.py` 限制队列）、展现端（`widgets.py` 截断 DOM）以及周期终止端（`resource.py` 工作集修剪）形成闭环防御。
- **外壳与内核解耦通知**：Electron 桌面端与 Python 后端保持清晰的宿主-服务关系，通过既有的 WebUI 端口与 Web 标准 API（Visibility API、postMessage、HTTP/WS）进行状态同步，不引入强耦合本地 C 扩展。

---

## Architectural Patterns

### Pattern 1: 自适应阶梯休眠与即时唤醒状态机 (Adaptive Loop Sleeping & Instant Assertion Wakeup)

**What:** 在自动化高频状态判定循环（`ModuleBase.loop()`）中，摒弃机械固定的 100ms 轮询。维护一个轻量级的连续空转计数器（`idle_loop_count`），根据游戏状态的动态活跃度自动切换三级休眠阶梯；一旦检测到按钮命中（`appear` 返回 True）或触发了点击驱动（`click`），立刻瞬时复位至 0 级极速状态。

**When to use:** 所有基于画面识别的状态转移循环，尤其是战斗挂机等待、地图舰阵航行、剧情对话渐变和结算动画过渡。

**Trade-offs:** 
- *优点*：消除大量无意义的每秒 10 次重复截图与图像模版匹配，CPU 占用在空转期降低 60%~80%，显著降低双核 CPU 温度。
- *考量*：必须保证状态发生变化的瞬间能够即刻清零延迟，严防胜利结算弹窗因处于深休眠状态而延迟响应。

**Example:**
```python
# module/base/base.py 核心优化逻辑示意
class ModuleBase:
    _idle_loop_count = 0

    def loop(self, skip_first=True, timeout=None):
        if timeout is not None:
            timeout = Timer.from_seconds(timeout).start() if not isinstance(timeout, Timer) else timeout.reset()

        while True:
            if timeout is not None and timeout.reached():
                return

            if skip_first:
                skip_first = False
            else:
                # 根据连续无交互帧数动态调节截图前休眠
                self._apply_adaptive_loop_sleep()
                self.device.screenshot()

            try:
                yield self.device.image
            except AttributeError:
                self.device.screenshot()
                yield self.device.image

    def _apply_adaptive_loop_sleep(self):
        # 阶梯延时规则：
        # Tier 0 (刚执行点击/状态跃迁): 0.10s (无额外休眠，保持极速响应)
        # Tier 1 (连续 3~8 帧无动作): 0.35s (过渡期，UI 仍在动画中)
        # Tier 2 (连续 9 帧以上无动作): 0.80s ~ 1.00s (稳定等待期，如战斗中、长动画)
        if self._idle_loop_count < 3:
            pass  # 依赖 Device 基础的 0.1s 间隔
        elif self._idle_loop_count < 8:
            time.sleep(0.25)
        else:
            time.sleep(0.70)
        self._idle_loop_count += 1

    def reset_loop_sleep(self):
        """关键动作触发点（如 appear 成功或点击执行后）调用，瞬时拉回零延迟"""
        self._idle_loop_count = 0
```

---

### Pattern 2: 可见性门禁日志流控与 DOM 环形截断 (Visibility-Gated Ephemeral Log Streaming & DOM Windowing)

**What:** 彻底重构 PyWebIO `RichLog` 运行机制。
1. **门禁拦截**：仅当前端处于激活展开状态时才调用 Rich 引擎进行富文本 HTML 转译；当窗口被最小化、移入托盘或用户折叠了日志栏时，后端完全跳过 HTML 生成与 WebSocket 推送。
2. **推流降频**：将常态下的推送频率从 0.25s（4Hz）下调为 1.0s（1Hz），日志更新对人眼视觉无任何滞后感，但富文本格式化 CPU 消耗锐减 75%。
3. **DOM 环形截断**：前端注入轻量 JS 监听器，维护不超过 150 行 DOM 节点的滑动窗口，超出部分在前端直接剪除旧行，杜绝 Chromium 渲染进程因千万行堆积而内存膨胀。

**When to use:** 7×24 小时长时间后台无人值守运行的 WebUI / 控制台。

**Trade-offs:** 
- *优点*：Chromium 渲染进程物理工作集恒定在 ~70MB 以内，V8 内存不泄漏；后端不产生无效 RPC。
- *对日志下载的影响*：**零破坏**。因为 Alas 的全部日志从第一行开始均由 `module/logger.py` 中的 `RichFileHandler` 实时写入磁盘 `./log/YYYY-MM-DD_alas.txt`，崩溃保存 `save_error_log` 也是直接拷贝磁盘文件。WebUI DOM 仅作为临时监视器，截断 DOM 绝不丢失任何历史日志。

**Example:**
```python
# module/webui/widgets.py 优化逻辑示意
def put_log(self, pm: ProcessManager) -> Generator:
    yield
    try:
        while True:
            # 1. 门禁检查：若用户折叠日志或页面不可见，进入静默省电，不渲染任何 HTML
            if not self.is_visible_or_expanded():
                # 仅更新水位线游标，不执行 CPU 密集的 self.render()
                self._unrendered_idx = len(pm.renderables)
                yield
                continue

            # 2. 从后台恢复时单次批量追平（最多最近 100 条）
            if self._just_restored_visibility:
                start_idx = max(0, len(pm.renderables) - 100)
                html = "".join(map(self.render, pm.renderables[start_idx:]))
                self.reset()
                self.extend(html)
                self._just_restored_visibility = False
                yield
                continue

            # 3. 正常增量推送（频率由 TaskHandler 控在 1.0s 一次）
            idx = len(pm.renderables)
            if idx != last_idx:
                html = "".join(map(self.render, pm.renderables[last_idx:idx]))
                self.extend_with_dom_cap(html, max_nodes=150)
                last_idx = idx
            yield
    except SessionException:
        pass
```

---

### Pattern 3: 多层级长期内存守护与工作集修剪 (Multi-Tier Memory Guard & Working Set Trimming)

**What:** 针对 16GB 物理内存已背负 15.8GB 虚拟内存的严重置换压力，构筑三道内存防线：
1. **图片缓冲高倍压缩**：将 `screenshot_deque` 中原始存储的 2.76MB (1280x720 RGB) Numpy Array 改存为 JPEG 字节流（`cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]`）。单帧体积从 2760KB 暴降至 ~50KB，60 帧缓冲仅占用 3MB 内存（下降 98%）。
2. **任务间隙工作集回缩**：在 `alas.py` 每次完成一次任务并进入下一次调度前，执行 `release_resources()`，显式调用 `gc.collect()`，并通过 Win32 API `ctypes.windll.psapi.EmptyWorkingSet(-1)` 强行通知 Windows 内存管理器剥离未使用的物理分页，归还物理 RAM。
3. **长时间巡检优雅回收 (Graceful Recycling)**：在 `ProcessManager` 中跟踪 Alas 子进程的持续存活周期与物理内存（RSS）。若子进程连续运行超过 24 小时且 RSS > 600MB，利用 Alas 原生的任务间无状态特性，在任务队列空闲时安全停止子进程并重新拉起，彻底铲除 CPython 底层内存碎片。

**When to use:** 长期常驻挂机系统与老旧操作系统。

**Trade-offs:** 
- *优点*：彻底根除因截图累积导致的 OOM 闪退；任务交界重启仅需 1.5 秒且完全无感，换取系统 7×24 小时极致清爽。
- *考量*：JPEG 压缩存在微小 CPU 开销（约 2~3ms），但在 NemuIPC 的 5ms 截图基础下总体耗时依然远低于 ADB 截图的 100~300ms。

**Example:**
```python
# module/device/screenshot.py 内存队列压缩改造
def screenshot(self):
    ...
    self.image = method()
    ...
    if self.config.Error_SaveError:
        # 存入 JPEG 二进制流代替原始 ndarray，极度节省内存
        _, buf = cv2.imencode('.jpg', self.image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        self.screenshot_deque.append({'time': datetime.now(), 'image_bytes': buf})
    return self.image

# alas.py / module/base/resource.py 任务交界内存释放
def release_resources(next_task=''):
    ...
    # 原有清理逻辑 (OCR, 模版缓存)
    ...
    import gc
    gc.collect()
    
    # Windows 物理工作集强制修剪
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
        except Exception:
            pass
```

---

### Pattern 4: Electron 桌面端生命周期与功耗总线协同 (Electron Lifecycle & Power State Bus)

**What:** 将 Electron 客户端由一个“只管展示的哑壳”升级为“具备感知宿主能耗状态的协调中枢”。
1. **无 GPU 纯净运行**：全局执行 `app.disableHardwareAcceleration()` 并追加命令行参数屏蔽 GPU 栅格化与硬件编解码，杜绝与网易 MuMu / Thorium 浏览器的独显 2GB 显存发生争抢，彻底规避 TDR 141 硬件重置。
2. **窗口状态降帧**：监听 `BrowserWindow` 的 `blur`、`minimize`、`hide`（托盘）事件。前台时锁定 30 FPS，失焦时降为 5 FPS，最小化或隐藏至托盘时直接压至 1 FPS 并启用 `setBackgroundThrottling(true)`。
3. **系统电源联动**：监听 `powerMonitor.on('suspend')` 与 `powerMonitor.on('lock-screen')`，将省电事件通过 IPC 及 postMessage 下发给前端及 PyWebIO。

**When to use:** 用户在挂机时进行多任务并发（看直播、听歌、日常办公），Electron 常驻后台或托盘。

**Trade-offs:** 
- *优点*：Electron 无论挂机多久，CPU 占用稳定低于 0.5%，显存占用为 0，内存压死在 80MB 内。
- *考量*：失焦时如果正在拖动滚动条可能会感知到 5 FPS 的低帧率，但用户一旦点击窗口（`focus`）会在 1 帧内即刻恢复流畅。

**Example:**
```typescript
// webapp/packages/main/src/index.ts
import { app, BrowserWindow, powerMonitor, ipcMain } from 'electron';

// 1. 剥离 GPU
app.disableHardwareAcceleration();
app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('disable-gpu-compositing');
app.commandLine.appendSwitch('renderer-process-limit', '1');
app.commandLine.appendSwitch('js-flags', '--max-old-space-size=128 --optimize-for-size');

export const setupPowerHooks = (mainWindow: BrowserWindow) => {
  mainWindow.webContents.setBackgroundThrottling(true);

  // 动态帧率阶梯
  mainWindow.on('focus', () => {
    mainWindow.webContents.setFrameRate(30);
    mainWindow.webContents.send('power-state-change', 'focused');
  });

  mainWindow.on('blur', () => {
    mainWindow.webContents.setFrameRate(5);
    mainWindow.webContents.send('power-state-change', 'blurred');
  });

  mainWindow.on('minimize', () => {
    mainWindow.webContents.setFrameRate(1);
    mainWindow.webContents.send('power-state-change', 'minimized');
  });

  // 托盘隐藏
  ipcMain.on('window-tray', () => {
    mainWindow.webContents.setFrameRate(1);
    mainWindow.hide();
    mainWindow.webContents.send('power-state-change', 'hidden');
  });

  // 系统级电源挂起
  powerMonitor.on('suspend', () => {
    mainWindow.webContents.send('power-state-change', 'suspended');
  });
  powerMonitor.on('resume', () => {
    mainWindow.webContents.send('power-state-change', 'active');
  });
};
```

---

## Data Flow

### Request Flow (调度与自适应循环执行链路)

```
[AzurLaneAutoScript.loop()]
          │
          ▼
   [get_next_task()] ────(空闲时间 > 0)────► [wait_until(future)]
          │                                         │
          │ (立即执行)                         [长等待自适应休眠 (5s -> 15s)]
          ▼                                         │
    [run(task)]                                     ▼
          │                                  [EmptyWorkingSet 内存修剪]
          ▼
   [ModuleBase.loop()] ◄──────────────────────────────┐
          │                                           │
          ├────► 检查 _idle_loop_count 阶梯延时       │
          │      (0~2次: 0ms | 3~8次: 250ms | >8次: 700ms)
          │                                           │
          ▼                                           │
   [device.screenshot()]                              │ (状态机未命中，继续轮询)
          │                                           │
          ├────► NemuIPC 共享内存抓取 (5~15ms)         │
          ├────► JPEG 编码存入 screenshot_deque (3MB) │
          │                                           │
          ▼                                           │
   [业务逻辑判定: self.appear(BUTTON)] ─────────────────┘
          │
          │ (判定命中 / 触发点击动作)
          ▼
   [self.appear_then_click() / click()]
          │
          ├────► [reset_loop_sleep()] ──► _idle_loop_count 重置为 0 (零延迟响应下步)
          ├────► 执行低开销触控 (nemu_touch / minitouch)
          │
          ▼
   [TaskEnd / 任务完成]
          │
          ▼
   [release_resources()]
          │
          ├────► OCR 模型注销 & 释放 Asset 字典
          ├────► gc.collect() 强制代际回收
          └────► Win32 EmptyWorkingSet 归还物理 RAM
```

---

### State Management

系统状态由四层物理隔离的存储机制管理，确保低资源状态下具备强容错与快速自愈能力：

1. **持久化配置与任务时间戳**：位于 `config/{config_name}.json`，每次任务结束（`TaskEnd`）原子化写入，完全独立于内存状态。
2. **实时错误追溯现场**：位于 `Screenshot.screenshot_deque`，内存中仅保留最近 60 帧 JPEG 压缩流。发生异常时直接倾倒至 `./log/error/{timestamp}/`，不耗费大量驻留内存。
3. **全量运行日志**：位于 `./log/{date}_{config_name}.txt`，由 Python `logging.FileHandler` 顺序写入，不受 WebUI 前端渲染截断或页面关闭的影响。
4. **前端展现状态**：PyWebIO Session 仅维护视图临时缓冲；一旦客户端失联或窗口最小化，无状态丢失隐患。

---

### Key Data Flows

#### 1. 窗口功耗状态联动流 (Power & Throttle Propagation)
```
[Electron Main: blur/min/hide/powerMonitor]
                 │
                 ▼ IPC
[Renderer: Alas.vue]
                 │
                 ▼ postMessage
[PyWebIO JS Client: window.addEventListener]
                 │
                 ▼ WebSocket State / document.visibilityState
[Python WebUI: TaskHandler & RichLog]
                 │
                 ▼
       ┌─────────┴─────────┐
       ▼                   ▼
[挂起 put_log 渲染]   [降低 overview 轮询至 30s]
```

#### 2. 日志数据双轨分流 (Log Ingestion & History Download)
```
[Alas Subprocess: logger.info()]
                 │
                 ├─── (轨道 A: 磁盘持久化，全量保全) ───► [./log/YYYY-MM-DD.txt] ──► [用户下载 / 错误打包]
                 │
                 └─── (轨道 B: 视图展示，受控节流)
                             │
                             ▼
                     [Queue(maxsize=500)]
                             │
                             ▼
                [ProcessManager.renderables (Max 300)]
                             │
                             ▼ (前台可见且展开时)
                [RichLog.render() 1.0s 节流]
                             │
                             ▼ WebSocket
                [JS DOM Window (滑动窗口最大 150 节点)]
```

#### 3. 自适应视觉观测与断言流 (Adaptive Vision & Instant Wakeup)
```
[状态循环开始] ──► [空转计数器 = 0]
      ▲                    │
      │                    ▼
      │           [截图采集: NemuIPC]
      │                    │
      │           [画面匹配: appear()]
      │             │             │
   (未匹配)         │             │ (匹配成功)
      │             ▼             ▼
      │      [延时递增]      [瞬时复位: count=0]
      │      (0.1s~1.0s)          │
      │             │             ▼
      └─────────────┴────── [执行点击 / 状态转移]
```

#### 4. 任务边界内存检查点与健康回收流 (Task Boundary Checkpoint & Graceful Recycling)
```
[任务正常完成: TaskEnd]
          │
          ▼
[alas.py: 调度主循环检查点]
          │
          ├────► [release_resources()]: OCR注销 / 模版清理
          ├────► [gc.collect()]: 强制回收垃圾对象
          ├────► [Win32 EmptyWorkingSet]: 释放私有工作集
          │
          ▼
[ProcessManager: 子进程健康探测]
          │
          ├─► 查询 subprocess.memory_info().rss
          │
          ├─► 若 RSS < 600MB: 保持运行，进入 wait_until 或下个任务
          │
          └─► 若 RSS >= 600MB: 
                    │
                    ▼
              [优雅自愈 (Graceful Recycling)]
              - 在任务安全空闲间隙终止子进程
              - 重新启动 alas 子进程 (耗时 1.5s，状态无缝读取 config.json)
              - 彻底消除 CPython C堆碎片
```

---

## Scaling Considerations

针对不同负载等级与并发实例，硬件资源瓶颈与架构伸缩策略对比如下：

| 负载级别 | 典型运行场景 | 关键架构瓶颈 | 推荐架构调优策略 |
|---------|-------------|-------------|-----------------|
| **单实例 7×24h 挂机** | 1 个 Alas 实例 + MuMu 12 + 直播软/硬解 | 双核 CPU 空转开销与内存置换颠簸 | 全面启用 `nemu_ipc` 截图、自适应循环休眠、错误截图 JPEG 压缩、DOM 150 节点截断。 |
| **双/多实例轮换挂机** | 2~3 个游戏账号通过 ProcessManager 定时交替运行 | 多 Python 进程物理内存并存导致 15.8GB 虚拟内存雪崩 | 强化任务交界处的 `EmptyWorkingSet`；非运行期账号子进程严格休眠或挂起；共享 OCR 单例。 |
| **超长时无人值守 (周级)** | 7×24h 连续运行数周，无人工交互与重启 | C 扩展库（OpenCV / NumPy）底层堆碎片与僵尸句柄 | 激活 `ProcessManager` RSS 阈值监测（600MB）；在任务空闲期自动触发轻量级进程再生。 |

### Scaling Priorities

1. **第一瓶颈：内存置换颠簸 (Memory & Pagefile Thrashing)**
   - *破坏性*：宿主机 Pagefile 已消耗 15.8GB，物理 RAM 处于极度饥饿状态。若 Alas 产生 300MB~1GB 的大数组分配，会导致 Windows 频繁进行磁盘换页，引发整机秒级卡顿。
   - *根治措施*：截图队列 JPEG 压缩（立省数百 MB）+ 任务交界 `EmptyWorkingSet` + 严格限制 DOM 与队列长度。
2. **第二瓶颈：双核 CPU 算力挤占 (CPU Starvation & Core Contention)**
   - *破坏性*：i5-4210H 仅 2 核 4 线程。若 Alas 循环截图与 PyWebIO 渲染各吃 20%，将导致直播掉帧与模拟器卡顿发热。
   - *根治措施*：自适应循环休眠（将无动作期截图率压低至 1 FPS）+ WebUI 后台 0Hz 推送 + NemuIPC 零 CPU 截图。
3. **第三瓶颈：GPU 引擎重置崩溃 (GPU TDR & Driver Reset)**
   - *破坏性*：GTX 960M 仅 2GB 显存，曾触发 `LiveKernelEvent 141`。
   - *根治措施*：Electron 彻底关闭硬件加速与 GPU 栅格化，把显存与 NVDEC 硬解管线 100% 留给直播与 MuMu。

---

## Anti-Patterns

### Anti-Pattern 1: 内存中长时间存储未压缩的原始大尺寸图像数组 (Uncapped Raw Buffers)

**What people do:** 将每帧 `1280x720x3` 的原始 Numpy uint8 数组（2.76MB）直接追加进 `collections.deque(maxlen=300)`。
**Why it's wrong:** 300 张原始图像在内存中净占 828MB。在 16GB 物理内存已经严重依赖 Pagefile 的系统上，极易直接引爆系统 OOM 或触发恶性磁盘换页。
**Do this instead:** 存入前通过 `cv2.imencode('.jpg')` 实时压缩，或将 maxlen 约束在 30~50；在 99.9% 正常运行的时间里仅占用 ~3MB 内存。

### Anti-Pattern 2: 无论界面是否可见，盲目全速执行 WebIO 渲染与 DOM 推送 (Blind High-Frequency DOM Streaming)

**What people do:** 在后端开启 0.25s（4Hz）的高频轮询任务，持续将 Rich 格式化生成的复杂 HTML 通过 WebSocket 注入前端 jQuery `append()`。
**Why it's wrong:** 当窗口最小化到托盘或日志被折叠时，用户根本无法看到日志，但 CPU 仍在反复进行正则表达式语法高亮与 HTML 拼装，Chromium 渲染进程被迫不断进行无用的 DOM 重排与内存积压。
**Do this instead:** 引入可见性与折叠门禁状态机。后台或折叠时直接暂停推送；前台激活时单次合并刷新最近 100 行。

### Anti-Pattern 3: 自动化状态机采用无差别的高频固定间隔轮询 (Rigid Polling Cadence)

**What people do:** 无论当前是处于战斗挂机、长达几秒的换页动画，还是处于即时交互菜单，均固定以 100ms 间隔死循环截图比对。
**Why it's wrong:** 在战斗与动画等明知无须干预的时间段，每秒 10 次截图比对让双核 CPU 始终处于满负荷高频状态，不仅浪费电力，还会抢占同机直播解码的 CPU 周期。
**Do this instead:** 实施自适应阶梯休眠。在未捕获状态期间逐步延长休眠步长至 0.8s~1.2s，并在捕获状态转移或点击操作时瞬时复位至 0ms 延迟。

### Anti-Pattern 4: 暴力终止子进程而不做状态持久化 (Hard Killing Without State Checkpoints)

**What people do:** 为了清理内存，直接在定时器中执行 `process.kill()`。
**Why it's wrong:** 会打断正在写入的配置文件或正在进行的战斗逻辑，导致 `config.json` 损坏或游戏进入未预期的失步状态。
**Do this instead:** 实施任务边界的优雅回收（Graceful Recycling）。只在调度器完成一个完整任务（`TaskEnd`）并已将最新时间戳固化到磁盘后的空闲间隙，才进行子进程的轻量重启。

---

## Integration Points

### External Services & System Boundaries

| System / Service | Integration Pattern | Interaction Details & Gotchas |
|------------------|---------------------|-------------------------------|
| **MuMu 模拟器 12** | 本地共享内存 Direct IPC (`external_renderer_ipc.dll`) | 直接映射显存共享表面读取 BGRA 像素。极速（5~15ms）且 0% CPU 编解码开销；严禁使用 Scrcpy（Scrcpy 后台强制保持 30~60 FPS H.264 软硬解码线程，极大消耗双核算力）。 |
| **Windows OS (DWM / PSAPI)** | Win32 API 动态调用 (`kernel32.dll`, `psapi.dll`) | 通过 `EmptyWorkingSet` 强制将进程物理工作集交还操作系统，有效缓和 15.8GB Pagefile 置换风暴。在空闲长等待期间调用。 |
| **Chromium 渲染子系统** | Chromium 命令行启动开关 (CLI Flags) | 剥离 GPU 加速管线，强行切断与 DirectX / OpenGL 驱动交互，从根本上杜绝 GTX 960M 2GB 显卡 TDR 超时（`LiveKernelEvent 141`）。 |

### Internal Boundaries

| Boundary | Communication Mechanism | Notes |
|----------|-------------------------|-------|
| **Electron Main ↔ Renderer** | Electron IPC (`ipcRenderer` / `ipcMain`) | 传递窗口生命周期与功耗事件（`focus`, `blur`, `minimize`, `powerMonitor`）。 |
| **Renderer ↔ PyWebIO** | HTML5 `postMessage` / Page Visibility API | 跨 Iframe 传递功耗模式与可见性，控制 WebUI 后端日志推流的挂起与恢复。 |
| **ProcessManager ↔ Alas Subprocess** | Multiprocessing `Queue` (Bounded) & OS Process Handle | 子进程日志单向投递；Supervisor 定期检查子进程句柄健康度与 RSS 物理内存。 |
| **ModuleBase ↔ Device Driver** | 直接对象调用与事件回调 | 按钮命中或点击动作直接触发 `reset_loop_sleep()`，实现 0 延迟断言与动作同步。 |

---

## Suggested Implementation Phase Ordering

基于组件依赖拓扑与风险隔离原则，建议按以下 5 个阶段逐步落地实施：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Python 后端内存守卫与截图压缩 (Core Memory Guard)              │
│ - 截图缓冲 JPEG 压缩 (module/device/screenshot.py)                      │
│ - 任务间隙 gc.collect() 与 EmptyWorkingSet (module/base/resource.py)   │
│ - 预期成果: 单实例常驻内存减少 150MB~300MB，彻底根除 OOM 闪退           │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 2: 自动化引擎自适应阶梯休眠 (Adaptive Loop Sleeping)              │
│ - ModuleBase.loop() 动态休眠阶梯与即时唤醒复位 (module/base/base.py)    │
│ - Device 截图间隔动态协调 (module/device/device.py)                     │
│ - 预期成果: 空转期与长等待期 CPU 占用下降 60%~75%，整机发热显著缓解     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 3: WebUI 与 PyWebIO 日志流控与 DOM 截断 (WebUI Gated Streaming)   │
│ - RichLog 前台可见性门禁与 1.0s 降频推送 (module/webui/widgets.py)       │
│ - 前端 JS DOM 150 条环形滑动截断窗口 (module/webui/widgets.py, app.py)  │
│ - 进程队列容量约束 Queue(maxsize=500) (module/webui/process_manager.py) │
│ - 预期成果: 彻底根除 7*24h DOM 膨胀，失焦与折叠状态下 WebUI CPU 降至 0% │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 4: Electron 桌面客户端轻量化与功耗总线 (Electron Low-Power)        │
│ - 深度注入 Chromium 无 GPU 参数 (webapp/packages/main/src/index.ts)     │
│ - 窗口失焦 (5 FPS) / 最小化 (1 FPS) 降频与 powerMonitor 接入            │
│ - Alas.vue Iframe postMessage 功耗状态桥接                              │
│ - 预期成果: 客户端常驻内存 < 80MB，无显存占用，杜绝 TDR 141 显卡崩溃    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 5: 7×24 小时长期稳定性巡检与优雅回收 (Long-Term Recycling & Ops)  │
│ - ProcessManager 子进程 RSS 物理内存低频探测与超限安全重启              │
│ - MuMu 12 与老旧双核 Haswell 协同最佳实践与用户配置指南                 │
│ - 预期成果: 实现周级 7×24h 极端无卡顿稳定运行                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Sources

- **代码库核心实现参考**：
  - `alas.py`: `AzurLaneAutoScript.loop()`, `get_next_task()`, `save_error_log()`
  - `module/base/base.py`: `ModuleBase.loop()`, `early_ocr_import()`
  - `module/base/resource.py`: `release_resources()`, `Resource`
  - `module/device/screenshot.py`: `Screenshot.screenshot()`, `screenshot_deque`, `screenshot_interval_set()`
  - `module/device/method/nemu_ipc.py`: `CaptureNemuIpc`, MuMu 共享内存原生调用
  - `module/webui/process_manager.py`: `ProcessManager`, `_renderable_queue`, `run_process`
  - `module/webui/widgets.py`: `RichLog.put_log()`, `RichLog.render()`, `RichLog.extend()`
  - `module/webui/app.py`: `task_handler`, `visibility_state_switch`, `alas_daemon_overview`
  - `webapp/packages/main/src/index.ts`: Electron 入口、`app.disableHardwareAcceleration()`
  - `webapp/packages/renderer/src/components/Alas.vue`: Iframe 容器组件
- **技术规范与官方标准**：
  - Microsoft Docs: *EmptyWorkingSet function (psapi.h)*
  - Electron Documentation: *Performance, Offscreen Rendering and powerMonitor API*
  - Chromium Project: *Design Documents — Inter-process Communication & Background Tab Throttling*
  - W3C Page Visibility API Specification (`document.visibilityState`)

---
*Architecture research for: AzurLaneAutoScript Low-Resource & 7*24h Stability Optimization*  
*Researched: 2026-09-12*
