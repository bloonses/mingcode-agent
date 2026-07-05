"""LLM 客户端工厂测试。"""
from unittest.mock import patch, MagicMock
from core.llm import create_llm, LLMClientWrapper


def test_create_llm_returns_chat_openai():
    config = {
        "llm": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test",
            "model": "deepseek-chat",
            "temperature": 0.5,
            "max_tokens": 2048,
            "reasoning_effort": None,
        }
    }
    llm = create_llm(config)
    assert llm is not None
    assert llm.model_name == "deepseek-chat"
    assert llm.temperature == 0.5
    assert llm.max_tokens == 2048


def test_create_llm_with_reasoning_effort():
    config = {
        "llm": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test",
            "model": "deepseek-r1",
            "reasoning_effort": "high",
        }
    }
    llm = create_llm(config)
    assert llm.reasoning_effort == "high"


def test_create_llm_without_reasoning_effort():
    config = {
        "llm": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test",
            "model": "deepseek-chat",
            "reasoning_effort": None,
        }
    }
    llm = create_llm(config)
    assert llm.reasoning_effort is None


def test_llm_wrapper_chat_returns_content():
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "hello back"
    mock_chat.invoke.return_value = mock_response
    wrapper = LLMClientWrapper(mock_chat)
    result = wrapper.chat([{"role": "user", "content": "hi"}])
    assert result["content"] == "hello back"
