# tests/test_executor.py
"""Executor 测试。"""
from unittest.mock import patch, MagicMock
from core.executor import Executor


def test_executor_invoke_returns_result():
    """Executor.invoke 应返回带 result 的 dict。"""
    mock_react_agent = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "task done successfully"
    mock_msg.tool_calls = None  # MagicMock 自动生成 tool_calls，必须显式 None
    mock_react_agent.invoke.return_value = {"messages": [mock_msg]}
    executor = Executor(react_agent=mock_react_agent)
    task = {"id": 0, "desc": "step 1", "status": "pending", "retries": 0, "feedback": None}
    result = executor.invoke(task)
    assert "result" in result
    assert "status" in result
    assert result["status"] in ("done", "executed")


def test_executor_invoke_exception_returns_failed():
    """Executor 异常应返回 failed 状态。"""
    mock_react_agent = MagicMock()
    mock_react_agent.invoke.side_effect = Exception("API error")
    executor = Executor(react_agent=mock_react_agent)
    task = {"id": 0, "desc": "step 1", "status": "pending", "retries": 0, "feedback": None}
    result = executor.invoke(task)
    assert result["status"] == "failed"
    assert "error" in result["result"].lower() or "API error" in result["result"]


def test_executor_invoke_preserves_task_fields():
    """Executor 应保留原 task 的 id 和 desc。"""
    mock_react_agent = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "ok"
    mock_msg.tool_calls = None
    mock_react_agent.invoke.return_value = {"messages": [mock_msg]}
    executor = Executor(react_agent=mock_react_agent)
    task = {"id": 5, "desc": "my task", "status": "pending", "retries": 0, "feedback": None}
    result = executor.invoke(task)
    assert result["id"] == 5
    assert result["desc"] == "my task"
