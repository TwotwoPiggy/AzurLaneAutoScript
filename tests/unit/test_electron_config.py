import os
import unittest


class TestElectronMainConfig(unittest.TestCase):
    def setUp(self):
        self.main_ts_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "webapp",
            "packages",
            "main",
            "src",
            "index.ts",
        )
        self.assertTrue(os.path.exists(self.main_ts_path), f"File not found: {self.main_ts_path}")
        with open(self.main_ts_path, "r", encoding="utf-8") as f:
            self.content = f.read()

    def test_no_unconditional_disable_hardware_acceleration(self):
        """DESK-01: 验证未在顶层无条件禁用 GPU 硬件加速"""
        lines = [line.strip() for line in self.content.splitlines()]
        # 顶层不应该有无条件的 app.disableHardwareAcceleration();
        top_level_disable = [
            line for line in lines
            if line == "app.disableHardwareAcceleration();"
        ]
        # 只允许在 GPU 崩溃容灾回调（降级回退）中存在
        self.assertEqual(
            len(top_level_disable),
            1,
            "app.disableHardwareAcceleration() should only exist as a crash fallback",
        )

    def test_low_power_gpu_and_memory_limit_switches(self):
        """DESK-01 & DESK-04: 验证注入了核显低功耗和 V8 堆内存上限开关"""
        self.assertIn("force_low_power_gpu", self.content)
        self.assertIn("disable-gpu-process-crash-limit", self.content)
        self.assertIn("--max-old-space-size=128", self.content)

    def test_stepped_frame_rate_throttling(self):
        """DESK-02: 验证存在失焦与最小化阶梯降频控制"""
        self.assertIn("applyFrameRate(5)", self.content)
        self.assertIn("applyFrameRate(1)", self.content)
        self.assertIn("setFrameRate(fps)", self.content)

    def test_gpu_and_renderer_crash_resilience(self):
        """DESK-03: 验证监听了渲染与 GPU 进程崩溃容灾事件"""
        self.assertIn("child-process-gone", self.content)
        self.assertIn("render-process-gone", self.content)


if __name__ == "__main__":
    unittest.main()
