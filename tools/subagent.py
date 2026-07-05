# tools/subagent.py
"""子智能体工具 - 派生独立 ReAct agent 处理子任务。"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from langgraph.prebuilt import create_react_agent
from core.llm import create_llm
from config.config import load_config


class SubagentInput(BaseModel):
    task: str = Field(description="Sub-task for the subagent to handle")


@tool(args_schema=SubagentInput)
def subagent(task: str) -> str:
    """Dispatch a subagent to handle an independent sub-task with its own context."""
    try:
        # 延迟导入以避免循环依赖（tools/__init__ -> tools.subagent -> tools）
        from tools import ALL_TOOLS
        config = load_config()
        llm = create_llm(config)
        agent = create_react_agent(llm, ALL_TOOLS)
        response = agent.invoke({"messages": [{"role": "user", "content": task}]})
        messages = response.get("messages", [])
        for msg in reversed(messages):
            content = getattr(msg, "content", "") or ""
            if content and not getattr(msg, "tool_calls", None):
                return content
        return "(subagent 无输出)"
    except Exception as e:
        return f"Error: {e}"
