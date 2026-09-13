import unittest
from unittest.mock import MagicMock, patch
from module.webui.widgets import RichLog


class DummyProcessManager:
    def __init__(self, count=200):
        self.renderables = [f"Log line {i}" for i in range(count)]
        self.renderables_max_length = 500
        self.renderables_reduce_length = 100


class TestWebUIPerf(unittest.TestCase):
    @patch("module.webui.widgets.run_js")
    def test_logoutput_extend_dom_truncation(self, mock_run_js):
        """WEB-02: 验证 extend 注入了 150 节点滑动截断与 overflow-anchor"""
        log = RichLog("log")
        log.extend("Test text", max_dom_nodes=150)
        self.assertTrue(mock_run_js.called)
        js_arg = mock_run_js.call_args_list[0][0][0]
        self.assertIn("overflow-anchor", js_arg)
        self.assertIn("children.length > 150", js_arg)
        self.assertIn(".slice(0, children.length - 150).remove()", js_arg)

    @patch("module.webui.widgets.run_js")
    def test_logoutput_visibility_gate_and_catchup(self, mock_run_js):
        """WEB-01 & WEB-03: 验证可见性门禁挂起以及恢复激活时的快照补偿"""
        log = RichLog("log")
        log.render = MagicMock(side_effect=lambda x: f"<div>{x}</div>")
        pm = DummyProcessManager(count=200)

        is_visible_state = [False]
        gen = log.put_log(pm, is_visible=lambda: is_visible_state[0])

        # 初始化 Generator
        next(gen)  # 产出 initial yield

        # 第一步：处于后台 (is_visible = False)
        # 此时应重置并渲染一次首屏，随后在后台状态下不会每次 append 新日志
        next(gen)
        # 模拟后台产生新日志
        pm.renderables.append("New background log 1")
        render_call_count_before = log.render.call_count
        next(gen)
        # 后台状态下不应调用增量渲染
        self.assertEqual(log.render.call_count, render_call_count_before)

        # 第二步：恢复前台 (is_visible = True)
        is_visible_state[0] = True
        next(gen)
        # 激活时应触发全量快照补偿，重新渲染最新不超过 150 条日志
        self.assertGreater(log.render.call_count, render_call_count_before)

    def test_websocket_heartbeat_and_visibility_injected(self):
        """WEB-04: 验证 app.py 注入了 30s WebSocket 心跳与 is_visible 监听"""
        import os
        app_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "module",
            "webui",
            "app.py",
        )
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("_ws_heartbeat", content)
        self.assertIn("self.task_handler.add(_ws_heartbeat, 30)", content)
        self.assertIn("is_visible=lambda: getattr(self, \"visible\", True)", content)


if __name__ == "__main__":
    unittest.main()
