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


def test_parallel_tool_calls_run_concurrently(mock_llm, tmp_memory_file):
    """两个慢工具并行执行，总耗时约等于单个耗时而非两倍。"""
    import json
    mock_llm.set_responses([
        {
            "role": "assistant",
            "content": "并行执行两个",
            "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "slow", "arguments": json.dumps({"seconds": 2})}},
                {"id": "c2", "type": "function",
                 "function": {"name": "slow", "arguments": json.dumps({"seconds": 2})}},
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
    agent.registry.register(SlowTool(duration=2))
    agent.memory.build_system_prompt(agent.registry.get_all_schemas())

    start = time.time()
    chunks = list(agent.chat("并行执行"))
    elapsed = time.time() - start

    # 并行：约 2s；串行会是 4s。设阈值 3.5s 容错。
    assert elapsed < 3.5, f"并行执行耗时 {elapsed:.1f}s，预期 < 3.5s"


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
