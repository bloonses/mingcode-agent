"""Reflector - 任务结果反思评估。

Phase 2: LLM 假成功检测 + 失败原因反馈。
- status=done → 调 LLM 判断 result 是否真正完成（避免假成功）
- status=failed → 直接返回 fail: <result>（不调 LLM）
"""
from typing import Dict


class Reflector:
    def __init__(self, llm_client):
        self.llm = llm_client

    def evaluate(self, task: Dict) -> str:
        """评估任务执行结果，返回 'success' 或 'fail: <reason>'。"""
        status = task.get("status")
        result = task.get("result", "")

        if status == "failed":
            # 已知失败，不调 LLM
            return f"fail: {result}"

        if status == "done":
            # 假成功检测：LLM 判断 result 是否真正完成
            try:
                verdict = self._llm_evaluate(task)
                if verdict == "ok":
                    return "success"
                else:
                    return verdict if verdict.startswith("fail") else f"fail: {verdict}"
            except Exception:
                # LLM 失败兜底：信任 status=done
                return "success"

        # 未知 status 兜底
        return f"fail: unknown status {status}"

    def _llm_evaluate(self, task: Dict) -> str:
        """~150 token LLM 调用判断结果是否真正完成。

        返回 'ok' 或 'fail: <原因>'。
        """
        desc = task.get("desc", "")
        result = task.get("result", "")
        # 截断过长 result
        if len(result) > 500:
            result = result[:500] + "...[truncated]"

        prompt = (
            f"任务: {desc}\n"
            f"执行结果: {result}\n\n"
            f"判断任务是否真正完成（注意假成功：结果含 Error/Traceback/失败/异常 等）。\n"
            f"只输出 'ok' 或 'fail: <原因>'。"
        )
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ], stream=False)
        return (response.get("content") or "fail: no response").strip()
