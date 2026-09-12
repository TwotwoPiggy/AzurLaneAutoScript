# Plan 04-03 Summary: 多进程调度器子进程 RSS 巡检看门狗、主进程修剪与安全自愈

## 执行概述 (Execution Overview)
- **Phase**: 04-stab-memory
- **Plan**: 03 (Wave 3)
- **需求与决策**: MEM-04 (D-07, D-09, D-10, D-11, D-12)
- **状态**: ✅ 已完成 (Completed)
- **提交信息**: `feat(process): implement subprocess RSS watchdog and safe recycling` (commit `6f08d89a3`)
- **远端推送**: 已成功推送至 `origin/custom` (通过本地代理 `http://127.0.0.1:10808`)

---

## 实施细节 (Implementation Details)

1. **两阶段泄漏判定与 48 小时夜间换茬 (`alas.py`)**:
   - 在 `AzurLaneAutoScript.__init__` 中记录子进程启动时间戳 `process_start_time = time.time()`。
   - 新增 `check_task_boundary_recycle()` 方法并在主调度循环 `loop()` 的任务安全边界（`Scheduler: End task` 之后）调用：
     - **两阶段泄漏判定 (D-09)**: 当物理内存 >600MB 时，首先就地执行 `release_resources()` 与 `trim_memory()` 全量深度修剪；若修剪后仍 >500MB，确认为持久内存泄漏，触发安全换茬退出。
     - **48 小时夜间老化换茬 (D-12)**: 当连续运行时长 >= 48 小时且系统时间处于凌晨空闲窗口（04:00~05:00）时，触发安全换茬退出。
     - **防范 IPC 日志截断竞争 (WARNING-1)**: 输出 `[{self.config_name}] exited. Reason: Safe restart\n` 日志后，显式调用 `time.sleep(0.1)` 确保底层多进程队列完整投递，随后调用 `sys.exit(0)` 安全退出。

2. **看门狗监控线程、主进程自管修剪与自愈热拉起 (`module/webui/process_manager.py`)**:
   - **状态与信号持久化 (WARNING-2)**: 在 `start(self, func, ev)` 中持久化保存 `self.ev`，确保热拉起时原始更新事件与停止信号完整传递。
   - **单例幂等看门狗生命周期**: 实现 `start_watchdog()` 单例防重入启动，并在 `stop()` 中通过 `_watchdog_stop_event` 优雅通知看门狗线程 `join(timeout=1)` 干净退出，防止手动停止时发生误重启。
   - **状态态感知与非阻塞日志排空 (BLOCKER-1 & WARNING-1)**:
     - 实时解析日志消息：识别 `Scheduler: Start task` 进入「任务执行态」（`in_active_task = True`）；识别 `Scheduler: End task`、`Wait until` 及服务器重试进入「调度等待态」（`in_active_task = False`）。
     - 实现 `_drain_renderable_queue()` 非阻塞循环排空队列积压日志，确保退出原因 100% 写入 `renderables`。
   - **主进程自身低频工作集修剪 (BLOCKER-2 & D-07)**:
     - 在看门狗线程中每 30 分钟（且处于调度等待态时）对 WebUI 主进程自身调用 `empty_working_set()`，完成 D-07 主进程自管修剪职责。
   - **活跃任务 180s 僵死保底强杀 (BLOCKER-1 & D-11)**:
     - 僵死超时检测严格仅在活跃任务期间生效；在 `wait_until` 或维护等待期自动挂起，消除误杀死循环。若活跃任务超过 180s 未输出任何日志，判定为死锁强杀并自动热拉起。
   - **无缝自愈热拉起 (D-10)**:
     - 当子进程退出且末尾日志为 `Reason: Safe restart` 时，自动排空队列并于 500ms 内调用 `self.start(...)` 重新拉起子进程。

---

## 验证结论 (Verification Results)
通过测试脚本 `scratch/verify_04_03.py` 进行全闭环验证：
- **两阶段判定**: 模拟 >600MB 并在修剪后回落至 450MB 时不误触发退出；修剪后仍保持 550MB 时成功触发带有 `Reason: Safe restart` 的退出并执行了 `sleep(0.1)` 防截断。
- **48h 老化换茬**: 运行 49h 在 14:00 不换茬，在 04:00 准确定向触发安全换茬。
- **状态感知**: 准确识别任务执行与等待边界，挂起等待期间的 180s 僵死超时。
- **队列排空**: `_drain_renderable_queue()` 机制保障最后一条退出原因完整保留。
- **生命周期**: 看门狗线程幂等启动，在 `stop()` 时 1 秒内安全终止。
- **主进程修剪**: 主进程自身工作集修剪成功，从 75.86MB 物理内存骤降至 1.20MB。
- 测试全部通过，退出码 0。
