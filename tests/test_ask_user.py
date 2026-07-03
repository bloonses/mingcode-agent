"""AskUserTool 单元测试。"""
from tools.ask_user import AskUserTool


def test_schema():
    tool = AskUserTool(prompt_func=lambda q: "")
    schema = tool.to_schema()
    assert schema["function"]["name"] == "ask_user"
    assert "question" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["required"] == ["question"]


def test_execute_returns_user_answer():
    captured = {}
    def fake_prompt(question):
        captured["q"] = question
        return "use pytest"

    tool = AskUserTool(prompt_func=fake_prompt)
    result = tool.execute(question="用哪个测试框架？")
    assert result == "use pytest"
    assert captured["q"] == "用哪个测试框架？"


def test_execute_trims_whitespace():
    tool = AskUserTool(prompt_func=lambda q: "  ok  \n")
    assert tool.execute(question="confirm?") == "ok"


def test_execute_empty_input_returns_marker():
    tool = AskUserTool(prompt_func=lambda q: "")
    result = tool.execute(question="continue?")
    assert result == "(no input)"


def test_default_prompt_func_is_input_builtin():
    # 默认 prompt_func 应为内置 input，便于在真实 CLI 中使用
    tool = AskUserTool()
    assert tool._prompt_func is input


def test_registered_in_main_agent():
    """主 agent 应注册 ask_user 工具。"""
    import config.config as cfg
    from core.agent import NeonAgent
    fake_config = cfg.DEFAULT_CONFIG
    agent = NeonAgent(fake_config)
    try:
        assert "ask_user" in agent.registry.list_tools()
    finally:
        # NeonAgent 创建了 ThreadPoolExecutor，需要清理
        agent._executor.shutdown(wait=False)
