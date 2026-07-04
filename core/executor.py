"""Executor - 单任务 ReAct 执行器。

复用现有 agent.py 的 ReAct 串行循环逻辑。
Phase 4 会扩展不确定性检测（Self-Ask）。
"""
from typing import Dict, Optional, List, Any


class Executor:
    def __init__(self, llm_client, memory, tool_registry,
                 max_iterations: int = 25,
                 self_asker=None,
                 enable_uncertainty_check: bool = True):
        """Phase 4: 默认开启不确定性检测。"""
        self.llm = llm_client
        self.memory = memory
        self.registry = tool_registry
        self.max_iterations = max_iterations
        self.self_asker = self_asker
        self.enable_uncertainty_check = enable_uncertainty_check

    def execute(self, task: Dict) -> Dict:
        """执行单个任务，返回更新后的 task（含 result / status）。"""
        # 把任务描述塞进 memory
        self.memory.add_message("user", f"[Task {task['id']}] {task['desc']}")
        # 重试时带反思反馈
        if task.get("feedback"):
            self.memory.add_message("user", f"[Retry feedback] {task['feedback']}")

        for iteration in range(self.max_iterations):
            try:
                stream_response = self.llm.chat(
                    messages=self.memory.get_messages(),
                    tools=self.registry.get_all_schemas(),
                    stream=True,
                )
            except Exception as e:
                task["result"] = f"LLM error: {e}"
                task["status"] = "failed"
                return task

            # 解析 Thought + tool_calls + final_answer
            thought, tool_calls, final_answer = self._parse_stream(stream_response)

            # 如果有 final_answer 且无 tool_calls，任务完成
            if final_answer and not tool_calls:
                task["result"] = final_answer
                task["status"] = "done"
                return task

            # 串行执行 tool_calls
            for tc in tool_calls:
                try:
                    result = self.registry.execute_tool(tc["name"], **tc.get("args", {}))
                except Exception as e:
                    result = f"Tool error: {e}"
                self.memory.add_message("tool", result, tool_call_id=tc.get("id", ""))

            # Phase 4 不确定性检测（Phase 1 默认关闭）
            if self.enable_uncertainty_check and self.self_asker:
                last_obs = self.memory.get_last_message().get("content", "") if hasattr(self.memory, 'get_last_message') else ""
                if last_obs:
                    try:
                        verdict = self.self_asker.check_uncertainty(last_obs, task)
                        if verdict.startswith("uncertain"):
                            user_clarification = self.self_asker.ask(task["desc"], verdict)
                            self.memory.add_message("user", f"[Clarification] {user_clarification}")
                    except Exception:
                        pass  # SelfAsker 失败不阻断

        # 达到 max_iterations 仍未完成
        task["result"] = "Max iterations reached"
        task["status"] = "failed"
        return task

    def _parse_stream(self, stream_response) -> tuple:
        """解析 LLM 流式响应，返回 (thought, tool_calls, final_answer)。

        复用现有 agent.py 的解析逻辑。tool_calls 为 list of dict：
        [{"id": str, "name": str, "args": dict}]
        """
        thought = ""
        tool_calls: List[Dict] = []
        final_answer: Optional[str] = None

        # 处理流式或非流式响应
        if hasattr(stream_response, '__iter__'):
            for chunk in stream_response:
                if isinstance(chunk, str):
                    thought += chunk
                elif isinstance(chunk, dict):
                    # 兼容非流式 dict 响应
                    content = chunk.get("content", "")
                    if content:
                        thought += content
                    tcs = chunk.get("tool_calls")
                    if tcs:
                        tool_calls.extend(tcs)
        else:
            # dict 响应
            if isinstance(stream_response, dict):
                thought = stream_response.get("content", "")
                tcs = stream_response.get("tool_calls")
                if tcs:
                    tool_calls = tcs

        # 如果有内容且无 tool_calls，认为是 final_answer
        if thought and not tool_calls:
            final_answer = thought

        return thought, tool_calls, final_answer
