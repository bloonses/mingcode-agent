"""CognitiveController - 综合认知框架状态机。

综合 4 种认知框架：
- Plan-and-Execute: 先拆任务再逐个执行
- Self-Reflection: 执行后反思（Phase 2 实现）
- Thinking (ToT): 规划时多候选（Phase 3 实现）
- Self-Ask: 执行中遇不确定向用户提问（Phase 4 实现）

Phase 1: 仅 Plan-and-Execute，Reflector 为 stub。
"""
from enum import Enum
from typing import Optional, List, Dict, Any


class State(Enum):
    CLASSIFY = "classify"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    DONE = "done"


class CognitiveController:
    def __init__(self, llm_client, memory, tool_registry,
                 planner=None, executor=None, reflector=None, self_asker=None,
                 max_replans: int = 3, max_task_retries: int = 2):
        self.llm = llm_client
        self.memory = memory
        self.registry = tool_registry
        # 延迟 import 避免循环依赖
        from core.planner import Planner
        from core.executor import Executor
        from core.reflector import Reflector
        from core.self_asker import SelfAsker
        self.planner = planner or Planner(llm_client)
        self.executor = executor or Executor(llm_client, memory, tool_registry)
        self.reflector = reflector or Reflector(llm_client)
        self.self_asker = self_asker or SelfAsker(llm_client, tool_registry)
        self.max_replans = max_replans
        self.max_task_retries = max_task_retries
        self.state = State.CLASSIFY
        self.task_list: List[Dict] = []
        self.current_task_idx = 0
        self.replan_count = 0
        self._user_input = ""

    def chat(self, user_input: str) -> str:
        """主入口：分类 → PLANNING → EXECUTING → REFLECTING → DONE。"""
        self._user_input = user_input
        if self._classify(user_input) == "simple":
            return self._fallback_to_react(user_input)

        self.state = State.PLANNING
        self.task_list = self.planner.execute(user_input)
        self.state = State.EXECUTING  # 初始规划后直接进入执行，避免误触发 _step_replan

        while self.state != State.DONE:
            if self.state == State.PLANNING:
                self._step_replan()
            elif self.state == State.EXECUTING:
                self._step_execute()
            elif self.state == State.REFLECTING:
                self._step_reflect()

        return self._build_answer()

    def _classify(self, input: str) -> str:
        """分类 simple/complex。

        本地规则预过滤（零 LLM 调用）：
        - 输入 <= 6 字符 → simple（hi/hello/你好/在吗 等）
        - 包含常见问候/闲聊词 → simple
        - 否则调 LLM 轻量分类，失败兜底 simple
        """
        stripped = input.strip()

        # 规则 1：短输入直接 simple（避免对 hi 你好 这种调 LLM）
        if len(stripped) <= 6:
            return "simple"

        # 规则 2：包含常见问候/闲聊关键词
        greeting_patterns = (
            "你好", "您好", "嗨", "哈喽", "在吗", "在不在", "thanks", "thank you",
            "谢谢", "辛苦", "再见", "bye",
        )
        lower_stripped = stripped.lower()
        for pattern in greeting_patterns:
            if pattern in lower_stripped:
                return "simple"

        # 规则 3：LLM 轻量分类
        try:
            prompt = (
                f"用户输入: {input}\n\n"
                f"这是简单对话（SIMPLE）还是复杂任务（COMPLEX）？\n"
                f"- SIMPLE: 问候、闲聊、单步问答\n"
                f"- COMPLEX: 需要拆分多步、写代码、分析、创建\n"
                f"只输出一个词：SIMPLE 或 COMPLEX"
            )
            response = self.llm.chat([
                {"role": "user", "content": prompt}
            ], stream=False)
            content = (response.get("content") or "").strip().upper()
            if "COMPLEX" in content:
                return "complex"
            return "simple"
        except Exception:
            return "simple"

    def _fallback_to_react(self, input: str) -> str:
        """简单输入走现有 ReAct（Phase 1 暂返回 placeholder，Task 5 接入 NeonAgent）。"""
        return f"[React fallback] {input}"

    def _step_execute(self):
        """执行当前任务。"""
        task = self.task_list[self.current_task_idx]
        task["status"] = "executing"
        result_task = self.executor.execute(task)
        # 只更新 result 和 status，保留 retries 和 feedback（由 _step_reflect 管理）
        task["result"] = result_task.get("result", "")
        task["status"] = result_task.get("status", "")
        self.state = State.REFLECTING

    def _step_reflect(self):
        """反思当前任务结果，实现 L1/L2/L3 分级降级。"""
        task = self.task_list[self.current_task_idx]
        verdict = self.reflector.evaluate(task)

        if verdict == "success":
            # 任务成功，下一个
            task["status"] = "done"
            self.current_task_idx += 1
            if self.current_task_idx >= len(self.task_list):
                self.state = State.DONE
            else:
                self.state = State.EXECUTING
        else:
            # 失败
            task["retries"] = task.get("retries", 0) + 1
            task["feedback"] = verdict

            if task["retries"] <= self.max_task_retries:
                # L1: 局部重试（回 EXECUTING，带 feedback）
                self.state = State.EXECUTING
            else:
                # 局部重试耗尽
                self.replan_count += 1
                if self.replan_count <= self.max_replans:
                    # L2: 整体重规划
                    self.state = State.PLANNING
                else:
                    # L3: 报错给用户
                    task["status"] = "failed"
                    self.state = State.DONE

    def _step_replan(self):
        """L2 重规划：带 Reflect feedback 调 Planner.execute。"""
        feedback = [t.get("feedback") for t in self.task_list if t.get("feedback")]
        new_tasks = self.planner.execute(self._user_input, feedback=feedback)
        self.task_list = new_tasks
        self.current_task_idx = 0
        self.state = State.EXECUTING

    def _build_answer(self) -> str:
        """汇总所有任务结果生成最终回答。"""
        results = []
        for task in self.task_list:
            status = task.get("status", "unknown")
            desc = task.get("desc", "")
            result = task.get("result", "")
            results.append(f"[{status}] {desc}: {result}")
        return "\n".join(results) if results else "No tasks executed"
