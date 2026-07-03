"""AskUserTool - 让 AI 在行动前向用户提问以明确意图。

设计：
- 通过依赖注入的 prompt_func 回调获取用户输入，默认为内置 input。
- 这样既能在真实 CLI 中阻塞等待用户输入，也便于测试注入 mock。
- 在终端提问时使用 Neon 风格高亮问题，提升可识别度。
"""
from typing import Callable, Optional

from .base import BaseTool

try:
    from ui.theme import NEON_TEAL
    from ui.console import console
    _HAS_UI = True
except Exception:
    _HAS_UI = False
    NEON_TEAL = "cyan"
    console = None


class AskUserTool(BaseTool):
    name = "ask_user"
    description = (
        "向用户提出一个澄清问题以明确意图或确认方案。"
        "在执行非平凡任务前、需求模糊、或存在多种实现选择时调用此工具。"
        "一次只问一个问题，等待用户回答后再继续。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "要问用户的单个问题，简洁明确，聚焦一个决策点"
            }
        },
        "required": ["question"]
    }

    def __init__(self, prompt_func: Optional[Callable[[str], str]] = None):
        # 默认用内置 input；注入回调便于测试和未来接 IM 渠道
        self._prompt_func = prompt_func if prompt_func is not None else input

    def execute(self, **kwargs) -> str:
        question = kwargs.get("question") or ""
        question = question.strip()
        if not question:
            return "Error: question is required"

        if _HAS_UI and console is not None:
            console.print()
            console.print(f"[{NEON_TEAL} bold]AI 提问[/{NEON_TEAL} bold]")
        # 始终把原始 question 传给 prompt_func，由其负责展示
        answer = self._prompt_func(question)

        if answer is None:
            return "(no input)"
        answer = answer.strip()
        return answer if answer else "(no input)"
