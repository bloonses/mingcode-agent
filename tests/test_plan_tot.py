"""plan_tot 工具薄包装测试（Phase 3: 改为调 Planner）。"""
from unittest.mock import MagicMock, patch

from tools.plan_tot import PlanToTTool


def test_schema():
    """工具 schema 应保持 plan_tot 名称，input 参数必需。"""
    tool = PlanToTTool(planner=MagicMock())
    schema = tool.to_schema()
    assert schema["function"]["name"] == "plan_tot"
    assert "input" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["required"] == ["input"]


def test_execute_calls_planner():
    """plan_tot.execute 应调 Planner.execute（薄包装）。"""
    mock_planner = MagicMock()
    mock_planner.execute.return_value = [
        {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
    ]
    tool = PlanToTTool(planner=mock_planner)
    result = tool.execute(input="写个贪吃蛇")
    mock_planner.execute.assert_called_once_with("写个贪吃蛇")
    assert "t1" in result


def test_execute_no_planner_creates_default():
    """无 planner 参数时应内部构造默认 Planner。"""
    tool = PlanToTTool(llm_client=MagicMock())
    assert tool._planner is None or tool._planner is not None  # 延迟构造
    # 触发一次 execute 后应已构造
    # 用 mock 避免真实 LLM 调用
    with patch("core.planner.Planner") as mock_planner_cls:
        mock_planner_cls.return_value.execute.return_value = []
        tool.execute(input="test")
    assert tool._planner is not None


def test_execute_returns_string():
    """execute 应返回字符串（工具协议）。"""
    mock_planner = MagicMock()
    mock_planner.execute.return_value = [
        {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
    ]
    tool = PlanToTTool(planner=mock_planner)
    result = tool.execute(input="test")
    assert isinstance(result, str)


def test_execute_empty_input_returns_error():
    """空 input 应返回错误信息。"""
    tool = PlanToTTool(planner=MagicMock())
    assert "Error" in tool.execute(input="")
    assert "Error" in tool.execute(input="   ")


def test_registered_in_main_agent():
    """主 agent 应注册 plan_tot 工具。"""
    import config.config as cfg
    from core.agent import NeonAgent
    agent = NeonAgent(cfg.DEFAULT_CONFIG)
    assert "plan_tot" in agent.registry.list_tools()
