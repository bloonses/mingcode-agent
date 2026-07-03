"""测试 LLMClient 的 messages 规范化逻辑，修复智谱 GLM code=1214 错误。"""
from core.llm import LLMClient


def _make_client():
    """构造一个 LLMClient 实例（不发真实请求）。"""
    config = {
        "llm": {
            "base_url": "http://localhost:11434",
            "api_key": "test",
            "model": "test",
        }
    }
    return LLMClient(config)


def test_none_content_becomes_empty_string():
    """content=None 应转为 ''，智谱不接受 null。"""
    client = _make_client()
    messages = [{"role": "user", "content": None}]
    sanitized = client._sanitize_messages(messages)
    assert sanitized[0]["content"] == ""


def test_tool_empty_content_filled():
    """tool 角色空 content 应填充默认值，智谱不接受空 tool 结果。"""
    client = _make_client()
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "f", "arguments": "{}"}}]},
        {"role": "tool", "content": "", "tool_call_id": "1"},
    ]
    sanitized = client._sanitize_messages(messages)
    assert sanitized[2]["content"] != ""
    assert sanitized[2]["content"]  # 非空


def test_tool_none_content_filled():
    """tool 角色 None content 应填充。"""
    client = _make_client()
    messages = [
        {"role": "tool", "content": None, "tool_call_id": "1"},
    ]
    sanitized = client._sanitize_messages(messages)
    assert sanitized[0]["content"] is not None
    assert sanitized[0]["content"] != ""


def test_normal_messages_unchanged():
    """正常消息不应被修改。"""
    client = _make_client()
    messages = [
        {"role": "system", "content": "you are helpful"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    sanitized = client._sanitize_messages(messages)
    assert sanitized == messages


def test_assistant_with_tool_calls_empty_content_kept():
    """assistant 带 tool_calls 时空 content 应保留为 ''（智谱接受）。"""
    client = _make_client()
    messages = [
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "f", "arguments": "{}"}}]},
    ]
    sanitized = client._sanitize_messages(messages)
    assert sanitized[0]["content"] == ""


def test_empty_messages_list_returns_empty():
    """空 messages 列表应原样返回。"""
    client = _make_client()
    assert client._sanitize_messages([]) == []


def test_missing_content_key_added():
    """缺少 content key 的消息应补上 ''。"""
    client = _make_client()
    messages = [{"role": "user"}]
    sanitized = client._sanitize_messages(messages)
    assert "content" in sanitized[0]
    assert sanitized[0]["content"] == ""
