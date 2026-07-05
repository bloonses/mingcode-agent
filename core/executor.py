# core/executor.py
"""Executor - 包装 ReAct agent 执行单个任务。"""
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage


class Executor:
    """Executor - 调用 ReAct agent 执行任务。

    Phase 2: 简单包装
    Phase 4: 扩展 Self-Ask 不确定性检测
    """

    def __init__(self, react_agent=None, llm=None, tools=None,
                 enable_uncertainty_check: bool = False):
        self.react_agent = react_agent
        self.llm = llm
        self.tools = tools or []
        self.enable_uncertainty_check = enable_uncertainty_check

    def invoke(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个任务。"""
        if self.react_agent is None:
            return {
                **task,
                "result": "Error: ReAct agent not configured",
                "status": "failed",
            }
        try:
            task_desc = task.get("desc", "")
            response = self.react_agent.invoke({
                "messages": [HumanMessage(content=task_desc)],
            })
            # 提取最后一条 AI 消息的内容
            messages = response.get("messages", [])
            content = ""
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
                    content = msg.content
                    break
                elif hasattr(msg, "content") and msg.content:
                    content = msg.content
                    break
            return {
                **task,
                "result": content or "(无输出)",
                "status": "done",
            }
        except Exception as e:
            return {
                **task,
                "result": f"Error: {e}",
                "status": "failed",
            }
