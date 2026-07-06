"""
SubAgentTool - 让 agent 能派生子智能体。
"""
from typing import Optional

from tools.base import BaseTool
from core.llm import LLMClient
from core.long_term_memory import LongTermMemory


class SubAgentTool(BaseTool):
    name = "task"
    description = (
        "派一个子智能体处理独立的子任务。子智能体有独立上下文，只返回最终答案。"
        "适合：并行调研多个主题、独立子问题、需要长时间工具链的任务。"
        "不要用于简单查询或单步工具调用。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "给子智能体的任务描述，要具体完整"},
            "context": {"type": "string", "description": "可选的背景信息"}
        },
        "required": ["task"]
    }

    def __init__(self, llm: LLMClient, long_term_memory: LongTermMemory, depth: int = 2,
                 knowledge_base=None):
        self._llm = llm
        self._ltm = long_term_memory
        self._depth = depth
        self._kb = knowledge_base

    def execute(self, task: str, context: str = "") -> str:
        # 延迟导入避免循环依赖
        from core.subagent import SubAgent
        sub = SubAgent(self._llm, self._ltm, depth=self._depth, knowledge_base=self._kb)
        return sub.run(task, context)
