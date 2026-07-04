"""SelfAsker 测试（Phase 4: 不确定性检测 + Self-Ask）。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_self_asker():
    from core.self_asker import SelfAsker
    return SelfAsker(MagicMock(), MagicMock())


class TestSelfAskerCheck:
    def test_confident_response_returns_confident(self):
        """LLM 返回 confident 时应返回 confident。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', return_value={"content": "confident"}):
            verdict = asker.check_uncertainty("obs", {"desc": "t1"})
        assert verdict == "confident"

    def test_uncertain_response_returns_uncertain_with_reason(self):
        """LLM 返回 uncertain 时应返回 uncertain: <reason>。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', return_value={"content": "uncertain: 需要确认文件路径"}):
            verdict = asker.check_uncertainty("obs", {"desc": "t1"})
        assert verdict.startswith("uncertain")
        assert "文件路径" in verdict

    def test_llm_failure_returns_confident(self):
        """LLM 调用失败时应兜底返回 confident（不阻断执行）。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', side_effect=Exception("network error")):
            verdict = asker.check_uncertainty("obs", {"desc": "t1"})
        assert verdict == "confident"

    def test_empty_response_returns_confident(self):
        """LLM 返回空时应兜底返回 confident。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', return_value={"content": ""}):
            verdict = asker.check_uncertainty("obs", {"desc": "t1"})
        assert verdict == "confident"

    def test_prompt_contains_task_and_observation(self):
        """prompt 应包含任务描述和最新观察。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', return_value={"content": "confident"}) as mock_chat:
            asker.check_uncertainty("工具返回：文件不存在", {"desc": "读取配置文件"})
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "读取配置文件" in prompt_text
        assert "文件不存在" in prompt_text

    def test_truncates_long_observation(self):
        """observation 过长时应截断。"""
        asker = _make_self_asker()
        long_obs = "x" * 1000
        with patch.object(asker.llm, 'chat', return_value={"content": "confident"}) as mock_chat:
            asker.check_uncertainty(long_obs, {"desc": "t1"})
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        # 验证 observation 被截断（< 600 字符）
        assert len(prompt_text) < 800


class TestSelfAskerAsk:
    def test_ask_calls_ask_user_tool(self):
        """ask 应调 registry.execute_tool('ask_user', ...)。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', return_value="用户回答：路径是 /tmp") as mock_tool:
            result = asker.ask("任务描述", "uncertain: 需要确认文件路径")
        mock_tool.assert_called_once()
        # 验证调用 ask_user 工具
        assert mock_tool.call_args[0][0] == "ask_user" or mock_tool.call_args[1].get('tool_name') == "ask_user"

    def test_ask_returns_user_response(self):
        """ask 应返回用户的回答字符串。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', return_value="用户回答"):
            result = asker.ask("任务", "uncertain: 问题")
        assert result == "用户回答"

    def test_ask_extracts_question_from_uncertain_reason(self):
        """ask 应从 'uncertain: <reason>' 提取问题传给 ask_user。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', return_value="用户回答") as mock_tool:
            asker.ask("任务描述", "uncertain: 文件路径是什么？")
        # 验证 prompt 含提取的问题
        call_kwargs = mock_tool.call_args[1]
        prompt_arg = call_kwargs.get('prompt', '')
        assert "文件路径是什么" in prompt_arg

    def test_ask_user_failure_returns_empty_string(self):
        """ask_user 工具调用失败时应返回空字符串（不阻断）。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', side_effect=Exception("tool error")):
            result = asker.ask("任务", "uncertain: 问题")
        assert result == ""

    def test_ask_user_cancelled_returns_empty_string(self):
        """用户取消 ask_user 时应返回空字符串。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', return_value=""):
            result = asker.ask("任务", "uncertain: 问题")
        assert result == ""
