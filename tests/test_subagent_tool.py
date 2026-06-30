import pytest
from unittest.mock import MagicMock
from tools.subagent import SubAgentTool
from core.long_term_memory import LongTermMemory


def test_subagent_tool_schema():
    """schema 应包含 task 参数。"""
    llm = MagicMock()
    ltm = MagicMock(spec=LongTermMemory)
    tool = SubAgentTool(llm, ltm, depth=1)
    schema = tool.to_schema()
    assert schema["function"]["name"] == "task"
    assert "task" in schema["function"]["parameters"]["properties"]
    assert "context" in schema["function"]["parameters"]["properties"]


def test_subagent_tool_execute_returns_final_answer(mock_llm, tmp_memory_file):
    """execute 应返回 SubAgent.run 的结果。"""
    mock_llm.set_responses([
        {"role": "assistant", "content": "Final Answer: tool result", "tool_calls": None},
    ])
    ltm = LongTermMemory()
    tool = SubAgentTool(mock_llm, ltm, depth=0)
    result = tool.execute(task="do something")
    assert result == "tool result"


def test_subagent_tool_execute_with_context(mock_llm, tmp_memory_file):
    """context 参数应被传递。"""
    mock_llm.set_responses([
        {"role": "assistant", "content": "Final Answer: ok", "tool_calls": None},
    ])
    ltm = LongTermMemory()
    tool = SubAgentTool(mock_llm, ltm, depth=0)
    result = tool.execute(task="task", context="background info")
    assert result == "ok"
