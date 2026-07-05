# tests/test_tools_advanced.py
"""高级工具测试。"""
from unittest.mock import patch, MagicMock
from tools.subagent import subagent
from tools.plan_tot import plan_tot
from tools.computer_use import computer_screenshot


def test_subagent_returns_string():
    """subagent 应返回字符串。"""
    with patch("tools.subagent.create_react_agent") as mock_create:
        mock_agent = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "sub task done"
        mock_msg.tool_calls = None
        mock_agent.invoke.return_value = {"messages": [mock_msg]}
        mock_create.return_value = mock_agent
        with patch("tools.subagent.create_llm") as mock_llm_factory:
            with patch("tools.subagent.load_config") as mock_load:
                mock_load.return_value = {"llm": {"base_url": "http://t", "api_key": "sk", "model": "m"}}
                result = subagent.invoke({"task": "do something"})
                assert isinstance(result, str)


def test_plan_tot_returns_string():
    """plan_tot 应返回字符串。"""
    with patch("tools.plan_tot.Planner") as mock_planner_cls:
        mock_planner = MagicMock()
        mock_planner.invoke.return_value = [{"id": 0, "desc": "step", "status": "pending", "retries": 0, "feedback": None}]
        mock_planner_cls.return_value = mock_planner
        with patch("tools.plan_tot.create_llm"):
            with patch("tools.plan_tot.load_config") as mock_load:
                mock_load.return_value = {"llm": {"base_url": "http://t", "api_key": "sk", "model": "m"}}
                result = plan_tot.invoke({"task": "complex task"})
                assert isinstance(result, str)


def test_computer_screenshot_returns_string():
    """computer_screenshot 应返回字符串（即使失败也不抛异常）。"""
    with patch("tools.computer_use.pyautogui") as mock_pg:
        mock_pg.screenshot.return_value = MagicMock()
        result = computer_screenshot.invoke({})
        assert isinstance(result, str)
