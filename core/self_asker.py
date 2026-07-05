# core/self_asker.py 升级版
"""SelfAsker - LLM 不确定性检测 + ask_user 工具。"""
from langchain_core.messages import HumanMessage, SystemMessage


class SelfAsker:
    """SelfAsker - 检测不确定性，必要时向用户提问。"""

    def __init__(self, llm=None, tools=None):
        self.llm = llm
        self.tools = tools or []

    def invoke(self, context: str) -> str:
        """检测不确定性。

        Returns:
            "confident" 或 "uncertain: <reason>"
        """
        if self.llm is None:
            return "confident"
        try:
            prompt = f"""判断以下任务上下文是否存在不确定因素：

{context}

判断标准:
- CONFIDENT: 任务清晰、参数明确、无歧义
- UNCERTAIN: <reason>: 缺少关键信息（如文件路径、参数值、目标对象等）

只输出 CONFIDENT 或 UNCERTAIN: <reason>。"""
            response = self.llm.invoke([
                SystemMessage(content="你是不确定性检测助手。"),
                HumanMessage(content=prompt),
            ])
            content = getattr(response, "content", "") or ""
            content = content.strip()
            if content.upper().startswith("UNCERTAIN"):
                if ":" in content:
                    reason = content.split(":", 1)[1].strip()
                    return f"uncertain: {reason}"
                return "uncertain: 需要用户澄清"
            return "confident"
        except Exception:
            return "confident"

    def ask(self, question: str) -> str:
        """调 ask_user 工具向用户提问。"""
        # 查找 ask_user 工具
        for tool in self.tools:
            if hasattr(tool, "name") and tool.name == "ask_user":
                try:
                    return tool.invoke({"question": question})
                except Exception as e:
                    return f"(提问失败: {e})"
        # 兜底：直接 input
        try:
            return input(f"\n[AI 问题] {question}\n> ")
        except (EOFError, KeyboardInterrupt):
            return "(用户取消)"
