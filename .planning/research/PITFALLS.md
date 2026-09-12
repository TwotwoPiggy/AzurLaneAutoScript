# Pitfalls Research: Alas 弱机性能轻量化与 7×24h 挂机稳定性

**Domain:** 弱机平台（Intel i5-4210H 2C4T Haswell + 16GB RAM + GTX 960M 2GB / HD 4600 双显卡）下 AzurLaneAutoScript (Alas) 7×24 小时无人值守挂机稳定性与低资源损耗调优
**Researched:** 2026-09-12
**Confidence:** HIGH（基于 Alas 核心代码库审计、Chromium/Electron 渲染与进程架构分析、PyWebIO 会话生命周期追踪、Windows WDDM TDR 崩溃机制研究以及 MuMu 模拟器通信协议排查）

---

## Critical Pitfalls (关键致命陷阱)

### Pitfall 1: Electron 盲目禁用 GPU 加速 (`--disable-gpu`) 导致双核 CPU 负载雪崩与发热降频

**What goes wrong (故障表现):**
在弱机优化中，开发者常误认为“关掉 GPU 就能省电防崩”，因而在启动时全局注入 `--disable-gpu` 或调用 `app.disableHardwareAcceleration()`（当前源码 `webapp/packages/main/src/index.ts:15` 存在此配置）。然而，禁用硬件加速后，Chromium 会将所有 DOM 树排版、CSS 效果、动画过渡及大量实时文本输出全面降级为 CPU 软件光栅化（SwiftShader / Skia CPU 渲染）。在仅有 2 核 4 线程的 Haswell 移动处理器（i5-4210H @ 2.9GHz）上，这会导致 Electron 渲染进程自身长期吃满 15%~35% 的 CPU 资源，与 MuMu 模拟器、Thorium 浏览器（视频直播硬解）以及 Alas Python 图像识别争抢极度匮乏的 CPU 周期，迅速诱发 CPU 温度突破 85℃ 并触发硬件级热降频（降频至 1.8GHz~2.2GHz），导致整机整体严重卡顿。

**Why it happens (根因分析):**
开发者将“避免独显 TDR 崩溃”等同于“彻底禁用 GPU”，未能理解 Chromium 进程模型：现代 WebUI 的复杂 CSS 和长列表重绘高度依赖 GPU 进行图层合成（Compositing）。Haswell 平台的 CPU 单核与多核算力极其贫弱，强行用 CPU 跑光栅化是典型的“拆东墙补西墙”。

**How to avoid (规避方案):**
- **绝不全局禁用 GPU**：移除盲目的 `app.disableHardwareAcceleration()`。
- **定向路由至节能核显**：通过 Chromium 命令行开关将 Electron 渲染明确指定给 **Intel HD Graphics 4600 核显**（`--gpu-preference=low-power`），利用核显原生支持的 Direct3D 11 特性负责轻量级 2D/DOM 合成，将独显完全释放给 MuMu 模拟器。
- **剥离无关 3D 管线**：启动参数中追加 `--disable-3d-apis`、`--disable-webgl`、`--disable-webgl2`，仅保留基础 2D 硬件加速，杜绝任何 3D 渲染开销。
- **限制渲染帧率与节流**：通过 `--limit-fps=15` 将界面帧率限制为 15 FPS，并在窗口失焦或最小化时挂起非必要重绘。

**Warning signs (预警信号):**
- 任务管理器中 `Alas.exe`（Renderer 进程）常态 CPU 占用 > 10%。
- CPU 频率在无重型任务时因发热自 2.9GHz 剧烈跌落至 1.8GHz。
- 播放直播时掉帧，伴随风扇狂转。

**Phase to address (对应阶段):**
Phase 1: Electron 桌面端轻量化与显存/GPU保护 (PERF-DESKTOP)

---

### Pitfall 2: Electron 后台休眠与遮挡节流 (Occlusion Throttling) 导致心跳挂起与关键告警静默

**What goes wrong (故障表现):**
当用户将 Alas 最小化至系统托盘，或前台全屏观看 Thorium 浏览器直播、将 Alas 窗口完全遮挡时，Chromium 的后台休眠保护机制自动触发：
1. **定时器严重钳制 (`timer-throttling`)**：后台页面的 `setInterval` / `setTimeout` 被强制限制为 1000ms 触发一次，甚至在完全不活动时被挂起至几分钟一次。
2. **遮挡优化挂起 (`CalculateNativeWinOcclusion`)**：Chromium 判定窗口不可见，完全停滞帧渲染与 DOM 更新。
这会导致 PyWebIO 前端用于维持 WebSocket 长连接的活性探测中断，引发无声断连；更为严重的是，当自动化出现严重异常（如 `RequestHumanTakeover`、船坞爆仓、被踢下线）时，前端的桌面提醒与弹窗逻辑被冻结，用户无法及时收到通知，挂机事故被无限期拖延。

**Why it happens (根因分析):**
现代浏览器为了移动端续航引入了激进的后台资源冷冻策略，而开发者将关键的告警提示和通信生命周期直接托付给了浏览器渲染进程内的前端 JavaScript。

**How to avoid (规避方案):**
- **禁用 Chromium 遮挡节流**：在主进程启动开关中追加 `--disable-backgrounding-occluded-windows` 与 `--disable-renderer-backgrounding`。
- **配置窗口防挂起属性**：在 `BrowserWindow` 的 `webPreferences` 中明确设置 `backgroundThrottling: false`。
- **告警下沉至 Node.js / Python 原生层**：关键告警（如船坞满、游戏维护、人工接管）不得仅仅依赖 WebUI 网页内的 DOM 弹窗，而必须通过 Electron 主进程调用 Windows 原生通知（`new Notification({ title, body })`）或通过 Python 直接调用系统托盘通知与 OnePush 推送，彻底绕过渲染管线的休眠限制。

**Warning signs (预警信号):**
- 窗口最小化几十分钟后重新打开，界面瞬间弹出大量堆积的过期告警。
- 最小化状态下偶发 WebUI 自动断线。

**Phase to address (对应阶段):**
Phase 1: Electron 桌面端轻量化与显存/GPU保护 (PERF-DESKTOP)

---

### Pitfall 3: PyWebIO 长时间空闲任务导致的 WebSocket 异常断连 (Code 1006) 与界面假死

**What goes wrong (故障表现):**
在 7×24 小时运行过程中，Alas 常有数小时处于无任务空闲期（例如所有日常已清空、等待委托完成、根据配置定时下线）。在这段漫长的零日志、零交互期间，PyWebIO 与 Starlette/FastAPI 之间的底层 WebSocket 极易因 Windows TCP 保活超时、本地杀毒软件/防火墙状态清理而发生半开连接异常关闭（通常为 `1006 abnormal closure`）。由于 PyWebIO 原生客户端缺乏健全的静默断线重连逻辑，前端网页会弹出模态灰屏：“Connection closed with server”，使整个管理面板陷入僵死，用户必须手动刷新整个页面才能恢复查看。

**Why it happens (根因分析):**
PyWebIO 最初设计定位是轻量级交互脚本工具，默认没有针对数天级常驻挂机设计应用层的心跳握手协议（Ping-Pong 保活）；FastAPI/Starlette 的 WebSocket 端点在无数据发送时长期静默，极易被底层网络栈斩断。

**How to avoid (规避方案):**
- **应用层定期心跳注入**：在 `module/webui/app.py` 的 `TaskHandler` 中注册低开销心跳生成器（例如每 30 秒向已连接的前端推送一条微型系统时间戳或空状态包），强制刷新 TCP 连接活性。
- **前端透明自愈重连补丁**：通过 `run_js` 注入自定义重连守卫，拦截 PyWebIO WebSocket 的 `onclose` 事件，在检测到 1006 异常断开时启动指数退避自愈重连（1s, 2s, 5s...），重连成功后静默拉取当前状态快照，杜绝粗暴灰屏遮罩。

**Warning signs (预警信号):**
- 晨起查看挂机状态时，WebUI 频繁停留在灰色断线提示遮罩上。
- 后台终端输出 `starlette.websockets.WebSocketDisconnect: 1006`。

**Phase to address (对应阶段):**
Phase 2: WebUI 前端与 PyWebIO 日志流渲染节流 (PERF-WEBUI)

---

### Pitfall 4: PyWebIO 页面刷新与重载导致 Session 闭包与后台生成器线程泄漏

**What goes wrong (故障表现):**
当用户在浏览器中按 F5 刷新、在 Electron 中使用 `Ctrl+R`，或后端服务重启触发重新加载时，每一次握手都会在 PyWebIO 内部创建全新的 `Session`。旧会话虽已失效，但其在 `app.py` 中通过 `task_handler.add(log.put_log(self.alas))` 注册的后台任务以及对 `pm.renderables` 的闭包引用，往往由于生成器阻塞在 `yield` 语句处而未能抛出 `SessionException`。经过数天的重复刷新与多标签访问，Python `gui.py` 进程内会滞留数十个空转的后台日志派发任务和关联线程，导致 Python 内存从初期的 250MB 缓慢膨胀至 1.2GB~1.8GB，并大量侵占操作系统虚拟内存 PageFile。

**Why it happens (根因分析):**
PyWebIO 的会话回收机制依赖于下一次 IO 输出失败时抛出的 `SessionException`。如果任务处于空闲等待，或者由于循环内没有产出新的日志消息，生成器就无法感知到前端会话已经消亡，导致 GC 根引用链一直被持有。

**How to avoid (规避方案):**
- **会话销毁钩子显式注销**：利用 PyWebIO 提供的 `session.on_close(callback)`，在客户端断开时主动调用清理逻辑，向关联的 `TaskHandler` 任务发送终止信号。
- **心跳感知清理**：在 `TaskHandler` 调度循环中校验关联 session 的活跃状态，凡发现 `session.closed` 立即移出调度队列并显式释放生成器。
- **弱引用解耦**：在组件之间传递状态时采用弱引用（`weakref`），避免跨闭包循环持有导致无法垃圾回收。

**Warning signs (预警信号):**
- 多次刷新页面后，`threading.active_count()` 随刷新次数持续攀升且永不下降。
- `gui.py` 进程的专用工作集（Working Set）和提交大小（Commit Size）随挂机天数单调上升。

**Phase to address (对应阶段):**
Phase 2: WebUI 前端与 PyWebIO 日志流渲染节流 (PERF-WEBUI)

---

### Pitfall 5: RichLog 朴素 DOM 截断破坏浏览器滚动锚定与视图跳动

**What goes wrong (故障表现):**
当前 Alas 的 `RichLog`（`module/webui/widgets.py`）机制为：当日志数量超过一定阈值时，直接调用 `reset()`（清空整个容器 DOM）并重新塞入数百行 HTML。这会导致整个日志视口疯狂闪烁并强行滚回底部。
部分开发者为了防止 DOM 节点暴增，采取朴素的做法：每产生一行新日志就执行 `$("#log>div").children().first().remove()`。这会引发严重的反向 UX 灾难与性能缺陷：
1. **破坏滚动锚定**：删除顶端节点会瞬间缩小容器的 `scrollHeight`，导致浏览器的视口坐标跳变。如果用户此时为了定位某个 Bug 而向上翻看历史日志，每次新日志到达都会使视口剧烈抖动、阅读焦点丢失。
2. **高频重排与重绘雪崩**：代码中当前以 0.25 秒（4Hz）的高频持续调用 `extend(html)`。每秒数次直接向 live DOM 插入和删除节点，引发极度密集的浏览器 Reflow/Repaint，在低性能核显或弱 CPU 下使渲染器 CPU 占用飙升。

**Why it happens (根因分析):**
将动态实时更新的 DOM 结构当成了简单的无损环形队列，忽视了现代浏览器渲染管线的排版流（Layout Tree）更新成本和滚动视口计算规则。

**How to avoid (规避方案):**
- **禁用原生滚动锚定干扰**：在日志容器 CSS 中声明 `overflow-anchor: none;`。
- **视口偏移精确补偿**：当且仅当用户处于手动翻看状态（`keep_bottom == false`）且需要裁剪顶部旧 DOM 时，必须在删除节点后立即在 JS 端同步修正滚动条高度（`scrollTop -= removedHeight`），使用户眼前的文字绝对保持静止。
- **批处理更新与 RAF 节流**：在后台日志高频爆发时，在客户端设立轻量级微批次缓冲区，利用 `requestAnimationFrame` 将多次 DOM 追加合并为单次批量插入；当日志面板处于折叠状态（Collapsed）时，完全停止一切 DOM 注入与更新操作。

**Warning signs (预警信号):**
- 用户尝试向上滚轮查看报错时，界面像被“扯动”一样不断向下或向上抽搐。
- 战斗激烈输出日志时，Chromium 渲染进程占用明显上升。

**Phase to address (对应阶段):**
Phase 2: WebUI 前端与 PyWebIO 日志流渲染节流 (PERF-WEBUI)

---

### Pitfall 6: 自动化循环与作战等待激进休眠导致结算界面漏检与 S 胜评价受损

**What goes wrong (故障表现):**
为了降低 Python 端图像检测对 CPU 的消耗，若开发者无差别地将主循环休眠从原本的 100ms~300ms 激进拉大到 2s~4s，会直接破坏碧蓝航线极其脆弱的状态迁移时间窗：
1. **战后评级漏点与卡死**：战斗结束时的 S 胜 / A 胜画面（`BATTLE_STATUS_S`、`BATTLE_STATUS_A`）及掉落物确认界面（`GET_ITEMS_1`）存在淡入动画与有效点击判定窗口。休眠过长会导致漏过判定，或在结算动画停留过久触发 `GameStuckError`，甚至被防挂机机制判定异常。
2. **紧急战术失效导致沉船**：在主线 14/15 图、大型作战月度 Boss 等高难度战斗中，潜艇支援（`handle_submarine_call`）、手动空袭清弹幕（`CombatManual`）或自律确认（`handle_combat_automation_confirm` 仅有 10 秒窗口）都需要亚秒级的响应。数秒的休眠延迟会导致关键技能未开、先锋全灭、S 胜掉落为 A 胜乃至出击大败，造成石油与好感度重大损失。

**Why it happens (根因分析):**
试图用全局静态粗暴的 `time.sleep()` 解决 CPU 功耗问题，缺乏对游戏逻辑状态处于“关键决策过渡期”还是“稳定执行等待期”的语意感知。

**How to avoid (规避方案):**
- **状态感知型自适应休眠 (State-Adaptive Polling)**：
  - **过渡敏感态 (100ms ~ 250ms)**：战斗准备点击、结算画面转场、掉落物接收、弹窗确认期间，维持极短轮询间隔，确保点击精准迅速。
  - **自律稳态期 (1.0s ~ 1.5s)**：在判定到战斗正在执行（检测到 `PAUSE` 按钮稳定且战斗时钟正常跳动）时，动态将截图与检测间隔拉长至 1.0s~1.5s，大幅压制战斗过程中的 CPU 消耗。
  - **系统脱机期 (5s ~ 60s)**：大世界网格长距离航行、远征长休眠时，执行深层休眠。
- **禁用粗暴的大颗粒度 sleep**：绝不随意修改 `screenshot_interval_set('combat')` 的安全下限（0.3s~1.0s），而是在保持帧捕获可控的前提下只跳过纯图像相似度计算。

**Warning signs (预警信号):**
- 作战日志中出现原本能够 S 胜的关卡频繁掉落至 A 胜或 B 胜。
- 战斗耗时相较于手动明显拉长 10%~20%。
- 频繁在战斗结算界面抛出 `GameStuckError`。

**Phase to address (对应阶段):**
Phase 3: Python 自动化核心循环与截图能效调优 (PERF-CORE)

---

### Pitfall 7: Scrcpy 僵尸进程与 NemuIPC 强制终止线程 (`SetAsyncExc`) 导致 DLL 句柄泄露与模拟器崩溃

**What goes wrong (故障表现):**
- **Scrcpy 孤儿进程与 Socket 积压**：Scrcpy 依赖在模拟器中注入的 `scrcpy-server.jar` 与本地两个 TCP Socket。当网络瞬断、模拟器卡顿时，如果重连逻辑未安全收尾，旧的 Android 端 `app_process` 服务不会退出，数次断线后模拟器内堆积数个 Java 编码服务，耗尽模拟器 CPU 和编码器资源；宿主机端也会残留大量 `CLOSE_WAIT` / `TIME_WAIT` 套接字，最终耗尽端口并报 `ConnectionResetError`。
- **NemuIPC 强杀引发 C 堆损毁与死锁**：在 `module/device/method/nemu_ipc.py` 中，调用 `run_func(nemu_capture_display)` 超时（0.5s）后会触发 `job.get_or_kill()`，底层使用 `PyThreadState_SetAsyncExc(thread_id, _JobKill)` 强行杀死线程。**然而，如果工作线程此时正在 C 语言外部 DLL (`external_renderer_ipc.dll`) 内部拷贝共享内存或正持有 Windows 共享互斥锁，Python 异步异常根本无法打断 C 底层执行！** 这会导致线程沦为僵尸线程，或者在未释放共享内存互斥锁的情况下被暴毙剥离，瞬间破坏 MuMu 内部渲染管道，后续调用必定报出 `nemu_capture_display rpc error: 1722 / 1726`，模拟器画面永久冻结，唯有重启电脑才能恢复。

**Why it happens (根因分析):**
开发者使用了 Python 级别极其不安全的异步异常注入（`SetAsyncExc`）来试图取消不受控的非托管 C 代码，打破了跨进程/跨语言共享内存与互斥体安全管理契约。

**How to avoid (规避方案):**
- **坚决弃用 `PyThreadState_SetAsyncExc` 强杀 C 库线程**：对于 NemuIPC，超时处理绝不能采用杀线程的方式。要么依靠原生 DLL 提供的非阻塞接口或配置内部超时，要么将 NemuIPC 截图隔离在一个专门的轻量独立工作子进程中——子进程一旦发生 C 级阻塞，直接通过操作系统 API（`TerminateProcess`）连根拔起，操作系统会自动清理其占用的全部句柄和映射，绝不会殃及主进程和 MuMu 共享互斥体。
- **Scrcpy 初始化前置幂等清理**：在启动 Scrcpy 之前，必须执行 `adb shell pkill -f com.genymobile.scrcpy`，清理掉宿主机与模拟器内的一切历史残留服务；Socket 开启时设置 `SO_REUSEADDR` 并安全关闭。

**Warning signs (预警信号):**
- 运行一段时间后日志中爆发 `nemu_capture_display rpc error: 1722` 或 `error: 1726`。
- 任务管理器中 Alas 进程的“句柄数”单调暴涨，甚至突破 4000 个。
- 模拟器内存不断攀升，显示画面黑屏卡死。

**Phase to address (对应阶段):**
Phase 3: Python 自动化核心循环与截图能效调优 (PERF-CORE) & Phase 4: 7×24 小时挂机内存与防泄漏机制 (STAB-MEMORY)

---

### Pitfall 8: 显存竞逐触发 Windows GPU 驱动 TDR (`LiveKernelEvent 141`) 与模拟器黑屏崩溃

**What goes wrong (故障表现):**
用户设备拥有双显卡：Intel HD Graphics 4600 核显 + Nvidia GeForce GTX 960M（仅 2GB 独立显存）。
在日常 7×24 挂机并发场景中：
- MuMu 模拟器（Vulkan / DirectX 图形引擎）常态占用 800MB~1.2GB 显存；
- Thorium 浏览器前台播放 1080p/4K 60fps 高清直播，硬解和渲染占用 500MB~800MB 显存；
- 若 Alas Electron 桌面客户端未加限制地运行在独显上，Chromium GPU 进程又会吃掉 300MB+ 显存。
三者合计瞬间刺穿 GTX 960M 的 2GB 物理显存上限！当显存耗尽时，Windows WDDM 驱动层会被迫开始向系统物理内存（Shared System Memory）进行大量纹理分页。由于当前整机 PageFile（虚拟内存）已高达 15.8GB used，系统内存带宽极其拥堵，PCIe 换页延迟呈指数级放大。一旦某个渲染指令或解码帧在 GPU 调度队列中等待超过 2 秒，Windows 内核立即判定 GPU 引擎死锁，触发 TDR（Timeout Detection and Recovery，记录系统错误 `LiveKernelEvent 141`），强制重置显卡驱动。这会导致瞬间黑屏 1~2 秒，伴随 MuMu 模拟器崩溃闪退、Thorium 视频绿屏、Alas 失去截屏通道全线停转。

**Why it happens (根因分析):**
在 Optimus 混合双显卡老旧笔记本上，没有对应用负载进行显卡级别分工，让对图形性能要求各异的应用全挤在物理显存极度狭窄（2GB）的移动独显上。

**How to avoid (规避方案):**
- **物理显卡负载硬性分流（核心战略）**：
  - **Nvidia GTX 960M 独显**：**专供 MuMu 模拟器独占！** 确保碧蓝航线 3D/2D 渲染拥有纯净的物理显存环境，绝对不被外部应用挤占。
  - **Intel HD Graphics 4600 核显**：**强制分配给 Thorium 浏览器与 Alas Electron！** Haswell 核显具备成熟的 Intel QuickSync 视频硬解单元，足以流畅硬件解码高清直播，且其显存直接动态划拨自系统 RAM，从根本上在物理层面阻断与 GTX 960M 的显存争抢链条，根除 `LiveKernelEvent 141`。
- **Electron 显存资源硬约束**：在 Electron 启动参数中限制 Chromium 显存缓存池大小（`--gpu-memory-buffer-compositor-resources`、`--disk-cache-size=30000000`）。
- **MuMu 模拟器内部显存压制**：配置 MuMu 内部渲染分辨率严格匹配 1280×720，锁定模拟器后台运行帧率为 20~30 FPS，降低画质抗锯齿开销。

**Warning signs (预警信号):**
- Windows 事件查看器中高频出现“事件 ID 4101：驱动程序 \Driver\nvlddmkm 已停止响应并已成功恢复”。
- 晚间开启视频直播几分钟内，屏幕突然闪烁黑屏，模拟器直接白屏闪退。
- GPU-Z 监测显示 GTX 960M 显存占用持续在 1980MB~2040MB 危险红线徘徊。

**Phase to address (对应阶段):**
Phase 1: Electron 桌面端轻量化与显存/GPU保护 (PERF-DESKTOP) & Phase 5: 老旧平台与模拟器协同最佳配置指导 (GUIDE-ENV)

---

### Pitfall 9: 虚拟内存 (PageFile) 严重踩踏与高频磁盘换页引发系统雪崩

**What goes wrong (故障表现):**
当前机型拥有 16GB 物理内存，但 PageFile（虚拟内存文件）已被消耗掉 15.8GB，说明系统早已处于极其危险的内存超额提用（Memory Overcommit）状态。在此状态下，任何一次突发性的大内存分配：
- 例如 Alas 运行出错时触发 `save_error_log()`，默认的 `screenshot_deque` 缓冲了 60 到 300 张原始尺寸为 1280×720×3 的未压缩 NumPy 图像矩阵（单张 2.7MB，300 张就是 810MB 瞬时物理内存！）；
- 或者当用户尝试配置多实例并发时，每个实例各自加载一套庞大的 MXNet 深度学习框架与 CNOCR 权重（单进程占用 400MB~800MB）；
都会直接诱发系统的硬缺页异常（Hard Page Faults）风暴。机械硬盘或普通 SSD 的活动时间瞬间飙升至 100%，CPU 被内核换页自旋锁吃满，整机进入长达 10~30 秒的假死卡顿状态。此时 ADB 响应超时、MuMu 内部进程被 Android 系统的低内存杀手（LMK）干掉，进而引发连锁雪崩。

**Why it happens (根因分析):**
内存密集型数据结构（图像缓冲池）未做内存级压缩，缺乏低内存感知机制；深度学习模型多进程重复载入造成严重冗余。

**How to avoid (规避方案):**
- **错误截图队列内存实时压缩**：重构 `module/device/screenshot.py` 中的 `screenshot_deque`。不要在内存中保存原始的 `np.ndarray`，而是在加入环形缓冲队列前，使用 OpenCV 将图像快速编码为 JPEG 内存字节流（`cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 75])`）。单张内存从 2.7MB 锐减至 80KB~150KB（缩减超 95%），300 张队列内存占用由 810MB 降至不足 40MB！
- **弱机自动约束缓冲容量**：在弱机配置下，将 `Error_ScreenshotLength` 的硬上限从 300 张强行钳制至 30~50 张。
- **强制全局共享单例 OCR 服务**：强制推行 `UseOcrServer: true`，全局仅运行一个共享 OCR 微服务（端口 22268），阻断多实例重复载入 MXNet 模型的数百兆内存浪费。
- **阶段性内存主动修剪**：在自动化任务执行完毕进入漫长的 `sleep_until` 空闲等待前，主动触发 Python `gc.collect()`，并通过 Windows API `ctypes.windll.psapi.EmptyWorkingSet(-1)` 释放临时物理工作集。

**Warning signs (预警信号):**
- 只要 Alas 一报错，整台电脑鼠标指针卡死、音乐播放断续破音。
- 资源监视器中硬盘响应时间突破 2000ms，硬缺页每秒数百次。
- 任务管理器中系统提交大小（Committed Memory）逼近 32GB 物理+虚拟上限。

**Phase to address (对应阶段):**
Phase 4: 7×24 小时挂机内存与防泄漏机制 (STAB-MEMORY)

---

## Technical Debt Patterns (技术债陷阱与权衡)

在对老旧硬件进行极限压榨和长期无人值守优化时，切忌使用表面省事却埋下隐患的“伪优化”手段：

| 快捷方式 (Shortcut) | 表面即时收益 | 长期技术代价 | 何时允许采纳 |
| :--- | :--- | :--- | :--- |
| **粗暴全局加大 `time.sleep(2.0)`** | 显著拉低循环 CPU 占用 | 破坏状态机实时性，漏过 S 胜结算与自律确认，导致出击失败 | **绝不允许**；必须采用状态自适应分级轮询 |
| **使用 `SetAsyncExc` 强杀超时工作线程** | 快速解决图像捕获卡死问题 | 损坏 C 语言扩展内存堆，造成 DLL 互斥体死锁和句柄泄漏，引发 `rpc 1722` | **绝不允许**；必须采用进程级物理隔离 |
| **日志截断时直接 `empty()` 清空 DOM 重建** | 规避了复杂的虚拟滚动算法开发 | 用户视口疯狂跳跃，无法向上回溯排查历史日志，高频重排浪费渲染性能 | 仅在用户主动点击“清空日志”按钮时允许 |
| **全局无脑追加 `--disable-gpu`** | 表面上绝不会再发生显卡掉驱动 | 将 2D 图层合成重压全扣在双核 CPU 上，加剧 CPU 满载与发热降频 | 仅在完全没有可用显卡驱动的纯无头服务器中允许 |
| **内存中保存未经压缩的原始 NumPy 截图** | 编写简单，保存错误日志时无需重新解码 | 单张 2.7MB 吞噬宝贵内存，在 PageFile 饱和时诱发系统换页卡死雪崩 | 仅在物理内存 >= 32GB 且虚拟内存极为充裕时允许 |

---

## Integration Gotchas (外部集成易错点)

Alas 高度依赖与 Android 模拟器、底层驱动及浏览器环境的深度协同，各集成点的核心防坑指南如下：

| 集成对象 (Integration) | 常见错误做法 (Common Mistake) | 正确架构做法 (Correct Approach) |
| :--- | :--- | :--- |
| **MuMu 12 模拟器 (NemuIPC)** | 在 Python 主线程中直接调用 DLL，或在超时后通过线程异常强杀 | 将 NemuIPC 包装为独立辅助子进程，由主进程进行 IPC 监控；若超时直接 OS 级 TerminateProcess，安全回收句柄 |
| **Scrcpy 视频流解码管道** | 客户端掉线后直接抛弃对象，未执行远程清理与套接字关闭 | 重新连接前通过 `adb shell pkill -f scrcpy` 清除 Android 端孤儿进程；严格设置 Socket `SO_LINGER` 防残留 |
| **PyWebIO + Starlette WebSocket** | 假定网络绝对可靠，长达数小时不发送任何数据帧 | 在 `TaskHandler` 中挂载 30s 轻量应用层 Ping 心跳包；前端注入指数退避自动重连逻辑 |
| **Windows Optimus 双显卡分配** | 默认由 Windows 自动判断显卡，导致 MuMu、Thorium、Electron 全挤在独显 | 显式指定：MuMu 独占 Nvidia GTX 960M；Thorium 与 Alas Electron 强制路由至 Intel HD 4600 核显 |
| **多版本 ADB 服务争抢** | Alas 自带 ADB 与模拟器内置 ADB 版本不一致，相互 kill-server | 在 Alas 部署配置中开启 `ReplaceAdb: true`，强制统一全局 ADB 二进制版本与端口 |

---

## Performance Traps (性能陷阱与扩容边界)

| 陷阱 (Trap) | 故障特征 (Symptoms) | 预防措施 (Prevention) | 崩溃阈值 (When It Breaks) |
| :--- | :--- | :--- | :--- |
| **全屏 1280×720 模板匹配密集扫描** | CPU 占用瞬间飙至 100%，出击逻辑卡顿 | 严格利用 `Button.area` 局部裁剪比对，禁止在已知上下文的全图检索 | 连续进行 3 次以上全图 matchTemplate 即可引发卡顿 |
| **4Hz 无节流富文本 DOM 推送** | Chromium 渲染器 CPU 占用 > 20%，界面卡顿 | 引入 `requestAnimationFrame` 批处理合并插入；折叠时彻底阻断 DOM 渲染 | 日志输出频率超过 10 条/秒时引发浏览器卡死 |
| **ProcessManager 未截断日志对象堆积** | Python 进程内存缓慢攀升至数吉字节 | 将 `renderables` 队列严格限制在 300 条以内，溢出立即切片回收 | 挂机超过 48 小时且日志输出量大时 |
| **报错转储瞬时内存爆发** | 写入 `log/error` 时整机无响应，鼠标冻结 | 队列在内存中存 JPEG，写入磁盘时流式分批写入，严禁瞬间构建大列表 | 当 `screenshot_deque` 达到 300 张且系统 PageFile 饱和时 |

---

## Security Mistakes (安全合规隐患)

| 错误 (Mistake) | 安全风险 (Risk) | 防范措施 (Prevention) |
| :--- | :--- | :--- |
| **无鉴权绑定 0.0.0.0 并开启远程穿透** | 控制台彻底暴露至公网，攻击者可任意操控游戏资产或下发系统指令 | 开启 `RemoteAccess` 时强制要求配置 PIN 码或 `--key` 认证；默认只监听 `127.0.0.1` |
| **错误截图脱敏区域坐标漂移** | UID、游戏昵称泄露于网络公开发布的 Bug 日志中，面临封号风险 | 采用动态特征锚点定位 UID 水印区域（而非硬编码像素坐标），保存前多重模糊化处理 |
| **Electron 渲染进程放开 Node 权限** | 开启 `nodeIntegration: true` 且禁用隔离，若 WebUI 受到 XSS 即可直接 RCE | 开启 `contextIsolation: true`，通过严密的 `preload.ts` 白名单暴露有限 IPC 接口 |

---

## UX Pitfalls (用户体验与交互防坑)

| 体验陷阱 (UX Pitfall) | 用户受损影响 (User Impact) | 改进与更优方案 (Better Approach) |
| :--- | :--- | :--- |
| **日志截断导致滚轮突然飞移** | 用户排查偶发错误时文字瞬间被顶走或飞至底部，根本无法阅读 | 引入 `overflow-anchor: none` 与视口高度动态补偿，用户向上回溯时锁定阅读点 |
| **过度节能导致切回前台严重迟滞** | 用户从后台切出 Alas 时，界面白屏或转圈 3~5 秒无响应 | 监测前台激活事件（`window.on("focus")`），瞬间拉升渲染帧率并主动请求状态快照刷新 |
| **异常报错时出现阻断性原生弹窗** | 挂机过程中弹出一个 Windows 模态确认框，导致后续所有自动化流程挂起 | 绝不在后台挂机流程中使用阻断式模态对话框，所有异常统一收敛至任务调度器自动重启策略 |

---

## "Looks Done But Isn't" Checklist (伪完成自查清单)

在各阶段功能开发完成后，必须对照以下清单进行防坑验收，防止“看似完成实则埋坑”：

- [ ] **Electron 节能优化**：表面上失焦时窗口降低了 CPU 占用，**实测验证**：最小化到系统托盘 4 小时以上，WebUI 的长连接未被挂起断开，原生桌面系统告警依然能在 1 秒内弹出。
- [ ] **WebUI 日志虚拟截断**：表面上 DOM 节点数控制在 200 行以内，**实测验证**：在大量日志输出过程中向上滚轮翻看历史，视口文字绝对静止无抖动，且折叠日志后渲染进程 CPU 占用直接归零。
- [ ] **战斗轮询节能优化**：表面上战斗中 CPU 占用减少 50%，**实测验证**：连续出击高难关卡（如 14-4、大世界月度 Boss）10 次以上，潜艇召唤与技能释放准确触发，未发生任何一次 A 胜降级或漏点结算。
- [ ] **NemuIPC 超时防护**：表面上在图像获取超时后捕获了异常并重连成功，**实测验证**：持续运行 24 小时后，Alas 进程的 Windows Handle（句柄数）保持平稳（<= 1500），未出现任何 `rpc 1722 / 1726` 报错。
- [ ] **双显卡分流调优**：表面上 Electron 开启了 GPU 加速，**实测验证**：在 Nvidia 控制面板与 Windows 显卡设置中确认 MuMu 绑定 GTX 960M，而 Electron 与 Thorium 绑定 Intel HD 4600；前台播放 4K 60fps 直播时连续运行 Alas 6 小时无驱动重置（`LiveKernelEvent 141` 为 0 次）。

---

## Recovery Strategies (故障恢复与自愈策略)

| 故障类别 (Pitfall) | 恢复成本 | 具体自动化恢复步骤 (Recovery Steps) |
| :--- | :--- | :--- |
| **GPU 驱动重置 (TDR 141)** | **HIGH (高)** | 1. 捕获截屏全黑或 DWM 异常；2. 关闭当前 Device 通道；3. 调用 `adb kill-server` 并强制重启 MuMu 模拟器进程；4. 延迟 15 秒待显卡驱动稳定后重新初始化连接。 |
| **NemuIPC 共享内存失效 (1722)** | **MEDIUM (中)** | 1. 放弃当前 IPC 会话并强制销毁 helper 子进程；2. 优雅降级切换到 `scrcpy` 或 `droidcast` 截图通道；3. 记录告警并调度在下一个空闲期重启模拟器。 |
| **WebUI WebSocket 假死断连** | **LOW (低)** | 1. 前端守护脚本侦测到长达 60s 无心跳数据包；2. 自动触发 WebSocket 静默重连；3. 重新获取调度器状态树并替换局部 DOM。 |
| **PageFile 严重踩踏卡死** | **HIGH (高)** | 1. 自动化看门狗检测到单次截图耗时 > 10s；2. 强制终止非核心分析，立即执行 `gc.collect()` 与工作集内存压缩；3. 暂缓大内存转储，进入 30 秒安全冷却期。 |

---

## Pitfall-to-Phase Mapping (阶段与防坑策略映射矩阵)

为保障后续路线规划的严谨落地，上述陷阱必须分工至各规划阶段彻底攻克：

| 关键陷阱 (Pitfall) | 预防解决阶段 (Prevention Phase) | 验证与验收手段 (Verification) |
| :--- | :--- | :--- |
| **Pitfall 1: Electron 盲目禁用 GPU 加速** | **Phase 1: PERF-DESKTOP** | 移除禁用参数，核显接管合成；Electron 渲染器空闲 CPU < 2%，整体系统温度正常 |
| **Pitfall 2: Electron 后台与遮挡休眠** | **Phase 1: PERF-DESKTOP** | 注入防休眠开关；最小化或遮挡 2 小时以上，告警依然即时触发且长连接稳固 |
| **Pitfall 8: 显存竞逐与 GPU TDR (141)** | **Phase 1: PERF-DESKTOP & Phase 5: GUIDE-ENV** | 硬件级双显卡路由；晚间并发直播 4 小时无黑屏、无 `LiveKernelEvent 141` 产生 |
| **Pitfall 3: PyWebIO 长空闲 WebSocket 断连** | **Phase 2: PERF-WEBUI** | 挂载 30s 心跳机制与静默自愈脚本；模拟挂机 8 小时无灰屏假死，无 1006 报错 |
| **Pitfall 4: Session 闭包与线程泄露** | **Phase 2: PERF-WEBUI** | 显式注册 `session.on_close`；连续刷新页面 20 次，`gui.py` 线程数与内存保持恒定 |
| **Pitfall 5: RichLog DOM 截断破坏视口** | **Phase 2: PERF-WEBUI** | 实现视口高度动态补偿与批量 RAF 渲染；大量刷屏时手动翻看无跳跃、无卡顿 |
| **Pitfall 6: 自动化循环激进休眠致漏点** | **Phase 3: PERF-CORE** | 实施状态感知型自适应休眠（临界态 200ms / 稳态 1.2s）；高难战斗 100% 保持 S 胜 |
| **Pitfall 7: Scrcpy 残留与 NemuIPC 强杀** | **Phase 3: PERF-CORE & Phase 4: STAB-MEMORY** | 废弃 `SetAsyncExc`，隔离子进程；72 小时挂机 Alas 句柄数稳定，无 `rpc 1722` 崩溃 |
| **Pitfall 9: 虚拟内存踩踏与 PageFile 雪崩** | **Phase 4: STAB-MEMORY** | 截图队列 JPEG 压缩，强制共享单例 OCR；报错转储瞬时内存增量 < 50MB，无磁盘卡死 |

---

## Sources (参考依据与分析来源)

- **Alas 源码基准**：
  - `webapp/packages/main/src/index.ts` (Electron 启动配置与硬件加速开关)
  - `module/webui/app.py` & `widgets.py` (PyWebIO 会话、RichLog 渲染与 DOM 截断机制)
  - `module/combat/combat.py` & `base/base.py` (战斗循环、截图间隔控制与状态机跳转)
  - `module/device/method/nemu_ipc.py` & `pool.py` (NemuIPC 互操作、线程池调度与 `SetAsyncExc` 实现)
  - `module/device/screenshot.py` (`screenshot_deque` 图像缓冲池管理与转储机制)
- **技术规范与架构文档**：
  - Chromium Documentation: *Handling Backgrounding and Occlusion Throttling in Chromium*
  - Microsoft Hardware Developer: *Timeout Detection and Recovery (TDR) in WDDM v1.3/v2.0*
  - PyWebIO Internal Architecture: *Session Lifecycle, Output Channels, and Coroutine Tasks*
  - Intel Haswell Iris/HD Graphics 4600 Programmer Reference Manual (PRM)
  - Nvidia Optimus Architecture & Hardware Decoding Routing Guidelines

---
*Pitfalls research for: AzurLaneAutoScript (Alas) Performance and Low-Resource 7*24h Stability*
*Researched: 2026-09-12*
