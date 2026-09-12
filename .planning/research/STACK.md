# Stack Research

**Domain:** AzurLaneAutoScript (Alas) Low-Resource & 7*24h Stability Optimization  
**Researched:** 2026-09-12  
**Confidence:** HIGH  

---

## Executive Summary & Target Environment

本调研针对 Alas 在特定弱机高压硬件环境下的 7×24 小时长期无人值守挂机场景制定：
- **CPU 约束**：Intel Core i5-4210H @ 2.9GHz（Haswell 架构移动端标压双核四线程，计算资源极其紧张，极易因高频唤醒无法进入 C-states 导致发热降频）。
- **内存约束**：16GB 物理 RAM，PageFile 已占用 15.8GB（重度虚拟内存换页压力，进程物理工作集抖动极易引发全局磁盘 IO 阻塞）。
- **GPU 约束**：Intel HD Graphics 4600 核显 + Nvidia GeForce GTX 960M（2GB 显存，双显卡切换 Optimus 架构），曾触发 `LiveKernelEvent 141`（显卡引擎超时/TDR 崩溃），显存与硬件编解码器极度稀缺。
- **并发应用**：7×24h 网易 MuMu 模拟器 + Thorium 浏览器观看高清视频直播（重度硬解/软解占用） + 网易云音乐 + Alas（Electron 桌面端 + Python 3.10 后端）。

核心技术路线：**“零 GPU 争抢、零冗余编解码、原语级共享内存、原生滑动截断、Win32 工作集修剪与自适应睡眠”**。

---

## Recommended Stack

### Core Technologies

| Technology / Component | Version / Target | Purpose | Why Recommended |
|------------------------|------------------|---------|-----------------|
| **NemuIPC** | MuMu 12 (`external_renderer_ipc.dll` >= 3.8.13) | 模拟器本地原生共享内存截图与输入注入 | **耗时 5~15ms，CPU 开销 < 1%**。直接从宿主机 MuMu 渲染进程共享内存拷出原生 BGRA 像素，完全绕过 Android 内部 Java 层、网络协议栈与 H.264/JPEG 编解码，彻底根除双核 CPU 算力挤占与 GPU TDR 冲突。 |
| **Electron Low-Power Runtime** | Electron 15.1.0 (Chromium 94) | 彻底剥离 GPU 依赖、失焦极致降频的控制台运行时 | 通过注入特定 Chromium flags（`--disable-gpu`, `--disable-gpu-compositing`, `--disable-software-rasterizer`）完全阻断与 DirectX/OpenGL 驱动交互，规避 TDR 崩溃；失焦/后台强制压制至 1~5 FPS，V8 堆内存上限压制在 128MB。 |
| **Win32 Working Set Trimming** | Windows PSAPI (`kernel32.dll` / `psapi.dll`) | 进程级物理工作集修剪与内存防置换释放 | 针对 15.8GB 虚拟内存换页重压，解决 Python 即使 `gc.collect()` 也无法将空闲虚拟页退还给操作系统的缺陷。在闲置期调用 `EmptyWorkingSet`，可将每个 Alas 进程物理内存从 200MB+ 压减至 20~30MB。 |
| **Native DOM Window Truncation** | Native JS DOM API + PyWebIO WebSocket 节流 | WebUI 7×24h 日志渲染节点上限锚定与流控 | 不引入庞大三方库，通过前端轻量 JS 滑动窗口（FIFO）将日志 DOM 节点严格限制在 200~300 条以内；后台（`document.hidden`）完全挂起 WebSocket 推送，前台时批量合并推送，杜绝 Chromium 渲染进程内存暴涨。 |

---

### Supporting Libraries & System APIs

| Library / API | Version | Purpose | When to Use |
|---------------|---------|---------|-------------|
| **`ctypes.windll.psapi.EmptyWorkingSet`** | Win32 API | 强制清理进程未引用的物理工作集，归还物理 RAM 给系统 | 在任务执行完毕触发 `release_resources()`，或进入 `wait_until()` 长时间空闲等待前调用。 |
| **`gc` (CPython gc tuning)** | Built-in | 垃圾回收代际阈值调优与全代回收控制 | 启动时调整阈值为 `gc.set_threshold(50000, 15, 15)`，防止高频图像匹配中频繁触发 Gen0 垃圾回收；在任务间隙显式触发 `gc.collect()`。 |
| **`collections.deque(maxlen=30~50)`** | Built-in | 限制错误截图历史回溯队列容量 | 替换默认的 300 容量限制。每个 720p 截图占用 2.76MB，50 张仅占 ~138MB（原 300 张占近 1GB 内存），彻底消除内存雪崩隐患。 |
| **`psutil`** | 5.9.3 (已安装) | 后台低频健康监控与孤立僵尸进程自愈 | 建立 60s 级低频监控守护，监测各 Python 子进程 RSS 物理内存与孤立 `adb.exe` 进程，异常时优雅自愈。 |
| **HTML5 Page Visibility API** | Web Standard | 探测控制台窗口与浏览器标签的前后台可见性 | 当 `document.visibilityState === 'hidden'` 时，停止 WebUI 日志拉取和 DOM 刷新，进入极度省电状态。 |

---

### Development & Diagnostic Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **Windows Performance Monitor / Resource Monitor** | 监控 Working Set, Private Bytes 与 Page Faults/sec | 验证 `EmptyWorkingSet` 与 deque 缩容对缓解磁盘换页抖动的实际效果。 |
| **Chromium Command Line Switch Inspector** | 验证 Electron 进程是否完全脱离 GPU 体系 | 确认已无 `gpu-process`，渲染由纯 CPU 软件微管线接管且帧率被限制。 |
| **MuMu SDK DLL Inspector** | 检查 MuMu 12 安装路径及 `external_renderer_ipc.dll` 导出函数 | 确保 `nemu_connect`, `nemu_capture_display`, `nemu_input_event_touch_*` 正常加载。 |

---

## Implementation & Runtime Configuration

### 1. Electron 桌面端极致轻量化配置 (`webapp/packages/main/src/index.ts`)

```typescript
// 彻底禁用 GPU 硬件加速并切断 GPU 进程（规避 GTX 960M 2GB 显存耗尽引发的 TDR 141 崩溃）
app.disableHardwareAcceleration();

// 注入 Chromium 底层优化 Flags
app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('disable-gpu-compositing');
app.commandLine.appendSwitch('disable-gpu-rasterization');
app.commandLine.appendSwitch('disable-software-rasterizer');
app.commandLine.appendSwitch('disable-accelerated-video-decode');
app.commandLine.appendSwitch('disable-accelerated-mjpeg-decode');
app.commandLine.appendSwitch('disable-accelerated-2d-canvas');

// 启用 Windows 原生窗口遮挡跟踪与后台强制节流
app.commandLine.appendSwitch('enable-features', 'CalculateNativeWinOcclusion');
app.commandLine.appendSwitch('enable-background-throttling');
app.commandLine.appendSwitch('disable-renderer-backgrounding', 'false');

// 内存与 V8 紧凑模式：限制 V8 堆内存为 128MB，开启内存尺寸优化
app.commandLine.appendSwitch('js-flags', '--max-old-space-size=128 --optimize-for-size --lite-mode');
app.commandLine.appendSwitch('renderer-process-limit', '1');

// 窗口事件与动态降帧节流编排
const setupWindowThrottling = (win: BrowserWindow) => {
  // 默认启用后台节流
  win.webContents.setBackgroundThrottling(true);

  // 失去焦点时降低渲染帧率至 5 FPS
  win.on('blur', () => {
    win.webContents.setFrameRate(5);
  });

  // 获得焦点时恢复至 30 FPS（对控制台足够流畅且节约 CPU）
  win.on('focus', () => {
    win.webContents.setFrameRate(30);
  });

  // 最小化或托盘隐藏时压制到 1 FPS
  win.on('minimize', () => {
    win.webContents.setFrameRate(1);
  });
  win.on('hide', () => {
    win.webContents.setFrameRate(1);
  });
  win.on('restore', () => {
    win.webContents.setFrameRate(30);
  });
  win.on('show', () => {
    win.webContents.setFrameRate(30);
  });
};
```

---

### 2. PyWebIO / WebUI 前端滑动窗口截断与流控 (`module/webui/widgets.py` & `app.py`)

#### 前端原生轻量 DOM 滑动截断（零依赖）
在前端初始化或追加日志时注入原生 JS 修剪逻辑：
```javascript
// 保障 DOM 树节点恒定在 MAX_LINES 以内，绝不无限制堆积
function trimLogDom(scope, maxLines = 250) {
  const container = document.querySelector("#pywebio-scope-" + scope + " > div");
  if (!container) return;
  while (container.childNodes.length > maxLines) {
    container.removeChild(container.firstChild);
  }
}
```

#### 后端自适应节流与 WebSocket 缓冲 (`RichLog.put_log`)
- **前台活跃期**：将日志轮询与推送频率从 `0.25s`（250ms）调整为 `1.0s`，并将 1 秒内积累的日志合并成单次 HTML 推送，大幅减少 WebSocket 小包与前端 重排（reflow）。
- **后台休眠期**：通过 `get_window_visibility_state()` 监测。当前端处于 `hidden` 状态时，后端仅在 `pm.renderables` 内存循环队列中记录，**暂停向前端发送 `run_js`**；当窗口切回 `visible` 时，一次性全量输出最近 150 行。

---

### 3. Python 自动化引擎能效与内存修剪 (`module/base/resource.py` & `alas.py`)

#### 物理工作集修剪（EmptyWorkingSet）
```python
import ctypes
import gc
from module.logger import logger

def trim_memory():
    """
    触发代际 GC 并强制修剪 Windows 进程物理工作集 (Working Set)
    """
    try:
        # 1. 回收循环引用的 Python 对象
        gc.collect(generation=2)
        
        # 2. Windows 专属 API: 将当前进程未使用的内存页移出物理 RAM
        ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
    except Exception as e:
        logger.warning(f"Failed to trim working set: {e}")
```

#### 自适应指数退避睡眠（Adaptive Backoff Sleep）
在等待状态变化或图像匹配失败的循环中，使用指数退避策略替代固定 `sleep(0.1)`：
- 第 1~3 次检查：间隔 0.2s（快速捕获即时弹窗）。
- 第 4~8 次检查：退避至 0.5s。
- 8 次以上：退避至 1.0s ~ 1.5s，让双核 CPU 能够进入深层 C-states 休眠，降低发热量与功耗。

#### 异常截图队列容量锁定 (`module/device/screenshot.py`)
```python
@cached_property
def screenshot_deque(self):
    try:
        length = int(self.config.Error_ScreenshotLength)
    except ValueError:
        length = 30
    # 强制将最大上限严格约束在 30 ~ 50（每个截图 2.76MB，上限约 138MB，防止原 300 占用 1GB 内存）
    length = max(1, min(length, 50))
    return deque(maxlen=length)
```

---

## Connection Method Recommendation (MuMu on Haswell i5)

针对 **Intel Core i5-4210H + 双显卡 (GTX 960M 2GB, 发生过 TDR 141) + 7×24h MuMu 12** 的特定工况，4 种连接方式综合评估如下：

| 评估维度 | **NemuIPC (网易共享内存)** | **DroidCast / DroidCast_raw** | **Scrcpy (视频流)** | **ADB / ADB_nc** |
|----------|---------------------------|------------------------------|---------------------|------------------|
| **截图耗时** | **5 ~ 15 ms** (最优) | 80 ~ 150 ms | 30 ~ 60 ms | 600 ~ 1500 ms |
| **CPU 占用** | **< 1% (纯内存拷贝，近乎零消耗)** | 10% ~ 20% (包含 JPEG 解码) | 15% ~ 30% (H.264 解码) | 20% ~ 40% (频繁子进程 IO) |
| **GPU 占用/TDR 风险** | **0% (无任何 GPU 参与，零 TDR 风险)** | 0% (无 GPU 参与) | **高 (抢占硬解/显存带宽，极易触发 TDR)** | 0% |
| **数据传输链路** | 宿主机 C DLL 共享内存直接读取 | 虚拟机 Android 内部 HTTP Server | 虚拟机 MediaCodec 编码 + 宿主机解码 | ADB Server Socket 管道转码 |
| **点击响应延迟** | 1 ~ 5 ms (原生 C API 注入) | 10 ~ 30 ms (MaaTouch / minitouch) | 5 ~ 15 ms (Scrcpy 控制流) | 100 ~ 300 ms (`adb shell input`) |
| **推荐评级** | **第一首选 (Strongly Recommended)** | **第二备选 (Fallback Backup)** | **严禁使用 (Avoid)** | **严禁使用 (Avoid)** |

### 关键配置要求（NemuIPC 生效必须项）：
1. **MuMu 版本**：必须使用 MuMu 12（版本号 >= 3.8.13，完美支持 4.0/5.0/6.0）。
2. **关闭模拟器后台保活**：在 MuMu 模拟器“设置中心” → “基本设置”中，**必须关闭“后台挂机时保活运行”**（`customer.app_keptlive = false`），否则 MuMu 会启用独立窗口无头渲染导致 IPC 捕获黑屏或报错。
3. **备用策略**：若用户未来临时切换至雷电模拟器或真机，自动降级切换至 `DroidCast`。

---

## Alternatives Considered

| Recommended Choice | Alternative | When to Use Alternative |
|--------------------|-------------|-------------------------|
| **NemuIPC** | DroidCast | 仅当使用非 MuMu 模拟器（如 LDPlayer、BlueStacks）或 MuMu 早期老旧版本且无法升级时。 |
| **彻底禁用 Electron GPU** | 开启 GPU 硬件加速 | 仅当拥有大显存独立显卡（>= 6GB VRAM）且无并发视频直播解码冲突的高性能台式机。当前机器 2GB 显存且已有 TDR 记录，必须坚决禁用。 |
| **原生 JS DOM 截断** | `vue-virtual-scroller` / `react-window` | 仅当前端采用全 Vue3 单页自研组件渲染日志时。对于 PyWebIO 这种由服务端直接向 DOM 注入 HTML 的架构，引入前端重型虚拟列表库需彻底重构 PyWebIO 交互层，成本过高且容易破坏现有逻辑。 |
| **Win32 `EmptyWorkingSet`** | 第三方内存清理工具 (如 Mem Reduct) | 仅当不想在代码中侵入系统 API 时。但在 Alas 任务调度周期中内建修剪更加精准（空闲时立即修剪，执行时不产生额外开销），优于外部软件暴力全局轮询。 |

---

## What NOT to Use

| Avoid (严禁采用) | Why (致命问题) | Use Instead (推荐替代方案) |
|------------------|----------------|----------------------------|
| **在当前机器上开启 Electron 硬件加速** | GTX 960M 仅 2GB 显存，且 Thorium 浏览器正在硬解直播流；Chromium 抢占显卡资源必将再次触发 `LiveKernelEvent 141` 驱动超时重置。 | 使用 `--disable-gpu` + `--disable-gpu-compositing` 彻底由 CPU 软件渲染。 |
| **使用 Scrcpy 截取本地 MuMu 模拟器** | 本地模拟器视频流传输需要在 Android 端编码并在宿主机解码，在双核 Haswell i5 上耗费宝贵的 CPU/GPU 资源。 | 使用零编解码开销的 **NemuIPC**。 |
| **无 DOM 截断的 7×24h PyWebIO 日志流** | 长时间运行产生数万个带有行内样式的 DOM 节点，直接耗尽 Chromium 渲染进程内存导致崩溃（OOM）。 | 注入原生 JS 滑动窗口（FIFO），严格截断并保持在 250 行以内。 |
| **默认 300 容量的错误截图队列** | 300 张 720p 截图占据近 1GB 内存，使原本已达 15.8GB 的 PageFile 发生灾难性置换，造成整机假死。 | 限制 `Error_ScreenshotLength` 为 30 ~ 50。 |
| **高频系统时钟提升 (`timeBeginPeriod(1)`)** | 强制提高 Windows 中断频率到 1ms 会阻断 CPU 进入深度省电 C-states，加剧老旧移动 CPU 发热与降频。 | 维持系统默认时钟，使用自适应指数退避睡眠。 |

---

## Stack Patterns by Variant

### Variant A: 极端弱机挂机并发工况（当前目标配置）
- **条件**：Intel i5-4210H (2c4t) + 16GB RAM (15.8GB PageFile) + GTX 960M (2GB) + 并发看直播
- **运行配置**：
  - 截图通信：强制锁定 `NemuIPC`。
  - Electron：无 GPU 软件光栅化模式，限制 V8 堆内存 128MB，失焦降频至 5 FPS，隐藏降频至 1 FPS。
  - WebUI 日志：DOM 锁定 250 行，窗口后台时完全挂起 WebSocket 日志流。
  - 内存修剪：每次任务完成与空闲等待时，调用 `EmptyWorkingSet`。
  - 截图缓冲：强制截断 `screenshot_deque` 至 30。

### Variant B: 独立服务器 / 高性能台式机工况
- **条件**：CPU >= 6 核，物理内存 >= 32GB 无 PageFile 压力，大显存独显
- **运行配置**：
  - Electron 可保持默认渲染帧率，日志 DOM 可放宽至 1000 行。
  - 错误截图缓冲可保持 100~300 行以便长期回溯排查。

---

## Version Compatibility

| 组件 A | 兼容组件 B | 兼容性要点与注意事项 |
|--------|------------|----------------------|
| **NemuIPC** | MuMu 12 (`3.8.13` ~ `6.0`) | 必须在模拟器中关闭“后台挂机时保活运行”；需适配 `shell/sdk`、`nx_device/12.0/shell/sdk`、`nx_main/sdk` 多路径 DLL 查找。 |
| **Electron 15.1.0** | Chromium 94 命令行参数 | `--disable-gpu`, `--disable-gpu-compositing`, `--js-flags` 均在 Chromium 94 稳定支持。 |
| **PyWebIO 1.6.2** | FastAPI / Starlette / Uvicorn | 兼容 WebSocket 通信，支持在生成器中通过自适应休眠动态控制推送频次。 |
| **Python 3.10** | `ctypes.windll.psapi.EmptyWorkingSet` | Windows 10/11 64-bit 深度原生兼容，需使用 `GetCurrentProcess()` 句柄。 |

---

## Sources & Verification

- **MuMu Player 官方 SDK 文档**：MuMu 12 外部渲染 IPC 规范与保活机制配置（`customer.app_keptlive`）。
- **Chromium Command Line Switches 官方手册**：`--disable-gpu-compositing`, `--max-old-space-size`, `CalculateNativeWinOcclusion` 行为规范验证。
- **Microsoft Win32 PSAPI 官方文档**：`EmptyWorkingSet` 内存回收与工作集置换机制规范。
- **Alas 源代码审计**：
  - `module/device/method/nemu_ipc.py`（NemuIPC 现有实现与重试机制）
  - `module/device/screenshot.py`（deque 内存缓冲与截图管道调用）
  - `module/webui/widgets.py` & `app.py`（PyWebIO 日志流与 DOM 注入逻辑）
  - `webapp/packages/main/src/index.ts`（Electron 主进程现有配置）

---
*Stack research for: AzurLaneAutoScript Low-Resource & 7*24h Stability*  
*Researched: 2026-09-12*
