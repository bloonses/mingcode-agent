"""SelfAsker - 不确定性检测 + Self-Ask。

Phase 4: LLM 不确定性检测 + 调 ask_user 工具向用户提问。
- check_uncertainty: ~100 token 判断 confident/uncertain
- ask: 调 registry.execute_tool("ask_user", ...) 向用户提问
"""
from typing import Dict


class SelfAsker:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.registry = tool_registry

    def check_uncertainty(self, last_observation: str, task: Dict) -> str:
        """判断是否不确定。返回 'confident' 或 'uncertain: <reason>'。"""
        try:
            # 截断过长 observation
            obs = last_observation
            if len(obs) > 500:
                obs = obs[:500] + "...[truncated]"

            prompt = (
                f"当前任务: {task.get('desc', '')}\n"
                f"最新观察: {obs}\n\n"
                f"基于当前进度，任务是否清晰可继续？\n"
                f"- 如果观察显示任务正常进行（如工具返回有效结果、文件存在等），输出 'confident'\n"
                f"- 如果观察显示有歧义、缺少信息、或需要用户确认（如文件不存在、参数模糊等），输出 'uncertain: <需要澄清的问题>'\n"
                f"只输出 'confident' 或 'uncertain: <问题>'。"
            )
            response = self.llm.chat([
                {"role": "user", "content": prompt}
            ], stream=False)
            content = (response.get("content") or "").strip()
            if not content:
                return "confident"
            return content
        except Exception:
            # LLM 失败兜底 confident（不阻断）
            return "confident"

    def ask(self, task_desc: str, uncertainty_reason: str) -> str:
        """触发 Self-Ask：调 ask_user 工具向用户提问。"""
        try:
            # 从 "uncertain: <reason>" 提取问题
            question = uncertainty_reason
            if ":" in uncertainty_reason:
                question = uncertainty_reason.split(":", 1)[1].strip()

            prompt = f"[Self-Ask] 任务「{task_desc}」需要澄清：{question}"
            result = self.registry.execute_tool("ask_user", prompt=prompt)
            return result if result else ""
        except Exception:
            # ask_user 失败不阻断
            return ""
