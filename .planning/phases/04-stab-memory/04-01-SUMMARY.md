# Plan 04-01 Summary: 错误截图队列 JPEG 内存流高倍压缩与回溯容量控制

## 执行概述 (Execution Overview)
- **Phase**: 04-stab-memory
- **Plan**: 01 (Wave 1)
- **需求与决策**: MEM-01 (D-01, D-02, D-03, D-04)
- **状态**: ✅ 已完成 (Completed)
- **提交信息**: `feat(device): compress screenshot deque with jpeg and clamp capacity` (commit `137967e99`)
- **远端推送**: 已成功推送至 `origin/custom` (通过本地代理 `http://127.0.0.1:10808`)

---

## 实施细节 (Implementation Details)

1. **DequeFrame 惰性解码容器与压缩存储 (`module/device/screenshot.py`)**:
   - 定义了轻量级字典子类 `DequeFrame(dict)`，直接封装 JPEG 压缩字节流 `image_bytes` 与时间戳 `time`。
   - 重写 `__getitem__`、`get`、`__contains__` 与 `__setitem__`，在访问 `'image'` 键时按需调用 `cv2.imdecode` + `cv2.cvtColor(bgr, COLOR_BGR2RGB)` 并缓存解码结果，保持已有调用代码 100% 透明向后兼容。
   - 在 `Screenshot.screenshot()` 中，当启用错误保存且图像有效时，使用 `cv2.cvtColor` 转为 BGR 并经由 `cv2.imencode('.jpg', bgr, [IMWRITE_JPEG_QUALITY, 80])` 压缩为字节流后存入 `screenshot_deque`。单帧体积由裸存 2.76MB 压缩至 ~31KB（降幅 >98%）。

2. **容量硬上限钳制与静态默认值同步**:
   - 在 `Screenshot.screenshot_deque` 属性中将容量硬上限钳制在 `max(1, min(length, 100))`，彻底防范历史 300 帧配置在极端情况下占用高额内存（D-02）。
   - 在 `module/config/argument/argument.yaml`、`module/config/argument/args.json` 与 `module/config/config_generated.py` 中将 `ScreenshotLength` / `Error_ScreenshotLength` 默认值同步修改为 60。

3. **异常转储链路直接二进制直写 (`alas.py`)**:
   - 重构 `AzurLaneAutoScript.save_error_log()`：遍历 `screenshot_deque` 时若存在 `image_bytes`，直接以二进制流 `'wb'` 写入 `{folder}/{image_time}.jpg`，完全规避二次 decode 与 encode 损耗，实现 100 帧仅耗时 ~117ms 直写落盘。
   - 保留未含 `image_bytes` 帧的平滑降级兼容逻辑。
   - 调度循环与任务交接中严格不执行 `screenshot_deque.clear()`，保留跨任务边界自然滑动窗口（D-04）。

---

## 验证结论 (Verification Results)
通过脚本 `scratch/verify_04_01.py` 严格验证以下指标：
- **单帧压缩率**: 模拟游戏 UI 图像单帧压缩后体积为 31.25 KB（原生裸存 2764.8 KB，降幅 98.8%）。
- **容量钳制**: 当配置设为 300 时，`screenshot_deque.maxlen` 被严格限制为 100。
- **内存占用**: 100 帧总图片字节流仅 3.05 MB（远低于旧机制 276 MB）。
- **落盘速度**: 100 帧 JPEG 二进制直接直写耗时 117.00 ms（单帧仅 1.17 ms），且图片经 `cv2.imread` 检验完好无损。
- **配置同步**: YAML、JSON 与 Python 静态类属性中默认值均严格一致为 60。
