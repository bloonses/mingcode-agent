# core/reflector.py
"""Reflector - 反思任务结果，LLM 假成功检测。

Phase 3: LLM 评估 + 失败兜底
"""
from langchain_core.messages import HumanMessage, SystemMessage


class Reflector:
    """Reflector - 评估任务结果是否真的成功。"""

    def __init__(self, llm=None):
        self.llm = llm

    def invoke(self, task: dict) -> str:
        """评估任务结果。

        Returns:
            "success" 或 "fail: <reason>"
        """
        status = task.get("status", "")
        result = task.get("result", "") or ""

        # 规则 1：status=failed 直接 fail
        if status == "failed":
            return f"fail: {result[:200]}"

        # 规则 2：result 含错误关键词
        error_keywords = ("error", "traceback", "exception", "failed", "失败", "错误")
        lower_result = result.lower()
        for kw in error_keywords:
            if kw in lower_result:
                return f"fail: result contains '{kw}'"

        # 规则 3：LLM 假成功检测
        if self.llm is None:
            return "success"
        try:
            return self._llm_evaluate(task)
        except Exception:
            # 兜底：LLM 异常时不阻塞流程
            return "success"

    def _llm_evaluate(self, task: dict) -> str:
        """LLM 评估 result 是否真的成功。"""
        result = task.get("result", "") or ""
        # 截断长 result
        if len(result) > 500:
            result = result[:500] + "... [truncated]"

        prompt = f"""评估以下任务结果是否真的成功：

任务描述: {task.get('desc', '')}
状态: {task.get('status', '')}
结果:
{result}

判断标准:
- SUCCESS: 结果确实完成了任务，无遗留问题
- FAIL: <reason>: 结果有问题（如代码语法错误、逻辑漏洞、未处理边界情况等）

只输出 SUCCESS 或 FAIL: <reason>，不要其他文字。"""

        response = self.llm.invoke([
            SystemMessage(content="你是任务结果评估助手，识别假成功。"),
            HumanMessage(content=prompt),
        ])
        content = getattr(response, "content", "") or ""
        content = content.strip()

        if content.upper().startswith("SUCCESS"):
            return "success"
        if content.upper().startswith("FAIL"):
            # 提取 reason
            if ":" in content:
                reason = content.split(":", 1)[1].strip()
                return f"fail: {reason}"
            return "fail: LLM 判定失败"
        # 兜底
        return "success"
