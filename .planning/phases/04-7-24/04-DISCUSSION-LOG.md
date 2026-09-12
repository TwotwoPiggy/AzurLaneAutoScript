# Phase 4: 7×24 小时挂机内存守护与防泄漏 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-12
**Phase:** 4-7×24 小时挂机内存守护与防泄漏
**Areas discussed:** 错误截图队列压缩与存储, Win32 工作集修剪与 GC 触发策略, 子进程 RSS 看门狗与安全重启机制

---

## 错误截图队列压缩与存储 (Error Screenshot Compression & Retention)

### 1. JPEG 压缩质量设定
| Option | Description | Selected |
|--------|-------------|----------|
| 采用 JPEG 质量 80 编码 | 单帧约 50~70KB，体积缩减 98%，文字与 UI 细节清晰无损，兼顾性能与排查还原度 | ✓ |
| 采用激进压缩 JPEG 质量 60 | 单帧仅约 30~40KB，最大限度省内存，但细微文字边缘可能有少量伪影 | |
| 动态根据平台性能决定 | 弱机且虚拟内存紧张时自动降至 70，平稳时 80 | |

**User's choice:** 采用 JPEG 质量 80 编码
**Notes:** 确定以 quality=80 兼顾 OCR 文本边缘清晰与 98% 压缩率。

### 2. 回溯容量与硬上限 (Error_ScreenshotLength)
| Option | Description | Selected |
|--------|-------------|----------|
| 默认 60 帧，上限钳制为 100 帧 | 总内存稳定在 3.6MB~6MB，足够回溯报错前 6~10 秒全部操作链 | ✓ |
| 紧凑型默认 30 帧，上限钳制为 50 帧 | 总内存小于 3MB，为极端低配让出最大内存空间 | |
| 维持现有代码的 300 帧上限 | 300 帧约 18MB，保留最大回溯跨度 | |

**User's choice:** 默认 60 帧，上限钳制为 100 帧
**Notes:** 相比旧代码 300 帧 raw ndarray 占用 828MB，压缩后 60~100 帧将内存严格控制在 3.6~6MB。

### 3. 落盘与兼容性策略
| Option | Description | Selected |
|--------|-------------|----------|
| 直接直写 .jpg 文件 + 按需惰性解码 | 报错存盘时直接以二进制流写入 .jpg，零二次编解码 CPU 损耗；历史代码访问提供按需惰性解码保证兼容 | ✓ |
| 存盘时统一先解码为 ndarray | 保持与旧 save_image 管道完全一致，但有解码与二次编码 CPU 损耗 | |

**User's choice:** 直接直写 .jpg 文件 + 按需惰性解码
**Notes:** 避免在出异常时的额外 CPU 消耗，保证落盘迅速，同时保持已有代码接口透明。

### 4. 任务交界队列生命周期
| Option | Description | Selected |
|--------|-------------|----------|
| 保持天然滑动队列（不主动清空） | 60 帧仅占 3.6MB，保留滚动现场对排查进入新任务瞬间或转场时的未识别最有价值 | ✓ |
| 每个新任务开始时主动清空队列 | 确保错误落盘的图片 100% 只属于当前出错的任务 | |

**User's choice:** 保持天然滑动队列（任务交界不主动清空）
**Notes:** 任务交接保留尾部连续性，有利于分析任务切出切入阶段的视觉异常。

---

## Win32 工作集修剪与 GC 触发策略 (Working Set Trimming & GC Cadence)

### 1. EmptyWorkingSet 触发时机
| Option | Description | Selected |
|--------|-------------|----------|
| 任务交接边界 + 调度器长等待空闲期触发 | 完成一轮出击/委托进入下一个任务前，或任务队列进入 wait_until 阶段触发；不干扰连续出击，保证常态低驻留 | ✓ |
| 仅任务队列彻底清空进入深度空闲时触发 | 最保守，但 7x24 循环任务可能长时间不触发修剪 | |
| 每次战役结算离开战斗以及任务交接时均触发 | 较为激进，但出击频繁时会有轻微页面重换入开销 | |

**User's choice:** 在「任务交接边界 + 调度器长等待空闲期」触发
**Notes:** 兼顾出击性能与内存压制，避开核心循环的计算敏感期。

### 2. GC 与 EmptyWorkingSet 协作模式
| Option | Description | Selected |
|--------|-------------|----------|
| 缓存注销 → gc.collect() → EmptyWorkingSet() 三部曲闭环 | 彻底释放死对象后再由系统收回物理页，规整效果最彻底 | ✓ |
| 仅注销缓存并调用 EmptyWorkingSet() | 完全依赖 CPython 自发 GC，避免显式 GC 停顿 | |

**User's choice:** 严格执行「模版/OCR缓存注销 → gc.collect() 循环垃圾回收 → EmptyWorkingSet() 物理页规整」标准三部曲闭环
**Notes:** 彻底断开循环引用并清空代际垃圾，保证工作集能够被操作系统有效缩减。

### 3. 进程修剪主体分配
| Option | Description | Selected |
|--------|-------------|----------|
| 子进程自管修剪 + 主进程独立低频修剪 | 子进程在任务边界使用 GetCurrentProcess() 自行修剪，零跨进程权限问题；主进程后台空闲时独立修剪自身 | ✓ |
| 由主进程集中管控 | 主进程统一持有子进程句柄并统一下发修剪 | |

**User's choice:** 子进程自管修剪 + 主进程独立低频修剪
**Notes:** 去中心化自管降低进程间同步与安全权限复杂性。

### 4. 跨平台封装抽象
| Option | Description | Selected |
|--------|-------------|----------|
| 封装为平台内存抽象工具库 (module/base/memory_utils.py) | Windows 下调用 psapi.EmptyWorkingSet，非 Windows 平滑降级，零侵入、零崩溃风险 | ✓ |
| 在 module/base/resource.py 就地封装 | 代码改动集中，但复用性略低 | |

**User's choice:** 封装为平台内存抽象工具库（如 module/base/memory_utils.py）
**Notes:** 提供一致的对外 API：`empty_working_set()`、`get_process_rss()`、`trim_memory()`。

---

## 子进程 RSS 看门狗与安全重启机制 (Subprocess RSS Watchdog & Safe Recycle)

**User's directive:** 全部由你决定 (Agent Discretion)

### 1. 泄漏警戒阈值设定
- 采用 600MB 基线警戒阈值与两阶段判定法：超过 600MB 时先在任务边界执行一次深度三部曲修剪；若修剪后仍 >500MB，确认存在不可逆的底质碎片，打上 `need_restart` 待重启标签。

### 2. 重启安全时机与窗口
- 优先选择「任务执行完毕、安全返回游戏主界面或进入任务调度队列待机点」执行毫秒级平滑热重启，保证 0 石油损耗与 0 战役评分扣减。
- 设定 180s 僵死保底：若子进程超过 180 秒完全无日志且无截屏，判定为底层 C 扩展死锁或模拟器假死，由看门狗强制终止并拉起新子进程恢复。

### 3. 重启状态衔接与透明度
- 基于 `ProcessManager.restart_processes` 现有链路无缝热重启，任务调度状态自动存盘，启动后立刻接管待办任务。WebUI 仅展示一行看门狗换茬审计日志。

### 4. 48 小时主动老化防御
- 引入低峰期主动换茬机制：连续稳定运行超过 48 小时且处于夜间（凌晨 4:00~5:00）空闲等待期时，主动执行一次安全热重启，彻底铲除长周期积累的 CPython 底层碎片。

---

## Agent's Discretion (裁量权落实)
- 用户在 Area 3（子进程 RSS 看门狗）明确指示全部由构建者决定，阈值设定（600MB/500MB）、任务边界安全点热重启、180s 僵死保底及 48h 夜间主动换茬均已作为核心工程决策固化。

## Deferred Ideas
- None — 本次讨论严密锁定在 Phase 4 内存守护与防泄漏范畴。
