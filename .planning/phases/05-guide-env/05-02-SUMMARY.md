# Plan 05-02 执行总结：自动化体检诊断脚本与运行时轻量提示

**Phase:** 05 - guide-env (弱机与模拟器协同最佳配置)
**Plan:** 05-02
**Wave:** 2
**执行时间:** 2026-09-13
**提交哈希:** `7535239ac`

---

## 完成状态

| 任务 | 状态 | 产物 |
|------|------|------|
| 05-02-01 | ✅ 完成 | `deploy/optimize/check_env.ps1` |
| 05-02-02 | ✅ 完成 | `module/device/connection.py` — 注入 `check_mumu_nemu_ipc_health()` |
| 05-02-03 | ✅ 完成 | `tests/unit/test_mumu_health.py` — 4 passed |
| 05-02-04 | ✅ 完成 | Git 提交并推送至 `origin/custom` |

---

## 产物详情

### 1. `deploy/optimize/check_env.ps1`
PowerShell 自动化环境体检与自愈脚本：
- **参数**：`[switch]$Fix`（写入修复）、`[switch]$Help`（显示帮助）
- **默认只读**：普通用户权限，零 UAC 弹窗，秒级完成
- **四大检测函数**：
  - `Check-GpuTopology`：枚举 GPU 适配器、检查 `HKCU:\Software\Microsoft\DirectX\UserGpuPreferences` 中 MuMu/Thorium GPU 首选项
  - `Check-TdrDelay`：读取 `HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers` 中 TdrDelay/TdrDdiDelay/TdrLevel
  - `Check-MuMuConfig`：四重级联查找 MuMu 安装路径，探测 `external_renderer_ipc.dll`，解析 `customer_config.json` 中保活配置
  - `Check-PageFileAndMemory`：检查物理/虚拟内存与分页文件所在磁盘类型（SSD/HDD）
- **`-Fix` 模式**：提权后写入 TdrDelay=8、TdrDdiDelay=8、TdrLevel=3；自动写入 GPU 首选项注册表

### 2. `module/device/connection.py` — `check_mumu_nemu_ipc_health()`
- 在 `Connection` 类中 `check_mumu_app_keep_alive()` 之后（约 392 行）注入新方法
- `Connection.__init__` 中第 134 行调用 `self.check_mumu_nemu_ipc_health()`
- 守卫逻辑：非 Windows 或非 MuMu 家族直接返回，不产生任何副作用
- NemuIPC 可用性检测：优先调用 `nemu_ipc_available()`，回退检测 `nemu_ipc` 属性
- 不可用时打印 `logger.warning(...)` 含调优指南链接 `doc/low_spec_tuning_guide.md`
- **绝不抛出异常**，完全非阻断

### 3. `tests/unit/test_mumu_health.py`
4 个测试用例，覆盖所有代码路径：
- `test_non_windows_skip` — 非 Windows 平台跳过，无警告
- `test_non_mumu_skip` — 非 MuMu 模拟器跳过，无警告
- `test_mumu_with_nemu_ipc_available` — NemuIPC 可用，无警告
- `test_mumu_nemu_ipc_unavailable_triggers_warning` — NemuIPC 不可用，触发含文档链接的警告

**验证结果：** `python -m pytest tests/unit/test_mumu_health.py` — **4 passed**

---

## 需求覆盖

| 需求 ID | 覆盖情况 |
|---------|---------|
| ENV-02 | ✅ `check_env.ps1` 的 `Check-MuMuConfig` 检测保活与 NemuIPC；`check_mumu_nemu_ipc_health()` 运行时提示 |
| ENV-03 | ✅ `check_env.ps1` 的 `Check-TdrDelay` 和 `Check-PageFileAndMemory`；`-Fix` 模式修复 TDR 注册表 |

---

## 决策一致性验证

- **D-10** ✅：`check_env.ps1` 覆盖 GPU、TDR、MuMu 与 PageFile 四大检测
- **D-11** ✅：默认只读，`-Fix` 提权写入
- **D-15** ✅：非阻断 `logger.warning` 包含文档链接
- **D-16** ✅：脚本归档于 `deploy/optimize/`

---

## Git 记录

```
7535239ac feat(device): add mumu nemu ipc health check and env optimization scripts
  - deploy/optimize/check_env.ps1 (new)
  - tests/unit/test_mumu_health.py (new)
  - module/device/connection.py (modified)
```

推送至：`origin/custom` ✅
