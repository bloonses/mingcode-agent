"""PlanToTTool 单元测试。"""
from unittest.mock import MagicMock

from tools.plan_tot import PlanToTTool


def _make_llm(response_content: str):
    llm = MagicMock()
    llm.chat.return_value = {
        "role": "assistant",
        "content": response_content,
        "tool_calls": None,
    }
    return llm


def test_schema():
    tool = PlanToTTool(llm=_make_llm(""))
    schema = tool.to_schema()
    assert schema["function"]["name"] == "plan_tot"
    assert "task" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["required"] == ["task"]


def test_execute_returns_llm_content():
    plan_text = "## 候选方案\n### 方案1\n## 最终计划\nstep1"
    llm = _make_llm(plan_text)
    tool = PlanToTTool(llm=llm)
    result = tool.execute(task="实现登录功能")
    assert result == plan_text
    # 确认 LLM 被非流式调用
    llm.chat.assert_called_once()
    _, kwargs = llm.chat.call_args
    assert kwargs.get("stream") is False


def test_execute_passes_task_in_prompt():
    llm = _make_llm("ok")
    tool = PlanToTTool(llm=llm)
    tool.execute(task="重构认证模块")
    args, kwargs = llm.chat.call_args
    messages = args[0] if args else kwargs["messages"]
    assert "重构认证模块" in messages[0]["content"]


def test_execute_empty_task_returns_error():
    tool = PlanToTTool(llm=_make_llm("ok"))
    assert "Error" in tool.execute(task="")
    assert "Error" in tool.execute(task="   ")


def test_execute_llm_exception_returns_failure_marker():
    llm = MagicMock()
    llm.chat.side_effect = RuntimeError("network down")
    tool = PlanToTTool(llm=llm)
    result = tool.execute(task="test task")
    assert "PlanToT" in result or "失败" in result
    assert "network down" in result


def test_execute_empty_llm_content_returns_marker():
    llm = _make_llm("")
    tool = PlanToTTool(llm=llm)
    result = tool.execute(task="test")
    assert result == "(空响应)"


def test_prompt_contains_tot_structure_keywords():
    """prompt 必须包含 ToT 三阶段关键词，确保 LLM 走思考→评估→筛选循环。"""
    llm = _make_llm("ok")
    tool = PlanToTTool(llm=llm)
    tool.execute(task="任务X")
    args, kwargs = llm.chat.call_args
    messages = args[0] if args else kwargs["messages"]
    prompt = messages[0]["content"]
    assert "候选方案" in prompt
    assert "评估" in prompt
    assert "最优方案" in prompt
    assert "最终计划" in prompt


def test_registered_in_main_agent():
    """主 agent 应注册 plan_tot 工具。"""
    import config.config as cfg
    from core.agent import NeonAgent
    agent = NeonAgent(cfg.DEFAULT_CONFIG)
    assert "plan_tot" in agent.registry.list_tools()
