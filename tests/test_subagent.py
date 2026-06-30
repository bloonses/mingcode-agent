import pytest
from core.subagent import SubAgent
from core.long_term_memory import LongTermMemory


def test_run_returns_final_answer(mock_llm, tmp_memory_file):
    """单轮响应含 Final Answer，直接返回答案。"""
    mock_llm.set_responses([
        {"role": "assistant", "content": "Final Answer: 调研完成，结果是 42", "tool_calls": None},
    ])
    ltm = LongTermMemory()
    sub = SubAgent(llm=mock_llm, long_term_memory=ltm, depth=0)
    result = sub.run("什么是答案？")
    assert result == "调研完成，结果是 42"


def test_run_extracts_final_answer_with_prefix(mock_llm, tmp_memory_file):
    """Final Answer 前可能有其他文字。"""
    mock_llm.set_responses([
        {"role": "assistant", "content": "经过思考\nFinal Answer: done", "tool_calls": None},
    ])
    ltm = LongTermMemory()
    sub = SubAgent(llm=mock_llm, long_term_memory=ltm, depth=0)
    assert sub.run("task") == "done"


def test_run_with_tool_call_then_final_answer(mock_llm, tmp_memory_file):
    """第一轮调工具，第二轮给 Final Answer。"""
    import json
    mock_llm.set_responses([
        {
            "role": "assistant",
            "content": "让我查一下",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "file_read", "arguments": json.dumps({"path": "/tmp/x.txt"})}
            }],
        },
        {"role": "assistant", "content": "Final Answer: 文件内容是 hello", "tool_calls": None},
    ])
    ltm = LongTermMemory()
    sub = SubAgent(llm=mock_llm, long_term_memory=ltm, depth=0)
    result = sub.run("读 /tmp/x.txt")
    assert result == "文件内容是 hello"


def test_run_returns_error_on_llm_exception(mock_llm, tmp_memory_file):
    """LLM 抛异常时返回 [subagent error: ...]。"""
    mock_llm.chat.side_effect = lambda **kw: (_ for _ in ()).throw(ConnectionError("refused"))
    ltm = LongTermMemory()
    sub = SubAgent(llm=mock_llm, long_term_memory=ltm, depth=0)
    result = sub.run("task")
    assert result.startswith("[subagent error:")


def test_run_returns_timeout(mock_llm, tmp_memory_file):
    """LLM 永远不返回 Final Answer 且达到超时。"""
    import time as _time

    def slow_chat(**kw):
        _time.sleep(10)
        return {"role": "assistant", "content": "Final Answer: late", "tool_calls": None}

    mock_llm.chat.side_effect = slow_chat
    ltm = LongTermMemory()
    sub = SubAgent(llm=mock_llm, long_term_memory=ltm, depth=0, timeout=1)
    result = sub.run("task")
    assert result == "[subagent timeout]"


def test_run_max_iterations(mock_llm, tmp_memory_file):
    """LLM 一直只返回无 Final Answer 的内容，达到最大轮次。"""
    mock_llm.set_responses([
        {"role": "assistant", "content": "还在思考...", "tool_calls": None}
    ] * 15)
    ltm = LongTermMemory()
    sub = SubAgent(llm=mock_llm, long_term_memory=ltm, depth=0, timeout=30)
    # 第 1 轮就会因无 tool_calls 且无 Final Answer 返回 "还在思考..."
    result = sub.run("task")
    assert result == "还在思考..."


def test_depth_zero_does_not_register_task_tool(mock_llm, tmp_memory_file):
    """depth=0 时工具列表不应包含 'task'。"""
    ltm = LongTermMemory()
    sub = SubAgent(llm=mock_llm, long_term_memory=ltm, depth=0)
    tool_names = sub.registry.list_tools()
    assert "task" not in tool_names


def test_depth_positive_registers_task_tool(mock_llm, tmp_memory_file):
    """depth>0 时工具列表应包含 'task'。"""
    ltm = LongTermMemory()
    sub = SubAgent(llm=mock_llm, long_term_memory=ltm, depth=2)
    tool_names = sub.registry.list_tools()
    assert "task" in tool_names
