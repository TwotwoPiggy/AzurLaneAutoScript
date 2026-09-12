# Plan 04-02 Summary: Win32 物理工作集修剪工具封装与任务边界 GC 闭环

## 执行概述 (Execution Overview)
- **Phase**: 04-stab-memory
- **Plan**: 02 (Wave 2)
- **需求与决策**: MEM-02, MEM-03 (D-05, D-06, D-07, D-08)
- **状态**: ✅ 已完成 (Completed)
- **提交信息**: `feat(resource): add Win32 EmptyWorkingSet memory trimming and GC cleanup` (commit `0a7477df0`)
- **远端推送**: 已成功推送至 `origin/custom` (通过本地代理 `http://127.0.0.1:10808`)

---

## 实施细节 (Implementation Details)

1. **底层跨平台内存工具库 (`module/base/memory_utils.py`)**:
   - 实现 `get_process_rss(pid: int = None) -> int`: 基于 `psutil.Process` 查询物理常驻内存，完备处理 `NoSuchProcess` 与 `AccessDenied` 异常安全降级返回 0。
   - 实现 `empty_working_set(pid: int = None) -> bool`:
     - 严格配置 64 位 Windows 下的 Win32 API 类型签名 (`wintypes.HANDLE`, `wintypes.BOOL`)，杜绝 ctypes 默认 32 位句柄截断导致的 `ERROR_INVALID_HANDLE` 崩溃。
     - 当前进程优先使用 `GetCurrentProcess()` 伪句柄进行自管工作集修剪（D-07），避免跨进程提权与句柄泄漏。
     - 支持通过 `OpenProcess` 指定远程 PID 修剪（保留用于主控巡检）。
     - 非 Windows 环境或异常时平滑降级返回 `False`（D-08）。
   - 实现 `trim_memory(pid: int = None) -> dict`: 严格按照「`gc.collect()` 垃圾回收 -> `empty_working_set()` 工作集归还」的标准流程执行，并返回前后内存变化统计字典。

2. **资源释放与调度空闲期三部曲闭环 (`module/base/resource.py`)**:
   - 在 `release_resources()` 中接续已有的 OCR 与 Template/Mask 缓存注销，形成「模版/OCR 缓存注销 → `gc.collect()` 垃圾回收 → `empty_working_set()` 工作集修剪」标准闭环（D-06）。
   - 增加修剪效益监控日志：当单次修剪释放物理内存超过 5MB 时输出 info 日志。
   - 确认在 `alas.py` 的调度交接处（`get_next_task`）及各任务队列等待分支（`wait_until`）均无缝复用该三部曲（D-05）。

---

## 验证结论 (Verification Results)
通过脚本 `scratch/verify_04_02.py` 进行全方位验证：
- **修剪能力**: 进程分配 80MB 堆对象并释放后，调用 `empty_working_set()` 返回 `True`，物理内存从 113.44 MB 即刻缩减至 1.24 MB。
- **三部曲闭环**: `trim_memory()` 执行成功，释放内存 50.94 MB。
- **跨平台容错**: 模拟 `sys.platform = 'linux'` 环境，函数无未经处理异常并平滑降级返回 `False`。
- **端到端测试**: 调用 `release_resources()`，日志成功输出：
  `INFO ... Memory trimmed: 86.5MB -> 1.2MB (freed 85.4MB)`
  验证通过。
