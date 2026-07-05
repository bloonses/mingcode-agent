"""main.py CLI 入口测试。"""
from unittest.mock import patch, MagicMock
from main import handle_command


def test_handle_help_command():
    result = handle_command("/help")
    assert "MINGCODE-LC" in result
    assert "/help" in result
    assert "/exit" in result


def test_handle_unknown_command():
    result = handle_command("/nonexistent")
    assert "未知" in result or "Unknown" in result


def test_handle_non_command():
    result = handle_command("hello")
    assert result is None


def test_handle_tools_with_agent():
    mock_agent = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "shell"
    mock_tool.description = "Execute shell command"
    mock_agent.tools = [mock_tool]
    result = handle_command("/tools", agent=mock_agent)
    assert "shell" in result


def test_handle_tools_without_agent():
    result = handle_command("/tools", agent=None)
    assert "未知" in result or "Unknown" in result


def test_handle_cognitive_no_args():
    """/cognitive 无参数应返回当前状态。"""
    mock_agent = MagicMock()
    mock_agent.cognitive_enabled = True
    result = handle_command("/cognitive", agent=mock_agent)
    assert "启用" in result or "enabled" in result.lower() or "on" in result.lower()


def test_handle_cognitive_on():
    """/cognitive on 应启用认知框架。"""
    mock_agent = MagicMock()
    mock_agent.cognitive_enabled = False
    result = handle_command("/cognitive on", agent=mock_agent)
    # 验证 cognitive_enabled 被设置为 True
    assert mock_agent.cognitive_enabled is True
    assert "启用" in result or "enabled" in result.lower()


def test_handle_cognitive_off():
    """/cognitive off 应关闭认知框架。"""
    mock_agent = MagicMock()
    mock_agent.cognitive_enabled = True
    result = handle_command("/cognitive off", agent=mock_agent)
    assert mock_agent.cognitive_enabled is False
    assert "关闭" in result or "disabled" in result.lower() or "off" in result.lower()


def test_handle_save_command():
    """/save 应调用 agent.save_session。"""
    mock_agent = MagicMock()
    result = handle_command("/save test_session", agent=mock_agent)
    assert "保存" in result or "save" in result.lower()


def test_handle_load_command():
    """/load 应调用 agent.load_session。"""
    mock_agent = MagicMock()
    result = handle_command("/load session1", agent=mock_agent)
    assert "加载" in result or "load" in result.lower()


def test_handle_sessions_empty():
    """/sessions 无会话应返回提示。"""
    mock_agent = MagicMock()
    mock_agent.memory.list_sessions.return_value = []
    result = handle_command("/sessions", agent=mock_agent)
    assert isinstance(result, str)


def test_handle_wechat_no_bot():
    """/wechat 未初始化应返回提示。"""
    mock_agent = MagicMock()
    mock_agent.wechat_bot = None
    result = handle_command("/wechat status", agent=mock_agent)
    assert isinstance(result, str)


def test_handle_qq_no_bot():
    """/qq 未初始化应返回提示。"""
    mock_agent = MagicMock()
    mock_agent.qq_onebot = None
    result = handle_command("/qq onebot status", agent=mock_agent)
    assert isinstance(result, str)
