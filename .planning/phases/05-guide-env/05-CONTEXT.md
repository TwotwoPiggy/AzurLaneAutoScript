# Phase 5: 弱机与模拟器协同最佳配置 - Context

**Gathered:** 2026-09-12
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段聚焦于为老旧双核移动平台（以 Intel Core i5-4210H 2C4T、GTX 960M 2GB + HD 4600 双显卡、16GB 物理内存但承受 15.8GB 虚拟内存置换重压为基准）在 7×24 小时无人值守挂机期间，与网易 MuMu 12 模拟器、Thorium 浏览器（高清直播硬解）、网易云音乐及 Alas 桌面端并发运行提供系统级的硬分流、低能耗调优、虚拟内存/TDR 防护建议及配套自动化脚本与运行时诊断。

- **In Scope:**
  - 提供 Windows 图形性能首选项与 Nvidia 控制面板双显卡硬分流详细配置指南（GTX 960M 独供 MuMu 12，HD 4600 核显承载 Thorium 与 Electron）。
  - 提供 Windows 注册表 `TdrDelay` / `TdrLevel` 超时参数防护配置与配套一键 `.reg` 导入/恢复文件。
  - 提供 MuMu 12 性能设置（核心分配 2 核、内存 3GB、帧率锁定 30 FPS、DirectX 11 渲染引擎、关闭“后台挂机保活”以确保 NemuIPC 生效）专项指南。
  - 提供系统级虚拟内存优化建议（固定 PageFile 在高速 SSD 盘，避免动态扩展引发磁盘 100% 颠簸假死）与电源散热优化建议。
  - 配套提供 PowerShell 自动化环境体检脚本（`deploy/optimize/check_env.ps1`），一键校验 GPU 首选项、TdrDelay、NemuIPC DLL 与虚拟内存状态。
  - 在 Alas 设备连接初始化环节注入轻量级诊断警告（若连接 MuMu 但 NemuIPC 未生效，输出非阻断友好提示与文档链接）。
  - 指南文档归档于 `doc/low_spec_tuning_guide.md` 并在 README 与主文档中建立索引。
- **Out of Scope:**
  - 侵入式重写 NemuIPC 底层 C 通信逻辑或重构 Electron 核心架构（在 Phase 1~4 核心代码阶段处理）。
  - 强制降低游戏内渲染分辨率至 1280×720 以下（避免破坏 Alas 坐标与图像模版匹配体系）。
  - 无脑定时强行重启模拟器或操作系统（冷启动会带来巨大的 CPU 与磁盘 IO 峰值冲击）。

</domain>

<decisions>
## Implementation Decisions

### 双显卡分流与 TDR 容灾配置 (GPU Offloading & TDR Hardening)
- **D-01 (双显卡分流指引入口):** 采用「Windows 图形性能首选项（主推）+ Nvidia 控制面板（校验辅助）」双重配置路径。Win10 2004+ / Win11 统一在“系统 -> 屏幕 -> 显示卡/图形设置”中将 MuMuPlayer 绑定至高性能（GTX 960M），将 Thorium 浏览器和 Electron（Alas 桌面端）绑定至节能（Intel HD 4600 核显）；在 Nvidia 控制面板 3D 设置中确保全局不强行覆盖为独显。
- **D-02 (TDR 超时注册表防护):** 将注册表 `HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers` 下的 `TdrDelay` 由默认 2 秒调整为 8 秒，配套提供一键导入脚本 `deploy/optimize/enable_tdr_delay_8s.reg` 与恢复脚本 `deploy/optimize/restore_tdr_delay_default.reg`，既留出高负荷时的显卡渲染缓冲，又避免系统真死机时永久挂起。
- **D-03 (Thorium 浏览器与 Electron 显存隔离):** 指南中明确指导将 Thorium 浏览器设置中“使用图形加速”保持开启（利用核显硬解 1080p/4K 60fps 直播，避免双核 CPU 软解爆炸），但操作系统级锁死在 HD 4600 核显，杜绝其侵占 GTX 960M 2GB 独立显存。
- **D-04 (分流状态双重验证手段):** 指南提供 Windows 任务管理器与 GPU-Z 双重验证方法：运行 MuMu + Thorium 直播 + Alas 时，任务管理器中 GPU 1 (GTX 960M) 仅由 `MuMuPlayer.exe` 产生 3D 计算与显存占用，GPU 0 (HD 4600) 负责 `thorium.exe` 视频解码（Video Decode）与 Electron 桌面端合成，提供图文状态对照表。

### MuMu 12 性能参数与 NemuIPC 协同 (MuMu 12 Optimization & NemuIPC Prerequisite)
- **D-05 (模拟器核心与内存分配):** 针对 i5-4210H (2C4T) + 16GB 内存机型，MuMu 12 推荐配置为「2 核 CPU + 3GB (3072MB) 内存」。严禁分配 3~4 核（会剥夺宿主机调度资源，导致直播与 Python 图像识别严重卡顿），严禁分配超过 4GB 内存（避免 Android 虚拟机无节制占用宿主机物理内存）。
- **D-06 (模拟器后台帧率上限压制):** MuMu 12 显示设置中强制锁定最大帧率为「30 FPS」。30 FPS 在碧蓝航线战斗与菜单中完全满足流畅识别，相较 60 FPS 减少独显约 40% 的渲染负载与功耗发热，且避免 20 FPS 下偶发转场动画识别丢帧。
- **D-07 (渲染引擎选型):** 渲染模式选用「DirectX 11 (DirectX 模式)」。GTX 960M (Maxwell 架构) 的 Nvidia 驱动对 DirectX 11 具备长达数年的成熟优化，相比老架构的 Vulkan 兼容层更少出现显存泄漏与特定 shader 编译超时导致 TDR 141 驱动重置。
- **D-08 (关闭后台挂机保活保障 NemuIPC):** 详细指导在 MuMu 12「设置中心 -> 运行与保活」中关闭「后台挂机保活（降低刷新率保活）」。解释保活机制会劫持渲染表面导致共享内存 `external_renderer_ipc.dll` 无法获取到有效帧，必须关闭保活以确保 NemuIPC 原生共享内存零 CPU 截图常态运行。

### 系统级虚拟内存优化与环境体检脚本 (Virtual Memory & Environment Health Check)
- **D-09 (系统分页文件配置):** 针对系统 15.8GB 虚拟内存重压，明确指导「分页文件（PageFile）必须且仅能设在高速固态硬盘（SSD）上，严禁放置在机械硬盘（HDD），且设置固定大小（初始 16384MB，最大 20480MB），关闭其他盘符分页文件」，消除 Windows 动态扩展分页文件引发的磁盘 100% 饱和与硬缺页假死。
- **D-10 (自动化环境体检脚本):** 在 `deploy/optimize/` 下编写配套 PowerShell 体检脚本 `check_env.ps1`，自动化检测：① 当前活动 GPU 与图形首选项注册表；② MuMu 12 安装路径及 `external_renderer_ipc.dll` 完整性；③ `TdrDelay` 注册表值；④ PageFile 磁盘分布及系统物理/虚拟内存余量。
- **D-11 (脚本权限与无害化执行):** 体检脚本设计为「默认只读检测，无需管理员权限」；支持 `-Fix` 参数或提示交互确认后以管理员权限执行一键写入（写入 TdrDelay 注册表与 Windows 图形首选项注册表），保证过程完全透明可控。
- **D-12 (系统电源计划与发热抑制):** 推荐 Windows 电源计划设置为「平衡」，并将“最大处理器状态”调整为 99%（关闭 Haswell 笔记本容易过热的高频睿频，防止温度触碰 85℃ 硬件热降频线），同时关闭“USB 选择性暂停”以防 ADB 连接无故断开。

### 指南交付载体与运行时集成 (Guide Delivery & Runtime Integration)
- **D-13 (文档存储路径与入口):** 指南文档主文件命名为 `doc/low_spec_tuning_guide.md`，并在根目录 `README.md` 与 `doc/Readme.md` 中添加“弱机与低配环境 7×24h 协同优化指南”超链接入口。
- **D-14 (分层速查与故障排查架构):** 文档采用「分层速查手册 + 故障排查手册 (FAQ)」结构组织：
  1. 3 分钟极速配置推荐表（核心参数一览）
  2. 分步图文操作详解（Windows 图形设置、MuMu 12 设置、虚拟内存与注册表）
  3. 常见问题排查（TDR 141 黑屏恢复、NemuIPC 退化 ADB 排查、直播卡顿排查）
- **D-15 (运行时非阻断诊断提示):** 在 Alas 设备连接与初始化逻辑中（`module/device/connection.py`），当检测到运行在 Windows 平台且连接 MuMu 模拟器时，若 NemuIPC 未能成功建立而回退至 ADB，在控制台日志与 WebUI 任务首行输出轻量级诊断警告（如 `[Notice] MuMu NemuIPC 共享内存未生效，正使用高 CPU 的 ADB 管道。请参考 doc/low_spec_tuning_guide.md 关闭 MuMu 后台保活并配置独显`），不阻断自动化执行。
- **D-16 (脚本与配置文件打包):** 将所有 `.reg` 注册表文件及 `check_env.ps1` 集中归档于 `deploy/optimize/`，随 Alas 源码仓库与发布压缩包一同分发。

### the agent's Discretion
用户在提问环节明确指定“所有 question 都用推荐项”，由 Agent 依据既有架构调研（ARCHITECTURE.md、PITFALLS.md）、Haswell i5 双显卡硬件特性及 Windows 10/11 WDDM 驱动层规范，全面锁定最专业、最稳健的推荐工程方案。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 调研与架构背景
- `.planning/research/ARCHITECTURE.md` — 弱机与模拟器并发运行架构全景
- `.planning/research/PITFALLS.md` — TDR 141 硬件重置成因与 WDDM 内存置换风暴分析
- `.planning/research/STACK.md` — NemuIPC 原生共享内存与 MuMu 12 兼容性规范
- `.planning/PROJECT.md` — 项目核心目标与硬件运行环境约束

### 设备连接与代码注入点
- `module/device/connection.py` — 设备连接探测、ADB 回退处理与诊断警告提示挂载点
- `module/device/method/nemu_ipc.py` — MuMu NemuIPC 共享内存动态库捕获与异常处理

### 待产出的目标文件
- `doc/low_spec_tuning_guide.md` — 弱机与模拟器协同最佳配置指南主文档
- `deploy/optimize/check_env.ps1` — 自动化环境体检与诊断脚本
- `deploy/optimize/enable_tdr_delay_8s.reg` — TDR 超时延长 8s 注册表配置文件
- `deploy/optimize/restore_tdr_delay_default.reg` — 恢复默认 TDR 注册表配置文件

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `module/device/method/nemu_ipc.py`: 内部具备 `check_nemu_ipc_available()` 与 `external_renderer_ipc.dll` 路径探测逻辑，可在编写诊断提示或 PowerShell 体检脚本时参考其探测规则。
- `module/device/connection.py`: 设备连接状态调度器，具备 `detect_device()` 与降级捕获链条。

### Established Patterns
- Alas 在检测到用户配置或运行环境异常时（例如 ADB 端口冲突或包名不匹配），通常在 `logger.warning()` 中打印高亮黄字说明，并在 WebUI 日志流中展示。
- 部署脚本均放置于 `deploy/` 目录结构下。

### Integration Points
- `deploy/optimize/`: 存放调优相关的 PowerShell 脚本与 `.reg` 配置文件。
- `doc/`: 存放用户调优指南文档，与 `doc/Readme.md` 建立连接。
- `module/device/connection.py`: 在发现 MuMu 环境但 NemuIPC 加载失败时输出指向指南文档的提示。

</code_context>

<specifics>
## Specific Ideas

- 用户明确要求：“所有 question 都用推荐项”。
- 体检脚本 `check_env.ps1` 需兼顾易用性与安全性：默认执行只读检查，控制台以彩色输出 [PASS] / [WARN] / [FAIL]，仅在显式传入 `-Fix` 参数时请求提权并写入注册表。
- 注册表改动需提供完整的回退方案（`.reg` 还原文件），保证用户无后顾之忧。

</specifics>

<deferred>
## Deferred Ideas

None — 讨论严格聚焦于 Phase 5（弱机与模拟器协同最佳配置）的范围，未出现范围蔓延。

</deferred>

---

*Phase: 5-弱机与模拟器协同最佳配置*
*Context gathered: 2026-09-12*
