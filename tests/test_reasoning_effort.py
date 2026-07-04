"""reasoning_effort 参数的单元测试。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_llm(config=None):
    """构造 LLMClient，config 缺省时用最小配置。"""
    from core.llm import LLMClient
    cfg = config or {
        "base_url": "http://localhost:11434/v1",
        "api_key": "test-key",
        "model": "test-model",
    }
    return LLMClient(cfg)


class TestReasoningEffortConstruction:
    def test_default_reasoning_effort_is_none(self):
        """无配置构造时 reasoning_effort 应为 None。"""
        llm = _make_llm()
        assert llm.reasoning_effort is None

    def test_explicit_reasoning_effort_from_config(self):
        """配置 reasoning_effort='high' 时构造后应等于 'high'。"""
        llm = _make_llm({
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-key",
            "model": "test-model",
            "reasoning_effort": "high",
        })
        assert llm.reasoning_effort == "high"

    def test_invalid_config_value_falls_back_to_none(self):
        """配置无效值（如 'garbage'）时构造后应兜底为 None。"""
        llm = _make_llm({
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-key",
            "model": "test-model",
            "reasoning_effort": "garbage",
        })
        assert llm.reasoning_effort is None


class TestReasoningEffortPayload:
    def test_build_payload_omits_field_when_none(self):
        """reasoning_effort=None 时 payload 不应含 reasoning_effort 键。"""
        llm = _make_llm()
        payload = llm._build_payload(messages=[{"role": "user", "content": "hi"}])
        assert "reasoning_effort" not in payload

    def test_build_payload_includes_field_when_set(self):
        """reasoning_effort='high' 时 payload 应含 reasoning_effort='high'。"""
        llm = _make_llm({
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-key",
            "model": "test-model",
            "reasoning_effort": "high",
        })
        payload = llm._build_payload(messages=[{"role": "user", "content": "hi"}])
        assert payload["reasoning_effort"] == "high"

    def test_runtime_change_reflects_in_next_payload(self):
        """运行时改 reasoning_effort='medium' 后下次 payload 应含该值。"""
        llm = _make_llm()
        llm.reasoning_effort = "medium"
        payload = llm._build_payload(messages=[{"role": "user", "content": "hi"}])
        assert payload["reasoning_effort"] == "medium"
