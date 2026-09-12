---
phase: "05"
plan: "01"
subsystem: doc/optimize
tags:
  - tdr
  - mumu12
  - nemuipc
  - pagefile
  - gpu-offloading
  - low-spec
requires: []
produces:
  - deploy/optimize/enable_tdr_delay_8s.reg
  - deploy/optimize/restore_tdr_delay_default.reg
  - doc/low_spec_tuning_guide.md
commits:
  - 5c0a20ff6: "docs(optimize): add tdr delay 8s registry hardening and restore scripts"
  - bc6535012: "docs(guide): add low spec hardware and mumu 12 co-optimization guide"
  - 1ab3a1ef1: "docs(readme): add link to low spec tuning guide"
---

# Plan 05-01: 核心调优指南文档与 TDR 容灾注册表配置 - Execution Summary

## 执行概览

本计划围绕老旧双核移动平台（基准画像：Intel i5-4210H 2C4T + GTX 960M 2GB / HD 4600 + 16GB 物理内存 / 15.8GB 虚拟内存置换重压），完成了完整的系统级软硬件协同调优指南主文档、Windows TDR 驱动超时容灾加固注册表脚本以及主文档超链接导航集成，严格兑现了决策 D-01 至 D-09、D-13、D-14。

## 任务执行明细

| 任务 ID | 类型 | 说明 | 交付产物 | 状态 / 提交哈希 |
| :--- | :--- | :--- | :--- | :--- |
| **05-01-01** | config | 创建 TDR 延迟 8 秒加固与默认恢复注册表脚本 | `deploy/optimize/enable_tdr_delay_8s.reg`<br>`deploy/optimize/restore_tdr_delay_default.reg` | ✅ 完成<br>`5c0a20ff6` |
| **05-01-02** | doc | 编写弱机与模拟器协同调优指南主文档 | `doc/low_spec_tuning_guide.md`（共 315 行，近 1.3 万字符） | ✅ 完成<br>`bc6535012` |
| **05-01-03** | doc | 在项目主文档与 README 中集成调优指南入口 | `doc/Readme.md`<br>`README.md` | ✅ 完成<br>`1ab3a1ef1` |

## 核心交付产物与技术细节

### 1. WDDM TDR 注册表加固与恢复脚本 (`deploy/optimize/`)
- `enable_tdr_delay_8s.reg`：
  - 路径：`[HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\GraphicsDrivers]`
  - 注入参数：`"TdrDelay"=dword:00000008` 与 `"TdrDdiDelay"=dword:00000008`（GPU 调度与 DDI 驱动超时由默认 2 秒放宽至 8 秒，吸收瞬态显存换页抖动）；
  - 保持防线：`"TdrLevel"=dword:00000003`（维持 `TdrLevelRecover` 恢复级别，严禁设为 0 关闭超时检测导致真死机无法自愈）。
- `restore_tdr_delay_default.reg`：
  - 使用注册表减号语法（`"TdrDelay"=-`、`"TdrDdiDelay"=-`）无残留清理自定义值，安全恢复 Windows 默认行为。

### 2. 弱机与模拟器协同最佳配置指南 (`doc/low_spec_tuning_guide.md`)
文档采用「分层速查手册 + 故障排查手册 (FAQ)」双层架构，全文核心内容涵盖：
- **前言与硬件画像**：详细解析 i5-4210H + GTX 960M 2GB 在并发 MuMu 12、Thorium 高清直播、网易云音乐与 Alas 时的三大痛点（显存刺穿触发 LiveKernelEvent 141、SSD 磁盘颠簸假死、CPU 双核争抢热降频）。
- **3 分钟极速配置推荐表**：提炼 GPU 分流、CPU/RAM 配额、DirectX 11、30 FPS、关闭挂机保活、固定 PageFile、TDR 8 秒加固与 99% 最大处理器状态的参数速查表。
- **分步配置操作详解**：
  - **Windows 图形首选项硬分流**：详细步骤指导 Win10/Win11 界面操作，绑定 MuMuPlayer 至独显高性能，Thorium 与 Alas 绑定至核显节能；深度剖析注册表 `HKCU\Software\Microsoft\DirectX\UserGpuPreferences` 规范（`GpuPreference=2;` 与 `GpuPreference=1;`）；防范 Nvidia 控制面板全局覆盖独显。
  - **MuMu 12 性能参数与保活关闭**：明确分配 2 核 + 3072 MB 内存、锁定 30 FPS、DirectX 11 渲染；**深度剖析保活机制危害**（`customer.app_keptlive: false`，保活劫持 SwapChain 导致 NemuIPC 抛出 RPC 1722/1726 异常并退化为高 CPU ADB 截图）。
  - **SSD PageFile 虚拟内存规整**：彻底关闭机械硬盘分页，在 SSD 设置固定 16384 MB ~ 20480 MB 尺寸，彻底消除动态伸缩引发的 100% 磁盘 I/O 假死。
  - **TDR 注册表加固与防蓝屏**：解析超时原理与一键导入/恢复方法。
  - **系统电源计划与散热优化**：平衡计划，最大处理器状态设为 99% 压制 Haswell 过热睿频，关闭 USB 选择性暂停。
- **运行状态验证与故障排查 (FAQ)**：
  - 提供 Windows 任务管理器 GPU 0 / GPU 1 引擎与显存分工对照表；
  - NemuIPC 掉落 ADB 告警排查四步法（查保活、查显卡、查 DLL、查模拟器索引）；
  - LiveKernelEvent 141 黑屏排查与散热清灰建议；
  - 严禁降低游戏内 720p 分辨率以防破坏 Alas 图像模版识别体系的红线说明。

### 3. 主文档与根目录入口导航
- `doc/Readme.md`：新增指向 `low_spec_tuning_guide.md` 的中文直达超链接条目。
- `README.md`：在“安装 Installation / 设备支持文档”小节添加 `[弱机与模拟器 7x24h 协同优化指南](doc/low_spec_tuning_guide.md)` 导航入口。

## 验证结论

- **注册表语法检验**：通过 `pwsh` 验证 `.reg` 文件符合标准 Windows Registry 5.00 语法，无损坏 BOM。
- **文档关键词与字符量检验**：
  - 关键技术字符串全量覆盖（`UserGpuPreferences`, `customer.app_keptlive`, `TdrDelay`, `PageFile`, `enable_tdr_delay_8s.reg`, `DirectX 11`, `30 FPS`）。
  - 总字符数达到 12,948 字符（远超 2000 字验收标准）。
- **链接完整性检验**：`doc/Readme.md` 与 `README.md` 的相对链接均指向真实有效的物理文件。

## 决策履行核对

- [x] **D-01**: Windows 图形首选项硬分流指引已就绪并包含注册表规范。
- [x] **D-02**: `deploy/optimize/enable_tdr_delay_8s.reg` 与 `restore_tdr_delay_default.reg` 已就绪。
- [x] **D-03**: 锁死 Thorium 浏览器与 Electron 于核显且保持硬件加速已详述。
- [x] **D-04**: 提供任务管理器 GPU 0 / GPU 1 负载与 GPU-Z 双重验证手段。
- [x] **D-05**: MuMu 12 推荐 2 核 CPU + 3072 MB 内存。
- [x] **D-06**: 锁定 MuMu 12 帧率上限为 30 FPS。
- [x] **D-07**: 推荐 DirectX 11 渲染引擎模式。
- [x] **D-08**: 深度解析并要求彻底关闭后台挂机保活以确保 NemuIPC 生效。
- [x] **D-09**: PageFile 固定于 SSD（16GB~20GB），彻底关闭机械硬盘分页。
- [x] **D-13**: 指南文档位于 `doc/low_spec_tuning_guide.md` 并在 README 与主文档建立索引。
- [x] **D-14**: 采用分层速查手册 + 故障排查手册 (FAQ) 架构。

---
*Plan 05-01 executed successfully. Ready for Plan 05-02.*
