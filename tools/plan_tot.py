"""PlanToTTool - 思维树（Tree of Thoughts）规划工具。

在行动前对复杂任务进行 思考 → 评估 → 筛选 的循环：
1. 生成多个候选方案（思考分支）
2. 对每个方案评估优缺点
3. 筛选最优方案并输出可执行计划

通过单次 LLM 非流式调用 + 结构化 prompt 实现，简单可靠。
"""
from typing import Any

from .base import BaseTool


_TOT_PROMPT_TEMPLATE = """对以下任务进行思维树（Tree of Thoughts）规划。

任务: {task}

请严格按以下结构输出（使用 Markdown），完成"思考 → 评估 → 筛选"的完整循环后再给出最终计划：

## 候选方案

### 方案 1: <简短名称>
- 思路: <实现路径与关键步骤>
- 优点: <该方案的优势>
- 缺点: <该方案的代价/风险>

### 方案 2: <简短名称>
- 思路: ...
- 优点: ...
- 缺点: ...

### 方案 3: <简短名称>
- 思路: ...
- 优点: ...
- 缺点: ...

## 评估
<对 3 个候选方案进行横向对比，从复杂度/风险/收益/契合度等维度分析>

## 最优方案
<选中的方案名称> —— <选择理由>

## 最终计划
<基于最优方案的可执行步骤化计划，每步 2-5 分钟粒度，便于直接交付执行>
"""


class PlanToTTool(BaseTool):
    name = "plan_tot"
    description = (
        "对复杂任务使用思维树（Tree of Thoughts）进行规划："
        "生成 3 个候选方案 → 评估优缺点 → 筛选最优方案 → 输出可执行计划。"
        "在执行非平凡任务（新功能/重构/架构改动）前调用此工具，"
        "完成思考→评估→筛选循环后再行动。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "需要规划的任务描述，应包含足够上下文让 LLM 理解目标和约束"
            }
        },
        "required": ["task"]
    }

    def __init__(self, llm: Any):
        # 依赖注入 LLMClient，避免硬依赖具体类型
        self.llm = llm

    def execute(self, **kwargs) -> str:
        task = (kwargs.get("task") or "").strip()
        if not task:
            return "Error: task is required"

        prompt = _TOT_PROMPT_TEMPLATE.format(task=task)
        try:
            resp = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
        except Exception as e:
            return f"PlanToT 失败（LLM 调用错误）: {e}"

        content = (resp or {}).get("content") or ""
        return content if content.strip() else "(空响应)"
