"""Token 消耗跟踪器：累计会话内每次 LLM 调用的 prompt/completion/total tokens。

支持：
- 记录每次调用的 token 用量（若 API 未返回 usage，可用估算值兜底）
- 累计会话总量、调用次数、平均每次
- 格式化显示（紧凑行 + 详细面板）
- 按模型分组统计
"""
from datetime import datetime
from typing import Dict, List, Optional, Any


class TokenTracker:
    """累计会话内 LLM token 消耗。"""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self.total_prompt: int = 0
        self.total_completion: int = 0
        self.total_tokens: int = 0

    def record(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None,
        model: str = "",
    ) -> Dict[str, Any]:
        """记录一次 LLM 调用的 token 用量，返回该次记录 dict。"""
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        entry = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": model,
            "timestamp": datetime.now().isoformat(),
        }
        self.calls.append(entry)
        self.total_prompt += prompt_tokens
        self.total_completion += completion_tokens
        self.total_tokens += total_tokens
        return entry

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """粗略估算 token 数（4 字符 ≈ 1 token）。"""
        return max(0, len(text or "") // 4)

    def record_estimated(self, prompt_text: str, completion_text: str, model: str = "") -> Dict[str, Any]:
        """API 未返回 usage 时用字符数估算兜底。"""
        p = self.estimate_tokens(prompt_text)
        c = self.estimate_tokens(completion_text)
        return self.record(p, c, p + c, model)

    def summary(self) -> Dict[str, Any]:
        """返回会话汇总（供 UI 显示）。"""
        return {
            "total_prompt": self.total_prompt,
            "total_completion": self.total_completion,
            "total_tokens": self.total_tokens,
            "call_count": len(self.calls),
            "avg_per_call": (self.total_tokens // len(self.calls)) if self.calls else 0,
        }

    def by_model(self) -> Dict[str, Dict[str, int]]:
        """按模型分组统计 token。"""
        grouped: Dict[str, Dict[str, int]] = {}
        for c in self.calls:
            m = c["model"] or "unknown"
            if m not in grouped:
                grouped[m] = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}
            grouped[m]["prompt"] += c["prompt_tokens"]
            grouped[m]["completion"] += c["completion_tokens"]
            grouped[m]["total"] += c["total_tokens"]
            grouped[m]["calls"] += 1
        return grouped

    def reset(self) -> None:
        """清空所有记录（新会话时调用）。"""
        self.calls.clear()
        self.total_prompt = 0
        self.total_completion = 0
        self.total_tokens = 0

    def format_compact(self) -> str:
        """格式化为紧凑单行（每次回复后显示）。"""
        s = self.summary()
        if s["call_count"] == 0:
            return ""
        return (
            f"Tokens: {s['total_prompt']:,} in → {s['total_completion']:,} out "
            f"(total {s['total_tokens']:,}) | {s['call_count']} calls"
        )
