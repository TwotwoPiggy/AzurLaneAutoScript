import sys
import unittest
from unittest.mock import MagicMock, patch
from PIL import ImageDraw, Image

for mod_name in ['uiautomator2', 'adbutils', 'adbutils.errors', 'uiautomator2cache']:
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except ImportError:
            mock_mod = MagicMock()
            mock_mod.__file__ = f"dummy/{mod_name}.py"
            sys.modules[mod_name] = mock_mod

from module.base.timer import Timer
from module.device.method.pool import WorkerThread, WorkerPool


class DummyConfig:
    Optimization_ScreenshotInterval = 0.2
    Optimization_CombatScreenshotInterval = 1.0
    Emulator_ScreenshotMethod = 'nemu_ipc'


class DummyScreenshotDevice:
    def __init__(self):
        self.config = DummyConfig()
        self._screenshot_interval = Timer(0.1)
        self.sleep_calls = []

    def sleep(self, seconds):
        self.sleep_calls.append(seconds)


class TestPerfCore(unittest.TestCase):
    def test_worker_kill_safe_detach(self):
        """CORE-03: 验证 Worker.kill 采用安全解绑机制，绝不调用 PyThreadState_SetAsyncExc"""
        pool = WorkerPool()
        worker = WorkerThread.__new__(WorkerThread)
        worker.thread_pool = pool
        worker.thread = MagicMock()
        worker.thread.ident = 12345
        pool.all_workers[worker] = None

        with patch("ctypes.pythonapi.PyThreadState_SetAsyncExc", MagicMock()) as mock_set_async:
            ret = worker.kill()
            self.assertTrue(ret)
            # 验证绝未调用 PyThreadState_SetAsyncExc
            self.assertFalse(mock_set_async.called)
            # 验证 worker 已被从 all_workers 解绑
            self.assertNotIn(worker, pool.all_workers)

    def test_screenshot_interval_combat_and_reset(self):
        """CORE-01: 验证 combat 间隔为 1.0~1.2s，且 reset 能正常重置计时"""
        from module.device.screenshot import Screenshot
        device = Screenshot.__new__(Screenshot)
        device.config = DummyConfig()
        device._screenshot_interval = Timer(0.1)

        device.screenshot_interval_set('combat')
        self.assertGreaterEqual(device._screenshot_interval.limit, 1.0)
        self.assertLessEqual(device._screenshot_interval.limit, 1.2)

        # 验证 reset 接口存在并能执行
        device.screenshot_interval_reset()
        self.assertTrue(device._screenshot_interval.started())

    def test_wait_until_appear_adaptive_backoff(self):
        """CORE-04: 验证 wait_until_appear 在长等待未出现时触发自适应 sleep 退避"""
        from module.base.base import ModuleBase
        module = ModuleBase.__new__(ModuleBase)
        module.device = DummyScreenshotDevice()
        module.device.screenshot = MagicMock()
        module.device.screenshot_interval_reset = MagicMock()

        # 模拟前 7 次 appear 返回 False，第 8 次返回 True
        call_count = [0]
        def fake_appear(btn, offset=0):
            call_count[0] += 1
            return call_count[0] > 7

        module.appear = fake_appear
        module.wait_until_appear(button="DUMMY_BTN")

        # 验证在超过 5 次未出现后调用了 self.device.sleep(0.3)
        self.assertGreater(len(module.device.sleep_calls), 0)
        self.assertEqual(module.device.sleep_calls[0], 0.3)
        # 验证命中后触发了瞬时唤醒重置
        self.assertTrue(module.device.screenshot_interval_reset.called)


if __name__ == "__main__":
    unittest.main()
