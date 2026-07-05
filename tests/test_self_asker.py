# tests/test_self_asker.py
"""SelfAsker 测试。"""
from unittest.mock import patch, MagicMock
from core.self_asker import SelfAsker


def test_selfasker_invoke_returns_confident_when_no_llm():
    """llm=None 时应返回 confident（占位行为）。"""
    asker = SelfAsker(llm=None, tools=[])
    result = asker.invoke("some context")
    assert result == "confident"


def test_selfasker_ask_returns_empty_when_no_tools():
    """tools=[] 且 llm=None 时 ask 应走 input 兜底（mock input）。"""
    asker = SelfAsker(llm=None, tools=[])
    with patch("builtins.input", return_value=""):
        result = asker.ask("question")
        assert result == ""


def test_selfasker_does_not_call_llm_when_none():
    """llm=None 时不应调 LLM。"""
    mock_llm = MagicMock()
    asker = SelfAsker(llm=None, tools=[])
    asker.invoke("ctx")
    mock_llm.invoke.assert_not_called()


def test_selfasker_confident_context():
    """清晰上下文应返回 confident。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "CONFIDENT"
    mock_llm.invoke.return_value = mock_response
    asker = SelfAsker(llm=mock_llm, tools=[])
    result = asker.invoke("明确的任务描述")
    assert result == "confident"


def test_selfasker_uncertain_context():
    """模糊上下文应返回 uncertain。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "UNCERTAIN: missing file path"
    mock_llm.invoke.return_value = mock_response
    asker = SelfAsker(llm=mock_llm, tools=[])
    result = asker.invoke("处理那个文件")
    assert result.startswith("uncertain")


def test_selfasker_llm_exception_returns_confident():
    """LLM 异常应兜底 confident（不阻塞）。"""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("API error")
    asker = SelfAsker(llm=mock_llm, tools=[])
    result = asker.invoke("ctx")
    assert result == "confident"


def test_selfasker_ask_calls_ask_user_tool():
    """ask 应调 ask_user 工具。"""
    mock_llm = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "ask_user"
    mock_tool.invoke.return_value = "user answer"
    asker = SelfAsker(llm=mock_llm, tools=[mock_tool])
    result = asker.ask("what file?")
    mock_tool.invoke.assert_called_once()
    assert "user answer" in result
