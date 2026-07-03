import time
import pytest
from unittest.mock import MagicMock
from core.agent import NeonAgent


class SlowTool:
    """测试用慢工具，sleep 指定秒数。"""
    from tools.base import BaseTool

    name = "slow"
    description = "slow tool for testing"
    parameters = {
        "type": "object",
        "properties": {"seconds": {"type": "number"}},
        "required": ["seconds"]
    }

    def __init__(self, duration=2):
        self._duration = duration

    def execute(self, seconds=2):
        time.sleep(seconds)
        return f"slept {seconds}s"

    def safe_execute(self, **kwargs):
        return self.execute(**kwargs)

    def to_schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


def test_serial_tool_calls_run_sequentially(mock_llm, tmp_memory_file):
    """两个慢工具串行执行，总耗时约等于两倍单个耗时（思考一步执行一步）。"""
    import json
    mock_llm.set_responses([
        {
            "role": "assistant",
            "content": "串行执行两个",
            "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "slow", "arguments": json.dumps({"seconds": 1})}},
                {"id": "c2", "type": "function",
                 "function": {"name": "slow", "arguments": json.dumps({"seconds": 1})}},
            ],
        },
        {"role": "assistant", "content": "Final Answer: done", "tool_calls": None},
    ])

    config = {
        "llm": {"base_url": "http://localhost", "api_key": "x", "model": "m",
                "temperature": 0.7, "max_tokens": 100},
        "memory": {"max_history": 5},
        "ui": {"theme": "neon", "animation": False, "show_thinking": False, "show_tools": False},
        "tools": {}, "wechat": {}, "qq": {}
    }
    agent = NeonAgent(config)
    # 用 mock_llm 替换真实 LLMClient
    agent.llm = mock_llm
    # 替换 registry 只留慢工具
    from tools.base import ToolRegistry
    agent.registry = ToolRegistry()
    agent.registry.register(SlowTool(duration=1))
    agent.memory.build_system_prompt(agent.registry.get_all_schemas())

    start = time.time()
    chunks = list(agent.chat("串行执行"))
    elapsed = time.time() - start

    # 串行：约 2s（1+1）。断言 >= 1.5s 确认是串行而非并行。
    assert elapsed >= 1.5, f"串行执行耗时 {elapsed:.1f}s，预期 >= 1.5s（应为两段串行）"
    assert elapsed < 3.5, f"串行执行耗时 {elapsed:.1f}s，预期 < 3.5s"


def test_main_agent_has_task_tool():
    """主 agent 的工具列表应包含 'task'。"""
    config = {
        "llm": {"base_url": "http://localhost", "api_key": "x", "model": "m",
                "temperature": 0.7, "max_tokens": 100},
        "memory": {"max_history": 5},
        "ui": {"theme": "neon", "animation": False, "show_thinking": False, "show_tools": False},
        "tools": {}, "wechat": {}, "qq": {}
    }
    agent = NeonAgent(config)
    assert "task" in agent.registry.list_tools()
