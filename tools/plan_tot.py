"""plan_tot 工具 - 调用 Planner 薄包装（Phase 3 DRY）。

Phase 1/2: 内含 ToT 逻辑
Phase 3: 改为调用 core.planner.Planner.execute，DRY
"""
from .base import BaseTool


class PlanToTTool(BaseTool):
    name = "plan_tot"
    description = (
        "使用思维树（ToT）生成任务计划。生成多个候选计划，评估后选最优。"
        "输入用户需求，返回任务列表。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "用户需求描述"
            }
        },
        "required": ["input"]
    }

    def __init__(self, planner=None, llm_client=None):
        """planner 可注入；不注入时用 llm_client 构造默认 Planner（延迟构造）。"""
        self._planner = planner
        self._llm_client = llm_client

    def execute(self, **kwargs) -> str:
        input_text = (kwargs.get("input") or "").strip()
        if not input_text:
            return "Error: input is required"

        planner = self._get_planner()
        tasks = planner.execute(input_text)
        return str(tasks)

    def _get_planner(self):
        """延迟构造 Planner（避免循环依赖）。"""
        if self._planner is None:
            from core.planner import Planner
            if self._llm_client is None:
                raise RuntimeError("planner or llm_client required")
            self._planner = Planner(self._llm_client)
        return self._planner
