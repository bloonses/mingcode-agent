"""Reflector 测试（Phase 2: LLM 评估 + 假成功检测）。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_reflector():
    from core.reflector import Reflector
    return Reflector(MagicMock())


class TestReflectorEvaluation:
    def test_done_status_with_ok_result_returns_success(self):
        """status=done 且 LLM 判 ok 时返回 success。"""
        reflector = _make_reflector()
        with patch.object(reflector, '_llm_evaluate', return_value="ok"):
            task = {"id": 0, "desc": "t1", "status": "done", "result": "all good"}
            verdict = reflector.evaluate(task)
        assert verdict == "success"

    def test_done_status_with_error_result_returns_fail(self):
        """status=done 但 result 含 Error 时 _llm_evaluate 应返回 fail。"""
        reflector = _make_reflector()
        with patch.object(reflector.llm, 'chat', return_value={"content": "fail: 含 Traceback"}):
            task = {"id": 0, "desc": "t1", "status": "done", "result": "Error: xxx"}
            verdict = reflector.evaluate(task)
        assert verdict.startswith("fail:")

    def test_failed_status_returns_fail_with_reason(self):
        """status=failed 时应返回 fail: <reason>（不调 LLM）。"""
        reflector = _make_reflector()
        task = {"id": 0, "desc": "t1", "status": "failed", "result": "Max iterations reached"}
        verdict = reflector.evaluate(task)
        assert verdict.startswith("fail:")
        assert "Max iterations" in verdict
        # 验证没调 LLM
        reflector.llm.chat.assert_not_called()

    def test_llm_evaluate_uses_task_desc_and_result(self):
        """_llm_evaluate 应把 task desc 和 result 都传给 LLM。"""
        reflector = _make_reflector()
        with patch.object(reflector.llm, 'chat', return_value={"content": "ok"}) as mock_chat:
            task = {"id": 0, "desc": "写 hello world", "status": "done", "result": "print('hello')"}
            reflector._llm_evaluate(task)
        # 验证 LLM 被调用
        mock_chat.assert_called_once()
        # 验证 prompt 含任务描述和结果
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "写 hello world" in prompt_text
        assert "print('hello')" in prompt_text

    def test_llm_failure_falls_back_to_trust_status(self):
        """LLM 评估失败时应兜底信任 task status（done→success）。"""
        reflector = _make_reflector()
        with patch.object(reflector.llm, 'chat', side_effect=Exception("network error")):
            task = {"id": 0, "desc": "t1", "status": "done", "result": "ok"}
            verdict = reflector.evaluate(task)
        assert verdict == "success"  # done 兜底为 success

    def test_llm_failure_with_failed_status_returns_fail(self):
        """LLM 评估失败 + status=failed 时兜底返回 fail。"""
        reflector = _make_reflector()
        with patch.object(reflector.llm, 'chat', side_effect=Exception("network error")):
            task = {"id": 0, "desc": "t1", "status": "failed", "result": "error"}
            verdict = reflector.evaluate(task)
        assert verdict.startswith("fail:")

    def test_truncates_long_result(self):
        """result 过长时应截断传给 LLM（避免 token 超限）。"""
        reflector = _make_reflector()
        long_result = "x" * 2000
        with patch.object(reflector.llm, 'chat', return_value={"content": "ok"}) as mock_chat:
            task = {"id": 0, "desc": "t1", "status": "done", "result": long_result}
            reflector._llm_evaluate(task)
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        # 验证 result 被截断（< 1000 字符）
        assert len(prompt_text) < 1500
