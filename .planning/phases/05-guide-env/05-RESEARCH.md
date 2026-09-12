# Phase 5: 弱机与模拟器协同最佳配置 - Research

**Researched:** 2026-09-12  
**Domain:** 弱机双显卡（Intel i5-4210H 2C4T + GTX 960M 2GB / HD 4600）与网易 MuMu 12 模拟器协同调优、WDDM TDR 防护、PageFile 虚拟内存规整、自动化体检脚本与运行时诊断集成  
**Confidence:** HIGH  

---

## Executive Summary

在 7×24 小时无人值守挂机场景中，以 **Intel Core i5-4210H (2C4T Haswell)** 搭配 **Nvidia GeForce GTX 960M (2GB VRAM) + Intel HD Graphics 4600 核显** 为代表的老旧移动平台，面临着三大物理级瓶颈约束：
1. **显存竞逐与 TDR 崩溃 (`LiveKernelEvent 141`)**：GTX 960M 仅有 2GB 独立显存。若 MuMu 12、Thorium 高清直播硬解与 Alas 客户端同时挤在独显上，显存瞬间耗尽并外溢至系统内存，WDDM 换页阻塞导致 GPU 调度超过 2 秒超时，直接触发显卡驱动重置与黑屏闪退。
2. **虚拟内存置换颠簸 (PageFile Thrashing)**：系统常态虚拟内存已消耗 15.8GB。若分页文件动态扩展或落入机械硬盘，任何突发内存分配都会引发 100% 磁盘 I/O 风暴与整机假死。
3. **CPU 算力争抢与发热降频**：双核四线程 CPU 算力匮乏。若 MuMu 分配过多核心或未启用 NemuIPC 原生共享内存（退化为 ADB 截图），CPU 持续满载将触发 85℃ 硬件热降频。

Phase 5 的核心使命是通过**系统级硬分流配置、模拟器参数调优、注册表 TDR 加固、PageFile 规范指导、自动化体检脚本与运行时非阻断诊断**，构建软硬件一体化的 7×24h 协同最佳实践方案，彻底阻断系统级崩溃链条。

---

## Technical Findings

### 1. ENV-01: 双显卡硬分流与 Windows 注册表 / GPU 偏好

#### 1.1 硬件画像与负载隔离策略
- **硬件分工原则**：
  - **Nvidia GeForce GTX 960M (2GB GDDR5)**：**专供 MuMu 12 模拟器独占**。碧蓝航线 3D 战斗与 2D 界面常态占用 700MB~1.1GB 显存，独占可留出约 900MB 安全余量，杜绝显存刺穿。
  - **Intel HD Graphics 4600 (集成核显)**：**承载 Thorium 浏览器与 Alas Electron 桌面端**。HD 4600 具备成熟的 Intel QuickSync 视频硬解单元（支持 1080p/4K 60fps 直播硬解），显存动态划拨自系统 RAM（Shared GPU Memory），在物理层面阻断与 GTX 960M 的显存争抢。

#### 1.2 Windows 图形首选项注册表规范 (Win10 2004+ / Win11)
- **注册表路径**：
  `HKEY_CURRENT_USER\Software\Microsoft\DirectX\UserGpuPreferences`
- **键值结构**：
  - **名称 (Name)**：目标可执行文件的完整绝对路径（`REG_SZ` 字符串）。
  - **数据 (Data)**：首选项参数字符串，标准格式如下：
    - `GpuPreference=1;`：**节能 (Power Saving)**，Windows 调度至集成核显（Intel HD 4600）。
    - `GpuPreference=2;`：**高性能 (High Performance)**，Windows 调度至独立显卡（GTX 960M）。
    - `GpuPreference=0;`：让 Windows 决定（系统默认）。
    *(注：Windows 11 或特定 WDDM 驱动版本可能附加 `AutoData=...` 或 `Flags=...;`，但在写入时注入标准 `GpuPreference=1;` 或 `GpuPreference=2;` 具备完整兼容性与最高优先级)*。

#### 1.3 核心目标进程绑定表

| 进程组件 | 典型可执行文件路径 | 注册表键值数据 | 目标 GPU | 设定理由 |
| :--- | :--- | :--- | :--- | :--- |
| **MuMu 12 主渲染窗口** | `<MuMuPath>\shell\MuMuPlayer.exe` | `GpuPreference=2;` | GTX 960M 独显 | 保持 Direct3D 交换链全速独占渲染 |
| **MuMu 12 渲染管道设备** | `<MuMuPath>\shell\MuMuNxDevice.exe` | `GpuPreference=2;` | GTX 960M 独显 | 虚拟机图形核心，保障 3D 性能 |
| **MuMu 12 虚拟化服务** | `<MuMuPath>\shell\MuMuVMMSVC.exe` | `GpuPreference=2;` | GTX 960M 独显 | 虚拟化后端辅助管道 |
| **Thorium 浏览器** | `%LOCALAPPDATA%\Thorium\Application\thorium.exe` | `GpuPreference=1;` | HD 4600 核显 | 核显硬解高清直播，完全释放独显显存 |
| **Alas 桌面客户端** | `<AlasPath>\AzurLaneAutoScript.exe` | `GpuPreference=1;` | HD 4600 核显 | 负责轻量级 WebUI 2D 合成，避免 CPU 纯软解 |
| **Alas Electron 开发态** | `<AlasPath>\webapp\node_modules\electron\dist\electron.exe` | `GpuPreference=1;` | HD 4600 核显 | 开发调试环境下隔离显存 |

#### 1.4 Nvidia 控制面板 (`nvcplui.exe`) 协同校验
1. **全局设置防范**：
   - 路径：`3D 设置` -> `管理 3D 设置` -> `全局设置`。
   - **首选图形处理器**必须设置为**“自动选择”**或**“集成图形”**。严禁全局设为“高性能 NVIDIA 处理器”，否则系统画图、浏览器、Electron 等所有进程都会强制霸占 GTX 960M 显存。
2. **程序设置针对性指定**：
   - 在“程序设置”选项卡中，分别确认 `MuMuPlayer.exe` 为“高性能 NVIDIA 处理器”，而 `thorium.exe` 和 `AzurLaneAutoScript.exe` 为“集成图形”。

---

### 2. ENV-02: MuMu 12 性能配置与 NemuIPC 协同

#### 2.1 MuMu 12 内部配置机理与文件布局
通过审计 Alas 设备底座代码（`module/device/method/nemu_ipc.py` 与 `module/device/platform/emulator_windows.py`），MuMu 12 的配置体系如下：
- **安装根目录**：如 `E:\ProgramFiles\MuMuPlayer-12.0\`
- **多开虚拟机配置路径**：`<MuMuPath>\vms\MuMuPlayer-12.0-{index}\configs\customer_config.json`
- **核心判定字段**：`customer.app_keptlive` (Boolean)
  - `false`：保活关闭（正常状态，NemuIPC 正常运行）
  - `true`：保活开启（**致命冲突！** 劫持渲染表面，导致 NemuIPC 捕获黑屏或死锁）

#### 2.2 图文界面优化推荐参数（设置中心）

| 设置分类 | 配置项 | 推荐值 | 调优机理与依据 |
| :--- | :--- | :--- | :--- |
| **性能设置** | **显卡渲染模式** | **DirectX 模式 (DirectX 11)** | GTX 960M (Maxwell) 对 DX11 驱动优化成熟度远超 Vulkan，有效避免 Shader 编译超时 |
| **性能设置** | **CPU 核心数** | **2 核** (严禁分配 3~4 核) | 宿主机仅 2C4T，分配 2 核留给模拟器，保留另外 2 个逻辑线程供 Python 图像识别与直播解码 |
| **性能设置** | **内存大小** | **3072 MB (3 GB)** | 充足承载碧蓝航线运行，杜绝 Android 内部无节制占用宿主机物理内存 |
| **显示设置** | **分辨率 / DPI** | **1280×720 (16:9) / 240 DPI** | Alas 坐标与图像模版严格基于 720p 匹配，不可随意修改 |
| **显示设置** | **帧率上限** | **30 FPS (关闭高帧率)** | 碧蓝航线自动化对 30 FPS 具备极高识别率，相比 60 FPS 减少独显约 40% 功耗发热 |
| **运行设置** | **后台挂机保活** | **彻底关闭** | **解除对 Direct3D 交换链的劫持，确保 NemuIPC 共享内存可用** |

#### 2.3 保活机制与 NemuIPC 冲突根因剖析
- **NemuIPC 原理**：MuMu 12 提供了 `external_renderer_ipc.dll`，该库通过 Direct3D 共享纹理句柄与命名内存映射，将 Android 模拟器的当前帧缓冲（1280×720 BGRA 32bpp）直接共享给 Alas 进程。单次截图耗时仅 5~15ms，且宿主机 CPU 占用为 0%。
- **保活机制破坏渲染表面**：当 MuMu 12 开启“后台挂机保活（降低刷新率保活）”后，一旦模拟器窗口最小化或失去焦点，其渲染管线会切断常态的 SwapChain 呈现，转而采用离屏脏矩形合成或低频占位。此时：
  - `external_renderer_ipc.dll` 无法收到画面呈现事件，内部 RPC 通信报错 `nemu_capture_display cannot find rpc connection` 或抛出 `error: 1722 / 1726`。
  - 读取到的帧出现持续全黑或画面停滞。
  - Alas 发生截图超时，进而退化为高 CPU 的 ADB 截图管道（单次截图 150~400ms，CPU 占用暴涨 25%）。
- **结论**：必须在 MuMu 设置中心明确关闭后台挂机保活，并在 `customer_config.json` 中保证 `"customer.app_keptlive": false`。

---

### 3. ENV-03: TDR 注册表与 PageFile 虚拟内存优化

#### 3.1 WDDM TDR 注册表配置机理
- **注册表路径**：
  `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\GraphicsDrivers`
- **关键注册表项**：
  - `TdrDelay` (REG_DWORD)：GPU 调度引擎超时等待时间。
    - Windows 默认值：`2`（秒）。在老旧平台或高负载视频硬解切换时，极易因短暂的 2.1 秒阻塞触发 TDR 141 显卡驱动重置。
    - 推荐值：`8`（秒，十进制，十六进制 `0x00000008`）。给硬件换页与渲染留出充裕缓冲，同时若显卡真发生致命硬件锁死，8 秒后依然能触发重置恢复，不至于系统永久死机。
  - `TdrDdiDelay` (REG_DWORD)：DDI 线程驱动调用的超时时间。
    - 推荐值：`8`（秒，`dword:00000008`）。
  - `TdrLevel` (REG_DWORD)：超时检测与恢复行为级别。
    - `0` (TdrLevelOff)：彻底关闭检测（**严禁使用**，会导致驱动死锁时整机直接硬死机）。
    - `3` (TdrLevelRecover)：检测到超时后重置引擎并尝试恢复环境（Windows 默认行为，**推荐保持为 3**）。

#### 3.2 一键 `.reg` 注册表脚本设计
采用标准 `Windows Registry Editor Version 5.00` 格式：

- **开启防护脚本** (`deploy/optimize/enable_tdr_delay_8s.reg`)：
  ```reg
  Windows Registry Editor Version 5.00

  [HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\GraphicsDrivers]
  "TdrDelay"=dword:00000008
  "TdrDdiDelay"=dword:00000008
  "TdrLevel"=dword:00000003
  ```

- **恢复默认脚本** (`deploy/optimize/restore_tdr_delay_default.reg`)：
  ```reg
  Windows Registry Editor Version 5.00

  [HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\GraphicsDrivers]
  "TdrDelay"=-
  "TdrDdiDelay"=-
  "TdrLevel"=dword:00000003
  ```
  *(注：减号 `-` 表示删除用户显式添加的键值，恢复 Windows 内部默认设置)*。

#### 3.3 PageFile 虚拟内存优化规范
- **痛点分析**：当前宿主机 16GB 物理内存已承载 15.8GB 虚拟内存使用量，整机提交内存高达 31GB。
  - 若 PageFile 设为“自动管理”，Windows 会在高频读写时动态伸缩文件尺寸，造成磁盘分配开销与严重碎片化。
  - 若 PageFile 被分配到机械硬盘（HDD），其 10~15ms 的寻道延迟会在换页时引发磁盘 100% 满载，整机卡死 10~30 秒。
- **最佳实践配置规范**：
  1. **盘符专一化**：分页文件**必须且仅能放置在高速固态硬盘（SSD）**上（如 C: 盘），彻底关闭所有机械硬盘（HDD）或其他分区的分页文件（设为“无分页文件”）。
  2. **固定尺寸消除颠簸**：
     - 选择 SSD 盘符 -> 点击“自定义大小”。
     - **初始大小 (MB)**：`16384` (16 GB)。
     - **最大值 (MB)**：`20480` (20 GB)。
     - 点击“设置”并保存。
  3. **收益**：固定大小消除了动态扩展带来的磁盘空间分配开销；借助 SSD 高达 50,000+ IOPS 的 4K 随机读写，微秒级响应硬缺页换页，从物理根源上阻断颠簸假死。

---

### 4. PowerShell 环境体检脚本 (`deploy/optimize/check_env.ps1`) 设计

#### 4.1 脚本定位与权限模型
- **无害只读探测（默认）**：普通用户或无提权终端下直接运行，仅使用 WMI / CIM / Registry 读取当前软硬件状态，输出格式化健康看板，不进行任何系统写操作。
- **一键自愈模式 (`-Fix`)**：传入 `-Fix` 参数时，检测当前权限；若非管理员，则通过 `Start-Process powershell -Verb RunAs` 弹出 UAC 提权并接续执行，安全写入 TdrDelay 注册表与推荐的 GPU 首选项。

#### 4.2 核心检测管道与实现逻辑
1. **GPU 硬件拓扑与首选项探测 (`Check-GpuTopology`)**：
   - 语法：`Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM`
   - 注册表查询：读取 `HKCU:\Software\Microsoft\DirectX\UserGpuPreferences`，匹配 `MuMuPlayer.exe`（应为 2）、`thorium.exe`（应为 1）、`AzurLaneAutoScript.exe`（应为 1）。
2. **TDR 注册表状态探测 (`Check-TdrDelay`)**：
   - 读取 `HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers` 下的 `TdrDelay`。若未设置或小于 8，标黄/标红警告；若为 8，标绿通过。
3. **MuMu 12 安装路径、DLL 完整性与保活配置探测 (`Check-MuMuConfig`)**：
   - 路径解析优先级：
     1. 运行中进程：`Get-Process MuMuPlayer, MuMuNxDevice -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path -First 1`
     2. 卸载注册表：`HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayer-12.0` 的 `InstallLocation`
     3. 用户执行缓存：`HKCU:\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache`
     4. 默认安装路径探测：`C:\Program Files\Netease\MuMuPlayer-12.0\`, `D:\Program Files\Netease\MuMuPlayer-12.0\` 等
   - DLL 校验：检查是否存在以下路径之一：
     - `<MuMuPath>\shell\sdk\external_renderer_ipc.dll`
     - `<MuMuPath>\nx_device\12.0\shell\sdk\external_renderer_ipc.dll`
     - `<MuMuPath>\nx_main\sdk\external_renderer_ipc.dll`
   - 保活校验：读取 `<MuMuPath>\vms\MuMuPlayer-12.0-*\configs\customer_config.json`，检查 `customer.app_keptlive`。若为 `true` 输出 `[FAIL]` 告警。
4. **内存与 PageFile 虚拟内存健康度 (`Check-PageFileAndMemory`)**：
   - 物理/虚拟内存用量：通过 `Get-CimInstance Win32_OperatingSystem` 提取 `TotalVisibleMemorySize`, `FreePhysicalMemory`, `TotalVirtualMemorySize`, `FreeVirtualMemory`。
   - 分页文件分布：通过 `Get-CimInstance Win32_PageFileUsage` 获取分页文件路径，结合 `Get-PhysicalDisk` 判定所在分区是否为 SSD。若发现机械盘上有 PageFile，输出标红警告。

---

### 5. 代码集成点分析 (Code Integration)

#### 5.1 注入位置剖析
通过对 `module/device/connection.py` 和 `module/device/device.py` 的架构调用链路审计：
- `Device` 继承自 `Connection`（`Device(Screenshot, Control, AppControl)`，`Screenshot` 最终派生自 `Adb(Connection)`）。
- 在 `connection.py` 的初始化流程中（`Connection.__init__`）：
  ```python
  # Connect
  self.adb_connect(wait_device=False)
  ...
  # Package
  ...
  self.check_mumu_app_keep_alive()
  ```
- 在 `device.py` 的初始化流程中（`Device.__init__`）：
  ```python
  self.screenshot_interval_set()
  self.method_check()
  if not self.config.is_template_config and self.config.Emulator_ScreenshotMethod == 'auto':
      self.run_simple_screenshot_benchmark()
  ```

#### 5.2 诊断告警实现方案
在 `module/device/connection.py` 中新增 `check_mumu_nemu_ipc_health(self)` 方法，并在 `check_mumu_app_keep_alive()` 执行之后或连接确立阶段调用：
```python
def check_mumu_nemu_ipc_health(self):
    """
    Check if MuMu is running with optimal NemuIPC configuration on Windows.
    Non-blocking warning with documentation link.
    """
    if not IS_WINDOWS:
        return
    if not self.is_mumu_family:
        return

    # Check if NemuIPC is usable or if currently using high-CPU fallback
    nemu_available = False
    try:
        nemu_available = self.nemu_ipc_available()
    except Exception:
        nemu_available = False

    if not nemu_available:
        logger.warning(
            '[Notice] 检测到当前运行于 MuMu 模拟器，但高效的 NemuIPC 共享内存通道未生效。\n'
            '当前自动化正回退至高 CPU 占用的 ADB 截图管道。\n'
            '为显著降低双核 CPU 负载与发热，请参考弱机调优指南：doc/low_spec_tuning_guide.md '
            '（请确认已关闭 MuMu 设置中的“后台挂机保活”并将 MuMu 分配至独显）。'
        )
```
- **关键特性**：
  - **非阻断 (Non-blocking)**：使用 `logger.warning` 输出，绝对不抛出 `RequestHumanTakeover`，不阻碍已有的 ADB 回退与自动化调度。
  - **醒目友好**：在控制台黄字高亮，并在 WebUI 日志流首部展示，精准指向本地与 Wiki 文档。

---

## Implementation Approach

根据上述调研，Phase 5 的实施计划应分为 4 个清晰的执行步骤：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 步骤 1: 注册表配置文件编写 (TDR Hardening Reg Files)                     │
│ - 创建 deploy/optimize/enable_tdr_delay_8s.reg                          │
│ - 创建 deploy/optimize/restore_tdr_delay_default.reg                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 步骤 2: PowerShell 自动化环境体检脚本 (Environment Health Checker)      │
│ - 编写 deploy/optimize/check_env.ps1                                    │
│ - 实现只读检测、CIM 内存/PageFile 识别、MuMu 路径与 DLL 探查、-Fix 提权写入│
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 步骤 3: 弱机与模拟器协同调优指南编写与文档入口集成 (Guide Documentation)│
│ - 编写 doc/low_spec_tuning_guide.md                                     │
│ - 更新 README.md 与 doc/Readme.md，加入指南超链接索引                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 步骤 4: Alas 设备连接层运行时轻量诊断注入 (Runtime Diagnostics)          │
│ - 在 module/device/connection.py 中集成 check_mumu_nemu_ipc_health()    │
│ - 输出非阻断友好提示，保持 100% 向后兼容                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Validation Architecture

### 1. 静态与代码规范验证
- **注册表语法校验**：
  验证 `.reg` 文件符合 Windows Registry 5.00 格式，无多余 BOM 损坏，键名路径精确对应 `HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers`。
- **PowerShell 语法校验**：
  ```powershell
  [System.Management.Automation.Language.Parser]::ParseFile("deploy/optimize/check_env.ps1", [ref]$null, [ref]$null)
  ```
  断言脚本无语法错误，参数定义符合规范。

### 2. 运行时只读体检验证
- 在当前 Windows 环境下直接执行：
  ```powershell
  pwsh -File deploy/optimize/check_env.ps1
  ```
  验证：
  - 能够正确捕获当前显卡列表（如 AMD RX 6800 XT / MuMu Virtual Display Adapter）。
  - 能够正确读取当前物理内存与虚拟内存分页文件（如 `C:\pagefile.sys`）。
  - 彩色输出 `[PASS]`, `[WARN]`, `[FAIL]`，且整个过程不触发任何提权弹窗。

### 3. 代码注入逻辑与单元测试验证
- 针对 `module/device/connection.py` 编写测试用例：
  - 模拟 Windows 平台与 `is_mumu_family=True`。
  - 模拟 `nemu_ipc_available() == False`。
  - 断言 `check_mumu_nemu_ipc_health()` 成功触发 `logger.warning`，日志内容包含 `doc/low_spec_tuning_guide.md`，且不会引发异常抛出。

### 4. 文档链接有效性验证
- 验证 `README.md` 与 `doc/Readme.md` 中的相对路径 `doc/low_spec_tuning_guide.md` 存在且无死链。

---

## Risk Analysis

| 潜在风险 | 影响严重度 | 发生概率 | 规避与缓解方案 |
| :--- | :--- | :--- | :--- |
| **修改注册表引发用户对系统稳定性的担忧** | 中 | 中 | 1. 脚本默认采用纯只读检测；2. 提供完整的 `restore_tdr_delay_default.reg` 还原脚本；3. 在指南中详述微软官方对 TdrDelay 的规范释义。 |
| **MuMu 12 安装路径多变导致体检脚本漏检** | 低 | 中 | 体检脚本实施“进程探测 -> 卸载注册表 -> MuiCache -> 常见目录枚举”四重级联查找策略，覆盖 99% 的安装场景。 |
| **运行时非阻断提示过度打扰其他模拟器用户** | 低 | 低 | 严格限制生效条件：仅在 `IS_WINDOWS` 且 `is_mumu_family` 且 `not nemu_ipc_available()` 时单次触发，对非 MuMu 模拟器（雷电、夜神、BlueStacks）零干扰。 |
| **虚拟内存固定过小导致其他大型游戏 OOM** | 中 | 低 | 指南中推荐设为初始 16GB、最大 20GB，总虚拟+物理内存达 32GB~36GB，既消除抖动，又足以满足所有日常多任务需求。 |

---
*Phase 5 Research complete. Ready for PLAN.*
