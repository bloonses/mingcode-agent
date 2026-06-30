"""
SubAgent - 子智能体
在独立上下文中跑完一个任务，返回最终答案字符串。
"""
import logging
import threading
from typing import Optional

from core.llm import LLMClient
from core.long_term_memory import LongTermMemory
from core.memory import ConversationMemory
from tools.base import ToolRegistry
from tools.shell import ShellTool
from tools.files import FileReadTool, FileWriteTool, FileEditTool
from tools.code import PythonExecTool
from tools.search import WebSearchTool, WebFetchTool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10
DEFAULT_TIMEOUT = 180

SUBAGENT_PROMPT_SUFFIX = """

你是 MINGCODE 的子智能体。专注完成给定任务，不要闲聊，不要询问用户。
使用工具完成任务后，用 `Final Answer: <结论>` 格式返回最终答案。
结论应简洁、聚焦、可操作。
若任务无法完成，返回 `Final Answer: [无法完成] <原因>`。
"""


def _parse_final_answer(content: str) -> Optional[str]:
    """从内容中提取 Final Answer 后的文本。"""
    if not content:
        return None
    marker = "Final Answer:"
    idx = content.find(marker)
    if idx < 0:
        return None
    return content[idx + len(marker):].strip()


class SubAgent:
    """子智能体：独立上下文跑完任务，返回最终答案字符串。"""

    def __init__(self, llm: LLMClient, long_term_memory: LongTermMemory,
                 depth: int = 2, timeout: int = DEFAULT_TIMEOUT):
        self.llm = llm
        self.long_term_memory = long_term_memory
        self.depth = depth
        self.timeout = timeout
        self.memory = ConversationMemory(max_history=20)
        self.registry = ToolRegistry()
        self._register_tools()
        self.memory.build_system_prompt(self.registry.get_all_schemas())
        # 追加子智能体专属指令
        self.memory.system_prompt = (self.memory.system_prompt or "") + SUBAGENT_PROMPT_SUFFIX

    def _register_tools(self):
        self.registry.register(ShellTool())
        self.registry.register(FileReadTool())
        self.registry.register(FileWriteTool())
        self.registry.register(FileEditTool())
        self.registry.register(PythonExecTool())
        self.registry.register(WebSearchTool())
        self.registry.register(WebFetchTool())
        # depth > 0 时注册递归 subagent 工具
        if self.depth > 0:
            from tools.subagent import SubAgentTool
            self.registry.register(
                SubAgentTool(self.llm, self.long_term_memory, depth=self.depth - 1)
            )

    def run(self, task: str, context: str = "") -> str:
        """跑独立 ReAct 循环，返回最终答案字符串。"""
        full_task = task if not context else f"{task}\n\n背景信息：{context}"
        self.memory.add_message("user", full_task)

        result_holder = {"value": "[subagent: no response]"}

        def _run_internal():
            try:
                for _ in range(MAX_ITERATIONS):
                    response = self.llm.chat(
                        messages=self.memory.get_messages(),
                        tools=self.registry.get_all_schemas(),
                        stream=False,
                    )
                    content = response.get("content") or ""
                    tool_calls = response.get("tool_calls")

                    if not tool_calls:
                        self.memory.add_message("assistant", content)
                        answer = _parse_final_answer(content)
                        if answer is not None:
                            result_holder["value"] = answer
                            return
                        # 没有 Final Answer 标记，返回内容本身
                        result_holder["value"] = content.strip() if content.strip() else "[subagent: empty response]"
                        return

                    # 有工具调用，记录 assistant 消息并执行
                    assistant_kwargs = {"tool_calls": [
                        {
                            "id": tc["id"],
                            "type": tc["type"],
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": __import__("json").dumps(
                                    tc["function"]["arguments"], ensure_ascii=False
                                ) if isinstance(tc["function"]["arguments"], dict)
                                else tc["function"]["arguments"]
                            }
                        } for tc in tool_calls
                    ]}
                    self.memory.add_message("assistant", content, **assistant_kwargs)

                    for tc in tool_calls:
                        call_id = tc["id"]
                        func = tc["function"]
                        tool_name = func["name"]
                        import json as _json
                        args = func["arguments"]
                        if isinstance(args, str):
                            try:
                                args = _json.loads(args)
                            except _json.JSONDecodeError:
                                args = {"_raw": args}
                        try:
                            result = self.registry.execute_tool(tool_name, **args)
                        except Exception as e:
                            result = f"工具执行错误: {str(e)}"
                        self.memory.add_message("tool", result, tool_call_id=call_id)
                # 达到最大迭代
                result_holder["value"] = "[subagent: max iterations reached]"
            except Exception as e:
                result_holder["value"] = f"[subagent error: {str(e)}]"
                try:
                    self.long_term_memory.auto_learn_from_error(
                        "subagent 执行异常", str(e)[:200]
                    )
                except Exception:
                    pass

        worker = threading.Thread(target=_run_internal, daemon=True)
        worker.start()
        worker.join(timeout=self.timeout)

        if worker.is_alive():
            # 超时，worker 仍在后台跑（daemon，随进程退出）
            return "[subagent timeout]"
        return result_holder["value"]
