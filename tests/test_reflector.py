# tests/test_reflector.py
"""Reflector 测试。"""
from unittest.mock import MagicMock
from core.reflector import Reflector


def test_reflector_success_when_done():
    """status=done 应返回 success。"""
    reflector = Reflector(llm=MagicMock())
    task = {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict == "success"


def test_reflector_fail_when_failed():
    """status=failed 应返回 fail:xxx。"""
    reflector = Reflector(llm=MagicMock())
    task = {"id": 0, "desc": "t1", "status": "failed", "result": "Error: timeout", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict.startswith("fail")


def test_reflector_fail_with_error_in_result():
    """result 含 Error 应返回 fail。"""
    reflector = Reflector(llm=MagicMock())
    task = {"id": 0, "desc": "t1", "status": "done", "result": "Traceback: ...Error: something", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict.startswith("fail")


def test_reflector_llm_not_called_when_none():
    """llm=None 时不应调 LLM，直接返回 success。"""
    reflector = Reflector(llm=None)
    task = {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict == "success"


def test_reflector_llm_evaluates_apparent_success():
    """status=done 且无错误关键词时应调 LLM 评估。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "SUCCESS"
    mock_llm.invoke.return_value = mock_response
    reflector = Reflector(llm=mock_llm)
    task = {"id": 0, "desc": "t1", "status": "done", "result": "看起来完成了，但实际可能有 bug", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict == "success"
    mock_llm.invoke.assert_called_once()


def test_reflector_llm_detects_apparent_failure():
    """LLM 应能识别假成功。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "FAIL: result contains syntax error"
    mock_llm.invoke.return_value = mock_response
    reflector = Reflector(llm=mock_llm)
    task = {"id": 0, "desc": "t1", "status": "done", "result": "代码已生成", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict.startswith("fail")
    assert "syntax error" in verdict


def test_reflector_llm_exception_falls_back_to_success():
    """LLM 异常应兜底为 success（避免阻塞流程）。"""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("API error")
    reflector = Reflector(llm=mock_llm)
    task = {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict == "success"


def test_reflector_truncates_long_result():
    """result > 500 字符应截断。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "SUCCESS"
    mock_llm.invoke.return_value = mock_response
    reflector = Reflector(llm=mock_llm)
    long_result = "x" * 1000
    task = {"id": 0, "desc": "t1", "status": "done", "result": long_result, "retries": 0, "feedback": None}
    reflector.invoke(task)
    # 验证 LLM prompt 包含截断后的内容
    call_args = mock_llm.invoke.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])
    prompt_content = str(messages)
    assert "x" * 1000 not in prompt_content
